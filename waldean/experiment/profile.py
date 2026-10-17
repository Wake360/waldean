from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import cast

import pandas as pd

MIN_PERIODS = 10
MIN_YEAR = 1900
MAX_YEAR = 2100
PARSE_SHARE = 0.95
NUMBER_RE = r"-?\d+(?:\.\d+)?"
YEAR_FIRST_RE = r"\d{4}\D"
MAX_CLASSES = 20
TASKS = ("binary", "multiclass", "regression")
HIGH_CARDINALITY_SHARE = 0.5
LEAK_CORRELATION = 0.95
MAX_PURITY_LEVELS = 50
MIN_GROUPS = 20
ID_NAME_RE = re.compile(r"(?i:(^|_)(id|key|code)($|_))|[a-z]Id$|ID$")


def column(df: pd.DataFrame, col: str) -> pd.Series:
    return cast(pd.Series, df[col])


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_dates(values, dayfirst: bool):
    parsed = pd.to_datetime(values, errors="coerce", format="mixed", dayfirst=dayfirst)
    return parsed.where(parsed.dt.year.between(MIN_YEAR, MAX_YEAR))


def time_columns(df: pd.DataFrame, target: str) -> list[dict]:
    found = []
    for col in df.columns:
        if col == target or not pd.api.types.is_string_dtype(df[col]):
            continue
        values = df[col].dropna().astype(str)
        if values.empty or values.str.fullmatch(NUMBER_RE).mean() >= 0.5:
            continue
        parsed = parse_dates(values, dayfirst=False)
        if parsed.notna().mean() < PARSE_SHARE or parsed.nunique() < MIN_PERIODS:
            continue
        flipped = parse_dates(values, dayfirst=True)
        compared = parsed.notna() & ~values.str.match(YEAR_FIRST_RE)
        ambiguous = flipped.notna().mean() >= PARSE_SHARE and bool((parsed != flipped)[compared].any())
        found.append({"column": str(col), "min": str(parsed.min()), "max": str(parsed.max()),
                      "periods": int(parsed.nunique()), "ambiguous": ambiguous})
    return found


def infer_task(series: pd.Series) -> str:
    values = series.dropna()
    n = values.nunique()
    if n < 2:
        raise ValueError(f"target needs at least 2 distinct values, found {n}")
    if n == 2:
        return "binary"
    numeric = pd.api.types.is_numeric_dtype(values)
    if numeric and pd.api.types.is_float_dtype(values) and not (values == values.round()).all():
        return "regression"
    if n <= MAX_CLASSES:
        return "multiclass"
    if numeric:
        return "regression"
    raise ValueError(f"target has {n} distinct text values; at most {MAX_CLASSES} classes are supported")


def target_info(y: pd.Series, task: str) -> dict:
    if task == "regression":
        if not pd.api.types.is_numeric_dtype(y):
            raise ValueError("regression needs a numeric target")
        return {"target_stats": {k: round(float(getattr(y, k)()), 4) for k in ("mean", "std", "min", "max")}}
    counts = {k: int(v) for k, v in y.value_counts().items()}
    values = sorted(counts, key=lambda k: (str(type(k)), k))
    if task == "binary" and len(values) != 2:
        raise ValueError(f"target needs exactly 2 values for a binary task, found {len(values)}")
    if len(values) > MAX_CLASSES:
        raise ValueError(f"target has {len(values)} classes; at most {MAX_CLASSES} classes are supported")
    info = {"target_values": values,
            "class_counts": {str(v): counts[v] for v in values},
            "minority_share": round(min(counts.values()) / sum(counts.values()), 4)}
    if task == "binary":
        info |= {"positive_label": values[1], "positive_rate": round(float((y == values[1]).mean()), 4)}
    return info


def integral(values: pd.Series) -> bool:
    return pd.api.types.is_float_dtype(values) and bool((values == values.round()).all())


def leak_reason(df: pd.DataFrame, col: str, target: str, task: str) -> str | None:
    labelled = df.loc[column(df, target).notna() & column(df, col).notna()]
    if len(labelled) < 2:
        return None
    x, y = column(labelled, col), column(labelled, target)
    if pd.api.types.is_numeric_dtype(x) and task != "multiclass":
        if task == "binary":
            y = (y == sorted(y.unique().tolist())[1]).astype(int)
        rho = float(x.corr(y, method="spearman"))
        if pd.notna(rho) and abs(rho) >= LEAK_CORRELATION:
            return f"spearman correlation {abs(rho):.2f} with the target"
        return None
    if task != "regression":
        levels = x.nunique()
        if 2 <= levels <= MAX_PURITY_LEVELS and labelled.groupby(col)[target].nunique().max() == 1:
            return "every value maps to one target class"
    return None


def suspect_columns(df: pd.DataFrame, target: str, task: str, skip: set[str]) -> list[dict]:
    found = []
    for col in df.columns:
        if col == target or col in skip:
            continue
        values = column(df, col).dropna()
        n, rows = values.nunique(), len(values)
        if n <= 1:
            found.append({"column": str(col), "kind": "constant", "reason": "constant: one value in every row"})
        elif n == rows and (not pd.api.types.is_float_dtype(values) or integral(values)):
            found.append({"column": str(col), "kind": "id",
                          "reason": "looks like an identifier: a different value in every row"})
        elif not pd.api.types.is_numeric_dtype(values) and n >= HIGH_CARDINALITY_SHARE * rows:
            found.append({"column": str(col), "kind": "high_cardinality",
                          "reason": f"{n} distinct values in {rows} rows; one-hot encoding would keep almost none"})
        elif (reason := leak_reason(df, col, target, task)) is not None:
            found.append({"column": str(col), "kind": "target_leak", "reason": reason})
    return found


def group_columns(df: pd.DataFrame, target: str, skip: set[str]) -> list[dict]:
    found = []
    for col in df.columns:
        if col == target or col in skip:
            continue
        values = column(df, col).dropna()
        if pd.api.types.is_bool_dtype(values) or (pd.api.types.is_float_dtype(values) and not integral(values)):
            continue
        if pd.api.types.is_numeric_dtype(values) and not ID_NAME_RE.search(str(col)):
            continue
        n = values.nunique()
        if n < MIN_GROUPS or n > len(values) / 2:
            continue
        found.append({"column": str(col), "groups": int(n), "max_size": int(values.value_counts().max())})
    return found


def profile(csv_path: str | Path, target: str, task: str | None = None) -> dict:
    path = Path(csv_path)
    df = pd.read_csv(path)
    if target not in df.columns:
        raise ValueError(f"target column {target!r} not in {path.name}")
    task = task or infer_task(column(df, target))
    if task not in TASKS:
        raise ValueError(f"task must be one of {list(TASKS)}, got {task!r}")
    labelled = df.loc[column(df, target).notna()]
    y = column(labelled, target)
    info = target_info(y, task)
    times = time_columns(df, target)
    suspects = suspect_columns(df, target, task, {t["column"] for t in times})
    return {
        "rows": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "numeric": [str(c) for c in df.columns if c != target and pd.api.types.is_numeric_dtype(df[c])],
        "target": target,
        "task": task,
        "target_distinct": int(y.nunique()),
        **info,
        "time_columns": times,
        "suspects": suspects,
        "group_columns": group_columns(df, target, {t["column"] for t in times} | {s["column"] for s in suspects}),
        "sha256": sha256(path),
    }
