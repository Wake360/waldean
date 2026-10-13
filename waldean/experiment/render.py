from __future__ import annotations

import nbformat

from ..core.notebook import normalize

IMPORTS = """import json

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, TimeSeriesSplit, train_test_split
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder"""

EVALUATE = """def scores(y_true, p):
    return {
        "roc_auc": float(roc_auc_score(y_true, p)),
        "average_precision": float(average_precision_score(y_true, p)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, p >= 0.5)),
    }


results = {"cv": {}, "holdout": {}, "skipped_folds": 0}
usable = [(a, b) for a, b in folds if y.iloc[a].nunique() == 2 and y.iloc[b].nunique() == 2]
results["skipped_folds"] = len(folds) - len(usable)
if y[test].nunique() < 2:
    raise ValueError("the test periods hold one class; roc_auc is undefined")
for name, model in models.items():
    results["cv"][name] = []
    for a, b in usable:
        model.fit(X.iloc[a], y.iloc[a])
        results["cv"][name].append(scores(y.iloc[b], model.predict_proba(X.iloc[b])[:, 1]))
    model.fit(X[train], y[train])
    results["holdout"][name] = scores(y[test], model.predict_proba(X[test])[:, 1])
print("WALDEAN_METRICS " + json.dumps(results, sort_keys=True))
pd.DataFrame(results["holdout"]).T"""


def code(source: str, field: str):
    cell = nbformat.v4.new_code_cell(source)
    cell.metadata["waldean"] = {"plan_field": field}
    return cell


def load_cell(plan: dict) -> str:
    feats = plan["features"]["numeric"] + plan["features"]["categorical"]
    return (f"df = pd.read_csv({plan['dataset']['path']!r})\n"
            f"df = df[df[{plan['target']!r}].notna()].reset_index(drop=True)\n"
            f"y = (df[{plan['target']!r}] == {plan['positive_label']!r}).astype(int)\n"
            f"features = {feats!r}\n"
            f"X = df[features]")


def model_cell(plan: dict) -> str:
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
            "    \"baseline\": Pipeline([(\"prep\", clone(prep)), (\"model\", DummyClassifier(strategy=\"prior\"))]),\n"
            "    \"candidate\": Pipeline([(\"prep\", clone(prep)),\n"
            "                           (\"model\", HistGradientBoostingClassifier(early_stopping=False,\n"
            "                                                                    random_state=SEED))]),\n"
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
    how = (f"trains on earlier values of `{s['column']}` than it tests on" if s["kind"] == "temporal_holdout"
           else "uses a stratified split, because the plan has no time column")
    split_a, split_b = split_cells(plan)
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nb.metadata["waldean"] = {"generator": "waldean create", "split_kind": s["kind"], "date_col": s.get("column")}
    nb.cells = [
        nbformat.v4.new_markdown_cell(f"# Can we predict `{plan['target']}`?\n\n{plan['goal']}\n\n"
                                      f"Generated from `plan.yaml`. Every reported score {how}. "
                                      "See `design.md` for the reasons."),
        code(IMPORTS, "models"),
        code(load_cell(plan), "features"),
        code(model_cell(plan), "models"),
        code(split_a, "split"),
        code(split_b, "split"),
        code(EVALUATE, "metrics"),
        nbformat.v4.new_markdown_cell("Both models are scored once on the test rows. Neither is chosen by "
                                      "that score. The CV scores come from the training rows only."),
    ]
    return normalize(nb, "experiment")
