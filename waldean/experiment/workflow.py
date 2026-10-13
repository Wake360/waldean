from __future__ import annotations

import dataclasses
import json
import shutil
from pathlib import Path

import nbformat

from ..analysis.dataflow import analyze
from ..analysis.ingest import parse_notebook
from ..checks.detect import run_static
from ..core.flag import Flag
from ..runtime.execute import KERNEL_NAME, execute, provenance, scrubbed_env, stdout_lines
from .plan import PlanError, contradictions, design, design_md, read_plan, write_plan
from .profile import profile, sha256
from .render import render


def dataset_path(exp: Path, plan: dict) -> Path:
    return (exp / plan["dataset"]["path"]).resolve()


def create(csv_path, target: str, out_dir, goal: str = "", exclude=(), time_column: str | None = None,
           seed: int = 0, *, keep=(), group_column: str | None = None, task: str | None = None) -> Path:
    csv, out = Path(csv_path).resolve(), Path(out_dir).resolve()
    prof = profile(csv, target, task=task)
    plan = design(prof, csv, out, goal, list(exclude), time_column, seed, keep=list(keep), group_column=group_column)
    out.mkdir(parents=True, exist_ok=True)
    write_plan(plan, out / "plan.yaml")
    (out / "design.md").write_text(design_md(plan, prof), encoding="utf-8")
    return out


def build(exp_dir) -> tuple[list[str], list[Flag]]:
    exp = Path(exp_dir).resolve()
    plan = read_plan(exp / "plan.yaml")
    csv = dataset_path(exp, plan)
    if sha256(csv) != plan["dataset"]["sha256"]:
        raise PlanError(f"{csv.name} changed since create: its sha256 differs from plan.yaml")
    fields = contradictions(plan, profile(csv, plan["target"], task=plan.get("task")))
    if fields:
        return fields, []
    nb_path = exp / "experiment.ipynb"
    nbformat.write(render(plan), nb_path)
    parsed = parse_notebook(nb_path)
    flags = run_static(parsed, analyze(parsed))
    (exp / "check.json").write_text(json.dumps([dataclasses.asdict(f) for f in flags], indent=2), encoding="utf-8")
    hashes = {"dataset": sha256(csv), "plan": sha256(exp / "plan.yaml"), "notebook": sha256(nb_path)}
    (exp / "build.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    return [], flags


def limitations(plan: dict, metrics: dict) -> str:
    lines = ["# Limitations", ""] + [f"- {a}" for a in plan["assumptions"] + plan["limitations"]]
    reason = plan["split"].get("override_reason")
    if reason:
        lines.append(f"- The split was overridden by the user: \"{reason}\".")
    if metrics.get("skipped_folds"):
        lines.append(f"- {metrics['skipped_folds']} CV fold(s) were skipped because their train or test rows hold one class.")
    return "\n".join(lines) + "\n"


def run(exp_dir, timeout: int = 600) -> Path:
    exp = Path(exp_dir).resolve()
    recorded = json.loads((exp / "build.json").read_text(encoding="utf-8"))
    plan = read_plan(exp / "plan.yaml")
    files = {"dataset": dataset_path(exp, plan), "plan": exp / "plan.yaml", "notebook": exp / "experiment.ipynb"}
    for key, path in files.items():
        if sha256(path) != recorded[key]:
            raise PlanError(f"{path.name} changed since build: its sha256 differs from build.json")
    nb = nbformat.read(files["notebook"], as_version=4)
    with scrubbed_env():
        try:
            executed = execute(nb, timeout=timeout, cwd=str(exp), kernel_name=KERNEL_NAME)
        except Exception as exc:
            ename, evalue = getattr(exc, "ename", None), getattr(exc, "evalue", None)
            reason = f"{ename}: {evalue}" if ename else str(exc)
            raise RuntimeError(f"experiment.ipynb failed: {reason}") from exc
    lines = stdout_lines(executed, "WALDEAN_METRICS ")
    if not lines:
        raise RuntimeError("experiment.ipynb printed no WALDEAN_METRICS line")
    metrics = json.loads(lines[-1].removeprefix("WALDEAN_METRICS "))
    ev = exp / "evidence"
    ev.mkdir(exist_ok=True)
    nbformat.write(executed, ev / "experiment.ipynb")
    for name in ("plan.yaml", "build.json", "check.json"):
        shutil.copyfile(exp / name, ev / name)
    (ev / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    (ev / "environment.json").write_text(json.dumps(provenance(), indent=2), encoding="utf-8")
    (ev / "limitations.md").write_text(limitations(plan, metrics), encoding="utf-8")
    return ev
