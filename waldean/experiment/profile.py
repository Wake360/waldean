from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

MIN_PERIODS = 10
MIN_YEAR = 1900
MAX_YEAR = 2100
PARSE_SHARE = 0.95
NUMBER_RE = r"-?\d+(?:\.\d+)?"
YEAR_FIRST_RE = r"\d{4}\D"
MAX_CLASSES = 20
TASKS = ("binary", "multiclass", "regression")


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
        stats = y.describe()
        return {"target_stats": {k: round(float(stats[k]), 4) for k in ("mean", "std", "min", "max")}}
    counts = y.value_counts()
    values = sorted(counts.index.tolist())
    if task == "binary" and len(values) != 2:
        raise ValueError(f"target needs exactly 2 values for a binary task, found {len(values)}")
    if len(values) > MAX_CLASSES:
        raise ValueError(f"target has {len(values)} classes; at most {MAX_CLASSES} classes are supported")
    info = {"target_values": values,
            "class_counts": {str(v): int(counts[v]) for v in values},
            "minority_share": round(float(counts.min() / counts.sum()), 4)}
    if task == "binary":
        info |= {"positive_label": values[1], "positive_rate": round(float((y == values[1]).mean()), 4)}
    return info


def profile(csv_path: str | Path, target: str, task: str | None = None) -> dict:
    path = Path(csv_path)
    df = pd.read_csv(path)
    if target not in df.columns:
        raise ValueError(f"target column {target!r} not in {path.name}")
    task = task or infer_task(df[target])
    if task not in TASKS:
        raise ValueError(f"task must be one of {list(TASKS)}, got {task!r}")
    labelled = df[df[target].notna()]
    return {
        "rows": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "numeric": [str(c) for c in df.columns if c != target and pd.api.types.is_numeric_dtype(df[c])],
        "target": target,
        "task": task,
        "target_distinct": int(labelled[target].nunique()),
        **target_info(labelled[target], task),
        "time_columns": time_columns(df, target),
        "sha256": sha256(path),
    }
