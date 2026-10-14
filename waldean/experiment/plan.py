from __future__ import annotations

import os
from pathlib import Path

import yaml

TEST_FRACTION = 0.2
N_SPLITS = 5
SPLIT_KINDS = ("temporal_holdout", "group_kfold", "stratified_kfold", "kfold")
IMBALANCE_SHARE = 0.2
TASKS = {
    "binary": {"models": ["DummyClassifier(strategy='prior')", "HistGradientBoostingClassifier(early_stopping=False)"],
               "metrics": ["roc_auc", "average_precision", "balanced_accuracy"]},
    "multiclass": {"models": ["DummyClassifier(strategy='prior')", "HistGradientBoostingClassifier(early_stopping=False)"],
                   "metrics": ["balanced_accuracy", "macro_f1", "log_loss"]},
    "regression": {"models": ["DummyRegressor(strategy='mean')", "HistGradientBoostingRegressor(early_stopping=False)"],
                   "metrics": ["rmse", "mae", "r2"]},
}
LIMITATIONS = [
    "Leaking columns are found only by near-perfect correlation or purity against the target. A feature computed "
    "from the future with a weaker signal passes. Exclude it with --exclude.",
    "Repeated entities are found only in text columns and id-named integer columns with 20 or more values.",
    "The goal text is stored, not interpreted.",
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


def group_column_names(prof: dict) -> list[str]:
    return [g["column"] for g in prof["group_columns"]]


def choose_group_column(prof: dict, group_column: str | None) -> str | None:
    names = group_column_names(prof)
    if group_column == "none":
        return None
    if group_column is not None:
        if group_column not in names:
            raise PlanError(f"--group-column {group_column!r} is not a group column; candidates: {names}")
        return group_column
    if len(names) > 1:
        raise PlanError(f"several group columns {names}: pick one with --group-column, or pass --group-column none")
    return names[0] if names else None


def design(prof: dict, csv_path: Path, out_dir: Path, goal: str, exclude: list[str],
           time_column: str | None, seed: int, *, keep=(), group_column: str | None = None) -> dict:
    suspects = {s["column"]: s["reason"] for s in prof["suspects"]}
    for col in exclude:
        if col not in prof["columns"]:
            raise PlanError(f"--exclude {col!r} is not a column")
        if col == prof["target"]:
            raise PlanError(f"--exclude {col!r} is the target")
    for col in keep:
        if col not in suspects:
            raise PlanError(f"--keep {col!r} was not excluded automatically; nothing to keep")
    col = choose_time_column(prof, time_column)
    if col is not None and next(t for t in prof["time_columns"] if t["column"] == col)["ambiguous"]:
        raise PlanError(f"dates in {col!r} read differently day-first and month-first; rewrite them as YYYY-MM-DD")
    groups = group_column_names(prof)
    group = choose_group_column(prof, group_column) if col is None else None
    excluded = [{"column": c, "reason": "excluded by the user (--exclude)"} for c in exclude]
    excluded += [{"column": c, "reason": r} for c, r in suspects.items() if c not in exclude and c not in keep]
    task = prof["task"]
    if col is not None:
        excluded.append({"column": col, "reason": "time column, used for the split only"})
        split = {"kind": "temporal_holdout", "column": col, "test_fraction": TEST_FRACTION, "n_splits": N_SPLITS}
        assumptions = [f"The model is meant for rows later than the data, so every split trains on earlier "
                       f"values of {col} than it tests on."]
        if groups:
            named = ", ".join(groups)
            assumptions.append(f"Rows of the same {named} appear in several periods. The time split keeps later "
                               f"rows of an entity in the test set, which is the intended use; {named} stays a feature.")
    elif group is not None:
        excluded.append({"column": group, "reason": "group column, used for the split only"})
        split = {"kind": "group_kfold", "column": group, "test_fraction": TEST_FRACTION, "n_splits": N_SPLITS}
        assumptions = [f"Rows of the same {group} are not independent, so every split keeps all rows of a "
                       f"{group} on one side."]
    else:
        kind = "kfold" if task == "regression" else "stratified_kfold"
        split = {"kind": kind, "column": None, "test_fraction": TEST_FRACTION, "n_splits": N_SPLITS}
        assumptions = ["No time or group column was found, so rows are treated as exchangeable."]
        if group_column == "none" and groups:
            split["override_reason"] = "group split declined by the user (--group-column none)"
            assumptions = [f"Rows of the same {groups[0]} are treated as independent because "
                           "the user declined the group split."]
    dropped = {e["column"] for e in excluded} | {prof["target"]}
    features = [c for c in prof["columns"] if c not in dropped]
    plan = {
        "dataset": {"path": Path(os.path.relpath(csv_path, out_dir)).as_posix(), "sha256": prof["sha256"], "rows": prof["rows"]},
        "goal": goal,
        "target": prof["target"],
        "task": task,
        "excluded_columns": excluded,
        "kept_columns": list(keep),
        "features": {"numeric": [c for c in features if c in prof["numeric"]],
                     "categorical": [c for c in features if c not in prof["numeric"]]},
        "split": split,
        "models": TASKS[task]["models"],
        "metrics": TASKS[task]["metrics"],
        "seed": seed,
        "assumptions": assumptions,
        "limitations": LIMITATIONS,
    }
    if task == "binary":
        plan["positive_label"] = prof["positive_label"]
    return plan


def validate(plan: dict) -> None:
    split = plan["split"]
    n_splits, seed, fraction = split.get("n_splits"), plan.get("seed"), split.get("test_fraction")
    if not isinstance(n_splits, int) or isinstance(n_splits, bool) or n_splits < 2:
        raise PlanError(f"split.n_splits must be an int >= 2, got {n_splits!r}")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise PlanError(f"seed must be an int, got {seed!r}")
    if isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or not 0 < fraction < 1:
        raise PlanError(f"split.test_fraction must be a number strictly between 0 and 1, got {fraction!r}")
    texts = {"target": plan.get("target"), "dataset.path": plan["dataset"].get("path")}
    if split.get("column") is not None:
        texts["split.column"] = split["column"]
    for field, value in texts.items():
        if not isinstance(value, str):
            raise PlanError(f"{field} must be a string, got {value!r}")
    for kind in ("numeric", "categorical"):
        columns = plan["features"].get(kind)
        if not isinstance(columns, list) or not all(isinstance(c, str) for c in columns):
            raise PlanError(f"features.{kind} must be a list of strings, got {columns!r}")
    if plan.get("task") not in TASKS:
        raise PlanError(f"task must be one of {list(TASKS)}, got {plan.get('task')!r}")
    if plan["task"] == "binary" and not isinstance(plan.get("positive_label"), (str, int, float, bool)):
        raise PlanError(f"positive_label must be a string or number, got {plan.get('positive_label')!r}")
    if not isinstance(plan.get("kept_columns", []), list):
        raise PlanError(f"kept_columns must be a list, got {plan.get('kept_columns')!r}")


def contradictions(plan: dict, prof: dict) -> list[str]:
    validate(plan)
    split = plan["split"]
    if split.get("kind") not in SPLIT_KINDS:
        raise PlanError(f"split.kind must be one of {list(SPLIT_KINDS)}, got {split.get('kind')!r}")
    fields = []
    if plan["task"] != prof["task"]:
        fields.append("task")
    times, groups = time_column_names(prof), group_column_names(prof)
    if not split.get("override_reason"):
        if split["kind"] == "temporal_holdout" and split.get("column") not in times:
            fields.append("split.column")
        elif split["kind"] == "group_kfold" and split.get("column") not in groups:
            fields.append("split.column")
        elif split["kind"] != "temporal_holdout" and times:
            fields.append("split.kind")
        elif split["kind"] not in ("temporal_holdout", "group_kfold") and len(groups) == 1:
            fields.append("split.kind")
    banned = {plan["target"], split.get("column")} | {e["column"] for e in plan["excluded_columns"]}
    features = plan["features"]["numeric"] + plan["features"]["categorical"]
    if any(c not in prof["columns"] or c in banned for c in features):
        fields.append("features")
    return fields


def task_reason(prof: dict) -> str:
    if prof["task"] == "binary":
        return "2 target values"
    if prof["task"] == "multiclass":
        return f"{len(prof['target_values'])} classes"
    return f"numeric target with {prof['target_distinct']} distinct values"


def split_sentence(plan: dict, prof: dict) -> str:
    split = plan["split"]
    share, n = f"{split['test_fraction']:.0%}", split["n_splits"]
    if split["kind"] == "temporal_holdout":
        fact = next(t for t in prof["time_columns"] if t["column"] == split["column"])
        return (f"Split: temporal_holdout on {split['column']}, because it parses as dates from {fact['min']} to "
                f"{fact['max']} with {fact['periods']} distinct periods. The last {share} of periods are the test "
                f"set. CV runs walk-forward over the training periods in {n} folds.")
    if split["kind"] == "group_kfold":
        fact = next(g for g in prof["group_columns"] if g["column"] == split["column"])
        return (f"Split: group_kfold on {split['column']}, because it has {fact['groups']} distinct values with up "
                f"to {fact['max_size']} rows each. A holdout of {share} of the groups and {n}-fold GroupKFold CV "
                f"keep every group on one side.")
    if split["kind"] == "stratified_kfold":
        return (f"Split: stratified holdout of {share} and {n}-fold stratified CV, because no time or group "
                f"column was found.")
    return f"Split: random holdout of {share} and {n}-fold CV, because no time or group column was found."


def design_md(plan: dict, prof: dict) -> str:
    lines = [f"# Design: {plan['target']}", "", f"Goal: {plan['goal'] or '(none given)'}", "",
             f"Task: {plan['task']} ({task_reason(prof)}).", "", split_sentence(plan, prof), ""]
    if plan["task"] == "binary":
        lines.append(f"Positive class: {plan['positive_label']!r} ({prof['positive_rate']:.1%} of labelled rows).")
    if plan["task"] != "regression":
        share = prof["minority_share"]
        if share < IMBALANCE_SHARE:
            lines.append(f"Classes are imbalanced: the smallest class is {share:.1%} of labelled rows, so "
                         "accuracy is not among the metrics.")
        else:
            lines.append(f"Classes are not imbalanced (smallest class {share:.1%}); accuracy is still not reported.")
    lines += [f"Models: {', '.join(plan['models'])}. Both are reported; neither is chosen by its test score.",
              f"Metrics: {', '.join(plan['metrics'])}.", "", "Excluded columns:"]
    lines += [f"- {e['column']}: {e['reason']}" for e in plan["excluded_columns"]] or ["- none"]
    suspects = {s["column"]: s["reason"] for s in prof["suspects"]}
    if plan.get("kept_columns"):
        lines += ["", "Columns kept by the user (--keep) although the profile flagged them:"]
        lines += [f"- {c}: {suspects.get(c, '')}" for c in plan["kept_columns"]]
    lines += ["", "Assumptions:"] + [f"- {a}" for a in plan["assumptions"]]
    lines += ["", "Limitations:"] + [f"- {x}" for x in plan["limitations"]]
    return "\n".join(lines) + "\n"


def write_plan(plan: dict, path: Path) -> None:
    Path(path).write_text(yaml.safe_dump(plan, sort_keys=False, allow_unicode=True), encoding="utf-8")


def read_plan(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
