from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from .dataflow import NotebookDataflow, analyze
from .detect import DEFAULT_CONFIDENCE_FLOOR, Flag, run_static
from .ingest import ParsedNotebook, parse_notebook
from .taxonomy import load_taxonomy

SCHEMA = 1
DEFAULT_OUT = Path(".waldean") / "repairs"
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
