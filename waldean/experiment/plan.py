from __future__ import annotations

import os
from pathlib import Path

import yaml

TEST_FRACTION = 0.2
N_SPLITS = 5
SPLIT_KINDS = ("temporal_holdout", "stratified_kfold")
MODELS = ["DummyClassifier(strategy='prior')", "HistGradientBoostingClassifier(early_stopping=False)"]
METRICS = ["roc_auc", "average_precision", "balanced_accuracy"]
LIMITATIONS = [
    "Repeated entities and leaking columns are not detected. Exclude them with --exclude.",
    "Binary classification only. The goal text is stored, not interpreted.",
]


class PlanError(ValueError):
    pass


def time_column_names(prof: dict) -> list[str]:
    return [t["column"] for t in prof["time_columns"]]


def choose_time_column(prof: dict, time_column: str | None) -> str | None:
    names = time_column_names(prof)
    if time_column is not None:
        if time_column not in names:
            raise PlanError(f"--time-column {time_column!r} is not a time column; candidates: {names}")
        return time_column
    if len(names) > 1:
        raise PlanError(f"several time columns {names}: pick one with --time-column")
    return names[0] if names else None


def design(prof: dict, csv_path: Path, out_dir: Path, goal: str, exclude: list[str],
           time_column: str | None, seed: int) -> dict:
    for col in exclude:
        if col not in prof["columns"]:
            raise PlanError(f"--exclude {col!r} is not a column")
    col = choose_time_column(prof, time_column)
    excluded = [{"column": c, "reason": "excluded by the user (--exclude)"} for c in exclude]
    if col is not None:
        excluded.append({"column": col, "reason": "time column, used for the split only"})
        split = {"kind": "temporal_holdout", "column": col, "test_fraction": TEST_FRACTION, "n_splits": N_SPLITS}
        assumptions = [f"The model is meant for rows later than the data, so every split trains on earlier "
                       f"values of {col} than it tests on."]
    else:
        split = {"kind": "stratified_kfold", "column": None, "test_fraction": TEST_FRACTION, "n_splits": N_SPLITS}
        assumptions = ["No time column was found, so rows are treated as exchangeable."]
    dropped = {e["column"] for e in excluded} | {prof["target"]}
    features = [c for c in prof["columns"] if c not in dropped]
    return {
        "dataset": {"path": os.path.relpath(csv_path, out_dir), "sha256": prof["sha256"], "rows": prof["rows"]},
        "goal": goal,
        "target": prof["target"],
        "positive_label": prof["positive_label"],
        "task": "classification",
        "excluded_columns": excluded,
        "features": {"numeric": [c for c in features if c in prof["numeric"]],
                     "categorical": [c for c in features if c not in prof["numeric"]]},
        "split": split,
        "models": MODELS,
        "metrics": METRICS,
        "seed": seed,
        "assumptions": assumptions,
        "limitations": LIMITATIONS,
    }


def contradictions(plan: dict, prof: dict) -> list[str]:
    split = plan["split"]
    if split.get("kind") not in SPLIT_KINDS:
        raise PlanError(f"split.kind must be one of {list(SPLIT_KINDS)}, got {split.get('kind')!r}")
    if split.get("override_reason"):
        return []
    names = time_column_names(prof)
    if split["kind"] == "temporal_holdout" and split.get("column") not in names:
        return ["split.column"]
    if split["kind"] != "temporal_holdout" and names:
        return ["split.kind"]
    return []


def design_md(plan: dict, prof: dict) -> str:
    split = plan["split"]
    lines = [f"# Design: {plan['target']}", "", f"Goal: {plan['goal'] or '(none given)'}", ""]
    if split["kind"] == "temporal_holdout":
        fact = next(t for t in prof["time_columns"] if t["column"] == split["column"])
        lines.append(f"Split: temporal_holdout on {split['column']}, because it parses as dates from "
                     f"{fact['min']} to {fact['max']} with {fact['periods']} distinct periods. The last "
                     f"{split['test_fraction']:.0%} of periods are the test set. CV runs walk-forward over "
                     f"the training periods in {split['n_splits']} folds.")
    else:
        lines.append(f"Split: stratified holdout of {split['test_fraction']:.0%} and {split['n_splits']}-fold "
                     f"stratified CV, because no time column was found.")
    lines += ["", f"Positive class: {plan['positive_label']!r} ({prof['positive_rate']:.1%} of labelled rows).",
              f"Models: {', '.join(plan['models'])}. Both are reported; neither is chosen by its test score.",
              f"Metrics: {', '.join(plan['metrics'])}.", "", "Excluded columns:"]
    lines += [f"- {e['column']}: {e['reason']}" for e in plan["excluded_columns"]] or ["- none"]
    lines += ["", "Assumptions:"] + [f"- {a}" for a in plan["assumptions"]]
    lines += ["", "Limitations:"] + [f"- {x}" for x in plan["limitations"]]
    return "\n".join(lines) + "\n"


def write_plan(plan: dict, path: Path) -> None:
    Path(path).write_text(yaml.safe_dump(plan, sort_keys=False, allow_unicode=True), encoding="utf-8")


def read_plan(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
