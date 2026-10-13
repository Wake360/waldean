from __future__ import annotations

import ast
import contextlib
import difflib
import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import nbformat

from ..analysis.dataflow import NotebookDataflow, _strip_magics, analyze
from ..checks.detect import _TEMPORAL_SPLITTERS, CV_SINKS, run_static
from ..core.flag import DEFAULT_CONFIDENCE_FLOOR, Flag
from ..analysis.ingest import ParsedNotebook, parse_notebook
from ..core.taxonomy import load_taxonomy
from ..runtime.execute import KERNEL_NAME, scrubbed_env

SCHEMA = 1
DEFAULT_OUT = Path(".waldean") / "repairs"
PROVENANCE_PACKAGES = ("numpy", "pandas", "scikit-learn")
GUARDED_NAMES = _TEMPORAL_SPLITTERS | CV_SINKS | {"train_test_split"}
RULES = (
    "Edit only the cells in the edit scope.",
    "Outside the edit scope, only add import lines.",
    "Do not add, delete, split or merge cells.",
    "Do not change the data, the features, the model or the metric.",
    "Keep the evaluation call.",
)


def supported(flaw_id: str) -> bool:
    return bool(load_taxonomy()[flaw_id].repair_invariant)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def where(nb: ParsedNotebook, flag: Flag) -> str:
    if nb.path is not None and nb.path.suffix == ".py":
        return f"line {nb.cells[flag.cell].start_line + flag.line - 1}"
    return f"cell {flag.cell}, line {flag.line}"


def edit_scope(flow: NotebookDataflow, flag: Flag) -> list[int]:
    cells = {flag.cell}
    for call in flow.calls:
        if (call.cell, call.line) != (flag.cell, flag.line) or call.name != flag.extra.get("sink"):
            continue
        for name in call.kw_args.get("cv", set()):
            ev = flow.last_assign(name, (call.cell, call.line))
            if ev is not None:
                cells.add(ev.cell)
    return sorted(cells)


def build_protocol(nb: ParsedNotebook, flow: NotebookDataflow, flags: list[Flag], path: Path) -> dict:
    d = load_taxonomy()[flags[0].flaw_id]
    return {
        "schema": SCHEMA,
        "id": f"{path.stem}--{d.id}",
        "status": "proposed",
        "flaw_id": d.id,
        "file": path.as_posix(),
        "original_sha256": sha256(path),
        "targets": [
            {"where": where(nb, f), "cell": f.cell, "line": f.line, "sink": f.extra["sink"],
             "confidence": f.confidence, "evidence": f.evidence}
            for f in flags
        ],
        "edit_scope": sorted(set().union(*(edit_scope(flow, f) for f in flags))),
        "instruction": d.repair_instruction,
        "invariant": d.repair_invariant,
        "fix": d.fix,
        "rules": list(RULES),
    }


def render_brief(protocol: dict, repair_dir: Path) -> str:
    if protocol["file"].endswith(".py"):
        cells = "cells are split at `# %%` markers and counted from 0; a file without markers is one cell"
    else:
        cells = "cells are counted from 0, markdown cells included"
    lines = [
        f"# Repair contract: {protocol['flaw_id']}",
        "",
        f"File: `{protocol['file']}`",
        "Status: proposed. Nothing has been changed or verified yet.",
        "",
        "## Finding",
        "",
        *(f"- {t['where']}: {t['evidence']}" for t in protocol["targets"]),
        "",
        "## Required change",
        "",
        protocol["instruction"],
        "",
        f"Invariant after the change: {protocol['invariant']}",
        "",
        f"Fix guidance: {protocol['fix']}",
        "",
        "## Rules",
        "",
        *(f"- {r}" for r in protocol["rules"]),
        f"- Edit scope: cells {', '.join(str(c) for c in protocol['edit_scope'])} ({cells}).",
        "",
        "## When done",
        "",
        f"Run `waldean verify {repair_dir.as_posix()}`. It rejects the change if a rule is broken "
        "or the finding remains.",
        "",
    ]
    return "\n".join(lines)


def propose(path: str | Path, out_root: Path = DEFAULT_OUT,
            floor: float = DEFAULT_CONFIDENCE_FLOOR) -> tuple[list[Path], list[str]]:
    path = Path(path)
    nb = parse_notebook(path)
    flow = analyze(nb)
    by_flaw: dict[str, list[Flag]] = {}
    unsupported = []
    for f in run_static(nb, flow):
        if f.confidence < floor:
            continue
        if supported(f.flaw_id):
            by_flaw.setdefault(f.flaw_id, []).append(f)
        else:
            unsupported.append(f"{f.flaw_id} at {where(nb, f)}: no repair contract for this class yet")
    written = []
    for flags in by_flaw.values():
        protocol = build_protocol(nb, flow, flags, path)
        repair_dir = out_root / protocol["id"]
        if repair_dir.is_symlink():
            raise ValueError(f"{repair_dir} is a symlink; refusing to write through it")
        repair_dir.mkdir(parents=True, exist_ok=True)
        for name in (f"original{path.suffix}", "protocol.json", "brief.md"):
            (repair_dir / name).unlink(missing_ok=True)
        shutil.copyfile(path, repair_dir / f"original{path.suffix}")
        (repair_dir / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
        (repair_dir / "brief.md").write_text(render_brief(protocol, repair_dir), encoding="utf-8")
        written.append(repair_dir)
    return written, unsupported


def _import_only(old: str, new: str) -> bool:
    diff = list(difflib.ndiff(old.splitlines(), new.splitlines()))
    if any(line.startswith("- ") for line in diff):
        return False
    added = "\n".join(line[2:] for line in diff if line.startswith("+ "))
    try:
        tree = ast.parse(added)
    except SyntaxError:
        return False
    return all(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body)


def _parse(source: str) -> ast.Module | None:
    try:
        return ast.parse(_strip_magics(source))
    except SyntaxError:
        return None


def _literal_no_shuffle(sources: list[str]) -> bool:
    for source in sources:
        tree = _parse(source)
        for node in ast.walk(tree) if tree else ():
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name == "train_test_split" and any(
                k.arg == "shuffle" and isinstance(k.value, ast.Constant) and k.value.value is False
                for k in node.keywords
            ):
                return True
    return False


def _renamed_imports(nb: ParsedNotebook) -> list[str]:
    reasons = []
    for cell in nb.code_cells:
        tree = _parse(cell.source)
        for node in ast.walk(tree) if tree else ():
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                reasons += [
                    f"import renames `{a.name}` to `{a.asname}`"
                    for a in node.names
                    if a.asname in GUARDED_NAMES and a.asname != a.name.rsplit(".", 1)[-1]
                ]
    return reasons


def static_checks(protocol: dict, original: ParsedNotebook, fixed: ParsedNotebook) -> list[str]:
    if [c.cell_type for c in original.cells] != [c.cell_type for c in fixed.cells]:
        return ["cells were added, removed or retyped; this version compares cell by cell"]
    scope = set(protocol["edit_scope"])
    reasons = [
        f"cell {o.index} changed outside the edit scope"
        for o, f in zip(original.cells, fixed.cells)
        if o.cell_type == "code" and o.index not in scope
        and o.source != f.source and not _import_only(o.source, f.source)
    ]
    flow = analyze(fixed)
    for sink in sorted({t["sink"] for t in protocol["targets"]}):
        if not any(c.name == sink and c.cell in scope for c in flow.calls):
            reasons.append(f"the evaluation call `{sink}` is no longer in the edit scope")
    if any(t["sink"] == "train_test_split" for t in protocol["targets"]) and not _literal_no_shuffle(
        [c.source for c in fixed.code_cells if c.index in scope]
    ):
        reasons.append("`train_test_split` in the edit scope does not pass the literal shuffle=False")
    reasons += _renamed_imports(fixed)
    fixed_flags = run_static(fixed, flow)
    reasons += [
        f"{f.flaw_id} is still reported at cell {f.cell}, line {f.line} (confidence {f.confidence:.2f})"
        for f in fixed_flags
        if f.flaw_id == protocol["flaw_id"] and f.cell in scope
    ]
    before = {f.flaw_id for f in run_static(original) if f.confidence >= DEFAULT_CONFIDENCE_FLOOR}
    reasons += [
        f"new finding {f.flaw_id} at cell {f.cell}, line {f.line}"
        for f in fixed_flags
        if f.confidence >= DEFAULT_CONFIDENCE_FLOOR and f.flaw_id not in before
    ]
    return reasons


def load_repair(repair_dir: Path) -> tuple[dict, Path]:
    protocol = json.loads((repair_dir / "protocol.json").read_text(encoding="utf-8"))
    if protocol.get("schema") != SCHEMA:
        raise ValueError(f"unsupported repair schema {protocol.get('schema')!r}")
    snapshot = repair_dir / f"original{Path(protocol['file']).suffix}"
    if sha256(snapshot) != protocol["original_sha256"]:
        raise ValueError(f"{snapshot} no longer matches the proposed original")
    nb = parse_notebook(snapshot)
    flow = analyze(nb)
    floor = min([DEFAULT_CONFIDENCE_FLOOR, *(t["confidence"] for t in protocol["targets"])])
    flags = [f for f in run_static(nb, flow) if f.flaw_id == protocol["flaw_id"] and f.confidence >= floor]
    scope = sorted(set().union(*(edit_scope(flow, f) for f in flags)))
    targets = sorted((f.cell, f.line, f.extra["sink"]) for f in flags)
    if scope != protocol["edit_scope"] or targets != sorted(
        (t["cell"], t["line"], t["sink"]) for t in protocol["targets"]
    ):
        raise ValueError("protocol.json does not match the snapshot; the contract was edited")
    return protocol, snapshot


def provenance() -> dict:
    packages = {}
    for name in PROVENANCE_PACKAGES:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    try:
        waldean_version = importlib.metadata.version("waldean")
    except importlib.metadata.PackageNotFoundError:
        waldean_version = "unknown"
    return {
        "waldean": waldean_version,
        "python": platform.python_version(),
        "platform": platform.system(),
        "packages": packages,
    }


def verify(repair_dir: str | Path, fixed_path: str | Path | None = None,
           metric: re.Pattern | None = None, timeout: int = 600) -> dict:
    repair_dir = Path(repair_dir)
    protocol, snapshot = load_repair(repair_dir)
    fixed = Path(fixed_path or protocol["file"])
    if metric is not None and fixed.suffix != ".ipynb":
        raise ValueError("--execute runs .ipynb notebooks only")
    reasons = static_checks(protocol, parse_notebook(snapshot), parse_notebook(fixed))
    evidence = {
        "schema": SCHEMA,
        "id": protocol["id"],
        "flaw_id": protocol["flaw_id"],
        "status": "rejected" if reasons else "static-pass",
        "original": {"path": snapshot.as_posix(), "sha256": sha256(snapshot)},
        "fixed": {"path": fixed.as_posix(), "sha256": sha256(fixed)},
        "edit_scope": protocol["edit_scope"],
        "static": {"passed": not reasons, "reasons": reasons},
        "execution": None,
        "provenance": provenance(),
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if not reasons and metric is not None:
        run = counterfactual(snapshot, fixed, metric, timeout)
        evidence["execution"] = run
        evidence["status"] = "verified" if run["complete"] else "inconclusive"
    (repair_dir / "evidence.json").unlink(missing_ok=True)
    (repair_dir / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence


def metric_values(nb_node, metric: re.Pattern) -> list[float]:
    values = []
    for cell in nb_node.cells:
        for out in cell.get("outputs", []):
            if out.get("output_type") != "stream":
                continue
            for line in out.get("text", "").splitlines():
                m = metric.search(line)
                if m:
                    with contextlib.suppress(ValueError):
                        values.append(float(m.group(1)))
    return values


def _first_line(exc: Exception) -> str:
    text = str(exc).strip()
    return f"{type(exc).__name__}: {text.splitlines()[0] if text else ''}"


def counterfactual(original: Path, fixed: Path, metric: re.Pattern, timeout: int) -> dict:
    from ..runtime.execute import execute

    cwd = str(fixed.resolve().parent)
    run = {"metric": metric.pattern, "cwd": cwd, "timeout_per_cell": timeout,
           "before": [], "after": [], "delta": None, "complete": False, "error": None}
    with scrubbed_env() as removed:
        run["env_removed"] = removed
        try:
            before = execute(nbformat.read(str(original), as_version=4),
                             timeout=timeout, cwd=cwd, kernel_name=KERNEL_NAME)
            after = execute(nbformat.read(str(fixed), as_version=4),
                            timeout=timeout, cwd=cwd, kernel_name=KERNEL_NAME)
        except Exception as exc:
            run["error"] = _first_line(exc)
            return run
    run["before"] = metric_values(before, metric)
    run["after"] = metric_values(after, metric)
    if not run["before"] and not run["after"]:
        run["error"] = "the metric pattern matched no output line"
    elif len(run["before"]) != len(run["after"]):
        run["error"] = "the metric pattern matched a different number of lines before and after"
    else:
        run["delta"] = [round(a - b, 6) for b, a in zip(run["before"], run["after"])]
        run["complete"] = True
    return run


def render_evidence(evidence: dict, repair_dir: Path) -> str:
    lines = [f"# Waldean repair — {evidence['id']}", "", f"status: {evidence['status']}", ""]
    static = evidence["static"]
    lines.append(f"- static checks: {'passed' if static['passed'] else 'failed'}")
    lines += [f"  - {r}" for r in static["reasons"]]
    run = evidence["execution"]
    if run is None:
        lines.append("- execution: not run (add --execute --metric REGEX to measure both protocols)")
    elif run["complete"]:
        lines.append(f"- metric `{run['metric']}`: before {run['before']}, after {run['after']}, "
                     f"delta {run['delta']}")
    else:
        lines.append(f"- execution: {run['error']}")
    lines += ["", f"evidence: {(repair_dir / 'evidence.json').as_posix()}", ""]
    return "\n".join(lines)
