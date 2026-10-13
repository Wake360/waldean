from __future__ import annotations

import nbformat

from ..core.notebook import normalize

IMPORTS = """import json

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import (average_precision_score, balanced_accuracy_score, f1_score, log_loss,
                             mean_absolute_error, mean_squared_error, r2_score, roc_auc_score)
from sklearn.model_selection import (GroupKFold, GroupShuffleSplit, KFold, StratifiedKFold, TimeSeriesSplit,
                                     train_test_split)
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder"""

SCORES = {
    "binary": """def scores(y_true, model, X_part):
    p = model.predict_proba(X_part)[:, 1]
    return {
        "roc_auc": float(roc_auc_score(y_true, p)),
        "average_precision": float(average_precision_score(y_true, p)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, p >= 0.5)),
    }""",
    "multiclass": """def scores(y_true, model, X_part):
    p = model.predict_proba(X_part)
    pred = model.classes_[p.argmax(axis=1)]
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "macro_f1": float(f1_score(y_true, pred, average="macro")),
        "log_loss": float(log_loss(y_true, p, labels=model.classes_)),
    }""",
    "regression": """def scores(y_true, model, X_part):
    pred = model.predict(X_part)
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_true, pred))),
        "mae": float(mean_absolute_error(y_true, pred)),
        "r2": float(r2_score(y_true, pred)),
    }""",
}

CLASS_GUARD = """usable = [(a, b) for a, b in folds if y.iloc[a].nunique() == y.nunique() and y.iloc[b].nunique() >= 2]
if y[test].nunique() < 2:
    raise ValueError("the test rows hold one class; the metrics are undefined")
if y[train].nunique() < y.nunique():
    raise ValueError("the training rows miss a class")"""

REGRESSION_GUARD = "usable = list(folds)"

LOOP = """results = {"cv": {}, "holdout": {}, "skipped_folds": len(folds) - len(usable)}
for name, model in models.items():
    results["cv"][name] = []
    for a, b in usable:
        model.fit(X.iloc[a], y.iloc[a])
        results["cv"][name].append(scores(y.iloc[b], model, X.iloc[b]))
    model.fit(X[train], y[train])
    results["holdout"][name] = scores(y[test], model, X[test])
print("WALDEAN_METRICS " + json.dumps(results, sort_keys=True))
pd.DataFrame(results["holdout"]).T"""

ESTIMATORS = {
    "binary": ("DummyClassifier(strategy=\"prior\")", "HistGradientBoostingClassifier(early_stopping=False, random_state=SEED)"),
    "multiclass": ("DummyClassifier(strategy=\"prior\")", "HistGradientBoostingClassifier(early_stopping=False, random_state=SEED)"),
    "regression": ("DummyRegressor(strategy=\"mean\")", "HistGradientBoostingRegressor(early_stopping=False, random_state=SEED)"),
}

HOW = {
    "temporal_holdout": "trains on earlier values of `{column}` than it tests on",
    "group_kfold": "keeps every `{column}` on one side of the split",
    "stratified_kfold": "uses a stratified split, because the plan has no time or group column",
    "kfold": "uses a random split, because the plan has no time or group column",
}


def evaluate_cell(task: str) -> str:
    guard = REGRESSION_GUARD if task == "regression" else CLASS_GUARD
    return SCORES[task] + "\n\n\n" + guard + "\n" + LOOP


def code(source: str, field: str):
    cell = nbformat.v4.new_code_cell(source)
    cell.metadata["waldean"] = {"plan_field": field}
    return cell


def target_line(plan: dict) -> str:
    t = plan["target"]
    if plan["task"] == "binary":
        return f"y = (df[{t!r}] == {plan['positive_label']!r}).astype(int)"
    if plan["task"] == "multiclass":
        return f"y = df[{t!r}].astype(str)"
    return f"y = df[{t!r}].astype(float)"


def load_cell(plan: dict) -> str:
    feats = plan["features"]["numeric"] + plan["features"]["categorical"]
    return (f"df = pd.read_csv({plan['dataset']['path']!r})\n"
            f"df = df[df[{plan['target']!r}].notna()].reset_index(drop=True)\n"
            f"{target_line(plan)}\n"
            f"features = {feats!r}\n"
            f"X = df[features]")


def model_cell(plan: dict) -> str:
    baseline, candidate = ESTIMATORS[plan["task"]]
    return (f"SEED = {plan['seed']}\n"
            f"numeric = {plan['features']['numeric']!r}\n"
            f"categorical = {plan['features']['categorical']!r}\n"
            "prep = ColumnTransformer([\n"
            "    (\"num\", SimpleImputer(strategy=\"median\"), numeric),\n"
            "    (\"cat\", make_pipeline(SimpleImputer(strategy=\"most_frequent\"),\n"
            "                          OneHotEncoder(handle_unknown=\"infrequent_if_exist\", max_categories=20,\n"
            "                                        sparse_output=False)), categorical),\n"
            "])\n"
            "models = {\n"
            f"    \"baseline\": Pipeline([(\"prep\", clone(prep)), (\"model\", {baseline})]),\n"
            f"    \"candidate\": Pipeline([(\"prep\", clone(prep)), (\"model\", {candidate})]),\n"
            "}")


def split_cells(plan: dict) -> list[str]:
    s = plan["split"]
    if s["kind"] == "temporal_holdout":
        return [
            f"t = pd.to_datetime(df[{s['column']!r}], errors=\"coerce\", format=\"mixed\")\n"
            "periods = np.sort(t.dropna().unique())\n"
            f"cutoff = periods[int(len(periods) * {1 - s['test_fraction']!r})]\n"
            "train = (t < cutoff).to_numpy()\n"
            "test = (t >= cutoff).to_numpy()\n"
            "print(f\"train {t[train].min()} to {t[train].max()}, test {t[test].min()} to {t[test].max()}\")\n"
            "print(f\"undated rows left out: {int(t.isna().sum())}\")",
            "train_periods = np.sort(t[train].unique())\n"
            f"cv = TimeSeriesSplit(n_splits={s['n_splits']})\n"
            "folds = [(np.flatnonzero(t.isin(train_periods[a]).to_numpy()),\n"
            "          np.flatnonzero(t.isin(train_periods[b]).to_numpy()))\n"
            "         for a, b in cv.split(train_periods)]",
        ]
    if s["kind"] == "group_kfold":
        return [
            f"known = df[{s['column']!r}].notna().to_numpy()\n"
            f"groups = df[{s['column']!r}].astype(str).to_numpy()\n"
            "rows = np.flatnonzero(known)\n"
            f"splitter = GroupShuffleSplit(n_splits=1, test_size={s['test_fraction']!r}, random_state={plan['seed']})\n"
            "train_rows, _ = next(splitter.split(rows, groups=groups[rows]))\n"
            "train = np.isin(np.arange(len(df)), rows[train_rows])\n"
            "test = known & ~train\n"
            "print(f\"train groups {len(set(groups[train]))}, test groups {len(set(groups[test]))}\")\n"
            "print(f\"rows without a group left out: {int((~known).sum())}\")",
            "inside = np.flatnonzero(train)\n"
            f"cv = GroupKFold(n_splits={s['n_splits']})\n"
            "folds = [(inside[a], inside[b]) for a, b in cv.split(inside, groups=groups[inside])]",
        ]
    if s["kind"] == "kfold":
        return [
            "rows = np.arange(len(df))\n"
            f"train_rows, _ = train_test_split(rows, test_size={s['test_fraction']!r}, random_state={plan['seed']})\n"
            "train = np.isin(rows, train_rows)\n"
            "test = ~train",
            "inside = np.flatnonzero(train)\n"
            f"cv = KFold(n_splits={s['n_splits']}, shuffle=True, random_state={plan['seed']})\n"
            "folds = [(inside[a], inside[b]) for a, b in cv.split(inside)]",
        ]
    return [
        "rows = np.arange(len(df))\n"
        f"train_rows, _ = train_test_split(rows, test_size={s['test_fraction']!r}, stratify=y, "
        f"random_state={plan['seed']})\n"
        "train = np.isin(rows, train_rows)\n"
        "test = ~train",
        "inside = np.flatnonzero(train)\n"
        f"cv = StratifiedKFold(n_splits={s['n_splits']}, shuffle=True, random_state={plan['seed']})\n"
        "folds = [(inside[a], inside[b]) for a, b in cv.split(inside, y.iloc[inside])]",
    ]


def render(plan: dict):
    s = plan["split"]
    how = HOW[s["kind"]].format(column=s.get("column"))
    split_a, split_b = split_cells(plan)
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nb.metadata["waldean"] = {"generator": "waldean create", "task": plan["task"], "split_kind": s["kind"],
                              "date_col": s.get("column") if s["kind"] == "temporal_holdout" else None}
    nb.cells = [
        nbformat.v4.new_markdown_cell(f"# Can we predict `{plan['target']}`?\n\n{plan['goal']}\n\n"
                                      f"Generated from `plan.yaml`. Every reported score {how}. "
                                      "See `design.md` for the reasons."),
        code(IMPORTS, "models"),
        code(load_cell(plan), "features"),
        code(model_cell(plan), "models"),
        code(split_a, "split"),
        code(split_b, "split"),
        code(evaluate_cell(plan["task"]), "metrics"),
        nbformat.v4.new_markdown_cell("Both models are scored once on the test rows. Neither is chosen by "
                                      "that score. The CV scores come from the training rows only."),
    ]
    return normalize(nb, "experiment")
