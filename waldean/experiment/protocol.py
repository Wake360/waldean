from __future__ import annotations

import math
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

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
