from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ..analysis.dataflow import analyze
from ..analysis.ingest import parse_notebook
from ..checks.detect import run_static
from ..core.flag import DEFAULT_CONFIDENCE_FLOOR
from .plan import N_SPLITS, TEST_FRACTION, PlanError, choose_time_column
from .profile import parse_dates, profile, sha256

ID_RE = re.compile(r"\b(identifier|key|id)\b", re.IGNORECASE)
REPEAT_RATIO = 1.5
SELECTION_METRIC = "roc_auc"
EVIDENCE_FIELDS = ("features", "candidates", "cv_folds", "cv_scores", "chosen", "holdout_rows", "holdout_scores")
RULES = [
    "Use only rows not listed in holdout.csv or unused.csv for fitting, cross-validation and every choice.",
    "Cross-validate as the cv section says, inside the training rows.",
    "Fit every preprocessing step inside the cross-validation folds.",
    "Name all candidate models, including a trivial baseline, before scoring any of them.",
    "Choose the candidate with the highest mean CV roc_auc. Choose features, hyperparameters and thresholds on CV too.",
    "Refit the chosen candidate on all training rows and score it once on the holdout rows. That score is the headline.",
    "Use only features known at prediction time. Read columns.csv for when each column is recorded.",
    "Write evidence.json with the fields listed under evidence. Row labels are 0-based row positions in data.csv.",
]
LIMITATIONS = [
    "Columns recorded after the outcome are not detected. The rule on prediction time leaves that judgement to you.",
    "Binary classification only.",
]


def read_dictionary(columns_path) -> dict[str, str]:
    cols = pd.read_csv(columns_path)
    return dict(zip(cols["column"].astype(str), cols["description"].fillna("").astype(str)))


def id_columns(df: pd.DataFrame, dictionary: dict[str, str], target: str) -> tuple[list[str], list[str]]:
    ids = [str(c) for c in df.columns if c != target and ID_RE.search(dictionary.get(str(c), ""))]
    repeated = [c for c in ids if len(df) / max(df[c].nunique(), 1) >= REPEAT_RATIO]
    return repeated, [c for c in ids if c not in repeated]


def holdout_mask(df: pd.DataFrame, kind: str, column: str | None, usable: np.ndarray, seed: int) -> np.ndarray:
    if kind == "temporal_holdout":
        t = parse_dates(df[column].astype(str), dayfirst=False)
        periods = np.sort(pd.unique(t[usable]))
        if len(periods) < 2:
            raise PlanError(f"{column!r} has fewer than 2 usable periods: a temporal holdout needs earlier rows to train on")
        cutoff = periods[len(periods) - math.ceil(TEST_FRACTION * len(periods))]
        return (t >= cutoff).to_numpy() & usable
    rng = np.random.default_rng(seed)
    if kind == "group_holdout":
        keys = df[column].astype(str)
        groups = np.unique(np.asarray(keys)[usable].astype(str))
        chosen = list(rng.permutation(groups)[: math.ceil(TEST_FRACTION * len(groups))])
        return keys.isin(chosen).to_numpy() & usable
    rows = np.flatnonzero(usable)
    mask = np.zeros(len(df), dtype=bool)
    mask[rng.permutation(rows)[: math.ceil(TEST_FRACTION * len(rows))]] = True
    return mask


def create_protocol(csv_path, columns_path, target: str, out_dir, question: str = "",
                    time_column: str | None = None, seed: int = 0) -> Path:
    csv, out = Path(csv_path).resolve(), Path(out_dir).resolve()
    prof = profile(csv, target)
    df = pd.read_csv(csv)
    repeated, unique = id_columns(df, read_dictionary(columns_path), target)
    if len(repeated) > 1:
        raise PlanError(f"several repeated identifier columns {repeated}: the protocol needs one entity column")
    time_col = choose_time_column(prof, time_column)
    if time_col is not None and next(t for t in prof["time_columns"] if t["column"] == time_col)["ambiguous"]:
        raise PlanError(f"dates in {time_col!r} read differently day-first and month-first; rewrite them as YYYY-MM-DD")
    group_col = repeated[0] if repeated else None
    usable = df[target].notna().to_numpy().copy()
    if time_col is not None:
        kind, cv_kind, column = "temporal_holdout", "walk_forward", time_col
        usable &= parse_dates(df[time_col].astype(str), dayfirst=False).notna().to_numpy()
    elif group_col is not None:
        kind, cv_kind, column = "group_holdout", "group_kfold", group_col
    else:
        kind, cv_kind, column = "random_holdout", "stratified_kfold", None
    holdout = holdout_mask(df, kind, column, usable, seed)
    excluded = [{"column": c, "reason": "identifier, one value per row"} for c in unique]
    if group_col is not None:
        excluded.append({"column": group_col, "reason": "entity key, repeated across rows; not a feature"})
    if time_col is not None:
        excluded.append({"column": time_col, "reason": "time column, used for the split only"})
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"row": np.flatnonzero(holdout)}).to_csv(out / "holdout.csv", index=False)
    unused_file = None
    if not usable.all():
        unused_file = "unused.csv"
        pd.DataFrame({"row": np.flatnonzero(~usable)}).to_csv(out / unused_file, index=False)
    protocol = {
        "protocol": 1,
        "question": question,
        "dataset": {"path": os.path.relpath(csv, out), "sha256": prof["sha256"], "rows": prof["rows"]},
        "target": target,
        "positive_label": prof["positive_label"],
        "excluded_columns": excluded,
        "split": {"kind": kind, "column": column, "holdout_file": "holdout.csv",
                  "holdout_rows": int(holdout.sum()), "holdout_sha256": sha256(out / "holdout.csv"),
                  "unused_file": unused_file},
        "cv": {"kind": cv_kind, "column": column, "n_splits": N_SPLITS,
               "rows": "training rows only: not in holdout.csv or unused.csv"},
        "selection": {"metric": SELECTION_METRIC,
                      "rule": "choose the candidate with the highest mean CV roc_auc; nothing is chosen on holdout rows"},
        "headline": "roc_auc of the chosen candidate, refitted on all training rows, scored once on the holdout rows",
        "evidence": {"file": "evidence.json", "fields": list(EVIDENCE_FIELDS),
                     "row_labels": "0-based row positions in data.csv"},
        "rules": RULES,
        "limitations": LIMITATIONS,
    }
    (out / "protocol.yaml").write_text(yaml.safe_dump(protocol, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return out


def fold_problems(i: int, train: list, test: list, n_rows: int, blocked: set, split: dict, key) -> list[str]:
    rows = list(train) + list(test)
    if not train or not test:
        return [f"CV fold {i} has an empty train or test side"]
    if not all(isinstance(r, int) and 0 <= r < n_rows for r in rows):
        return [f"CV fold {i} has row labels outside data.csv"]
    problems = []
    if set(rows) & blocked:
        problems.append(f"CV fold {i} uses holdout or unused rows")
    if set(train) & set(test):
        problems.append(f"CV fold {i} has rows in both train and test")
    if split["kind"] == "temporal_holdout" and not key.iloc[train].max() < key.iloc[test].min():
        problems.append(f"CV fold {i} trains on rows not earlier than its test rows")
    if split["kind"] == "group_holdout" and set(key.iloc[train]) & set(key.iloc[test]):
        problems.append(f"CV fold {i} shares {split['column']} values between train and test")
    return problems


def check_protocol(protocol_path, notebook_path) -> list[str]:
    proto_path, nb_path = Path(protocol_path).resolve(), Path(notebook_path).resolve()
    base = proto_path.parent
    proto = yaml.safe_load(proto_path.read_text(encoding="utf-8"))
    split = proto["split"]
    csv = base / proto["dataset"]["path"]
    if sha256(csv) != proto["dataset"]["sha256"]:
        raise PlanError(f"{csv.name} changed since the protocol was written")
    if sha256(base / split["holdout_file"]) != split["holdout_sha256"]:
        raise PlanError(f"{split['holdout_file']} changed since the protocol was written")
    parsed = parse_notebook(nb_path)
    problems = [f"waldean check: {f.flaw_id} in cell {f.cell}" for f in run_static(parsed, analyze(parsed))
                if f.confidence >= DEFAULT_CONFIDENCE_FLOOR]
    ev_path = nb_path.parent / proto["evidence"]["file"]
    if not ev_path.exists():
        return problems + [f"{ev_path.name} missing: the notebook must write it"]
    ev = json.loads(ev_path.read_text(encoding="utf-8"))
    missing = [k for k in EVIDENCE_FIELDS if k not in ev]
    if missing:
        return problems + [f"{ev_path.name} lacks {missing}"]
    df = pd.read_csv(csv)
    holdout = set(pd.read_csv(base / split["holdout_file"])["row"].tolist())
    unused = set(pd.read_csv(base / split["unused_file"])["row"].tolist()) if split["unused_file"] else set()
    if set(ev["holdout_rows"]) != holdout:
        problems.append("holdout_rows differ from holdout.csv")
    banned = sorted(set(ev["features"]) & ({proto["target"]} | {e["column"] for e in proto["excluded_columns"]}))
    if banned:
        problems.append(f"features include excluded columns {banned}")
    if len(ev["cv_folds"]) < 2:
        problems.append("fewer than 2 CV folds")
    key = None
    if split["kind"] == "temporal_holdout":
        key = parse_dates(df[split["column"]].astype(str), dayfirst=False)
    elif split["kind"] == "group_holdout":
        key = df[split["column"]].astype(str)
    for i, (train, test) in enumerate(ev["cv_folds"]):
        problems += fold_problems(i, train, test, len(df), holdout | unused, split, key)
    scores = ev["cv_scores"]
    if set(scores) != set(ev["candidates"]):
        problems.append("cv_scores must have one entry per candidate")
    elif ev["chosen"] not in scores:
        problems.append(f"chosen {ev['chosen']!r} is not a candidate")
    elif np.mean(scores[ev["chosen"]]) < max(np.mean(v) for v in scores.values()):
        problems.append(f"chosen {ev['chosen']!r} is not the candidate with the highest mean CV {SELECTION_METRIC}")
    if ev["chosen"] not in ev["holdout_scores"]:
        problems.append("holdout_scores lacks the chosen candidate")
    return problems
