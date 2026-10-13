from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

MIN_PERIODS = 10
PARSE_SHARE = 0.95
NUMBER_RE = r"-?\d+(?:\.\d+)?"


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def time_columns(df: pd.DataFrame, target: str) -> list[dict]:
    found = []
    for col in df.columns:
        if col == target or not pd.api.types.is_string_dtype(df[col]):
            continue
        values = df[col].dropna().astype(str)
        if values.empty or values.str.fullmatch(NUMBER_RE).mean() >= 0.5:
            continue
        parsed = pd.to_datetime(values, errors="coerce", format="mixed")
        if parsed.notna().mean() < PARSE_SHARE or parsed.nunique() < MIN_PERIODS:
            continue
        found.append({"column": str(col), "min": str(parsed.min()), "max": str(parsed.max()),
                      "periods": int(parsed.nunique())})
    return found


def profile(csv_path: str | Path, target: str) -> dict:
    path = Path(csv_path)
    df = pd.read_csv(path)
    if target not in df.columns:
        raise ValueError(f"target column {target!r} not in {path.name}")
    values = sorted(df[target].dropna().unique().tolist())
    if len(values) != 2:
        raise ValueError(f"target {target!r} needs exactly 2 values, found {len(values)}")
    labelled = df[df[target].notna()]
    return {
        "rows": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "numeric": [str(c) for c in df.columns if c != target and pd.api.types.is_numeric_dtype(df[c])],
        "target": target,
        "target_values": values,
        "positive_label": values[1],
        "positive_rate": round(float((labelled[target] == values[1]).mean()), 4),
        "time_columns": time_columns(df, target),
        "sha256": sha256(path),
    }
