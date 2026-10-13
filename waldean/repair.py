from __future__ import annotations

import contextlib
import difflib
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import nbformat

from .dataflow import NotebookDataflow, analyze
from .detect import DEFAULT_CONFIDENCE_FLOOR, Flag, run_static
from .ingest import ParsedNotebook, parse_notebook
from .taxonomy import load_taxonomy

SCHEMA = 1
DEFAULT_OUT = Path(".waldean") / "repairs"
PROVENANCE_PACKAGES = ("numpy", "pandas", "scikit-learn")
KERNEL_NAME = "waldean-verify"
SECRET_ENV_RE = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", re.IGNORECASE)
RULES = (
    "Edit only the cells in the edit scope.",
    "Outside the edit scope, only add import lines.",
    "Do not add, delete, split or merge cells.",
    "Do not change the data, the features, the model or the metric.",
    "Keep the evaluation call. Change how it splits the data.",
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
        repair_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, repair_dir / f"original{path.suffix}")
        (repair_dir / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
        (repair_dir / "brief.md").write_text(render_brief(protocol, repair_dir), encoding="utf-8")
        written.append(repair_dir)
    return written, unsupported


def _import_only(old: str, new: str) -> bool:
    for line in difflib.ndiff(old.splitlines(), new.splitlines()):
        if line.startswith("- "):
            return False
        added = line[2:].strip()
        if line.startswith("+ ") and added and not added.startswith(("import ", "from ")):
            return False
    return True


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
    (repair_dir / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence


@contextlib.contextmanager
def scrubbed_env():
    removed = {k: os.environ.pop(k) for k in list(os.environ) if SECRET_ENV_RE.search(k)}
    try:
        yield sorted(removed)
    finally:
        os.environ.update(removed)


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
    from .execute import execute

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
