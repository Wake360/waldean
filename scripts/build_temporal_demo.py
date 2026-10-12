import argparse
import importlib.metadata
import os
import platform
import re
from datetime import date
from pathlib import Path

import nbformat

from wald.execute import execute, stdout_lines

INTRO = """# Temporal CV leakage: impressive metric, wrong protocol

Synthetic daily demand series generated below with a fixed seed, so the notebook runs offline.
The same model and the same features are scored twice. Only the cross-validation protocol changes."""

IMPORTS = """import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import KFold, TimeSeriesSplit, cross_validate"""

DATA = """rng = np.random.default_rng(7)
n = 1460
t = np.arange(n)
demand = (200 + 0.15 * t + 25 * np.sin(2 * np.pi * t / 365.25)
          + 8 * np.sin(2 * np.pi * t / 7) + np.cumsum(rng.normal(0, 3, n)))
dates = pd.date_range("2021-01-01", periods=n, freq="D")
df = pd.DataFrame({"date": dates, "demand": demand})"""

FEATURES = """df["lag_1"] = df["demand"].shift(1)
df["lag_7"] = df["demand"].shift(7)
df["rolling_7"] = df["demand"].shift(1).rolling(7).mean()
df["day_of_week"] = df["date"].dt.dayofweek
df = df.dropna().reset_index(drop=True)
features = ["lag_1", "lag_7", "rolling_7", "day_of_week"]
X = df[features]
y = df["demand"]
model = RandomForestRegressor(n_estimators=200, random_state=0, n_jobs=-1)
scoring = ("r2", "neg_mean_absolute_error")"""

BEFORE_MD = """## Before: shuffled 5-fold CV

Each fold trains on days that come after the days it is tested on.
The lag features make neighbouring days near-duplicates, so the model interpolates instead of forecasting."""

BEFORE = """kf = KFold(n_splits=5, shuffle=True, random_state=0)
shuffled = cross_validate(model, X, y, cv=kf, scoring=scoring)
print(f"shuffled KFold: R2={shuffled['test_r2'].mean():.3f} MAE={-shuffled['test_neg_mean_absolute_error'].mean():.2f}")"""

AFTER_MD = """## After: TimeSeriesSplit

Every fold trains only on the past and tests on the following block of days."""

AFTER = """tscv = TimeSeriesSplit(n_splits=5)
temporal = cross_validate(model, X, y, cv=tscv, scoring=scoring)
print(f"TimeSeriesSplit: R2={temporal['test_r2'].mean():.3f} MAE={-temporal['test_neg_mean_absolute_error'].mean():.2f}")"""

OUTRO = """## What changed

The data, features and model are identical. The difference between the two printed scores is the leakage.
`wald check` flags the shuffled protocol statically, without running this notebook. The metric gap above is computed here, not claimed by Wald."""

PACKAGES = ("numpy", "pandas", "scikit-learn")


def build() -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nb.cells = [
        nbformat.v4.new_markdown_cell(INTRO),
        nbformat.v4.new_code_cell(IMPORTS),
        nbformat.v4.new_code_cell(DATA),
        nbformat.v4.new_code_cell(FEATURES),
        nbformat.v4.new_markdown_cell(BEFORE_MD),
        nbformat.v4.new_code_cell(BEFORE),
        nbformat.v4.new_markdown_cell(AFTER_MD),
        nbformat.v4.new_code_cell(AFTER),
        nbformat.v4.new_markdown_cell(OUTRO),
    ]
    return nb


def metric_lines(nb) -> list[str]:
    return stdout_lines(nb, "shuffled KFold:") + stdout_lines(nb, "TimeSeriesSplit:")


def write_eval(evals_dir: Path, lines: list[str], out: Path) -> Path:
    day = os.environ.get("WALD_BUILD_DATE", date.today().isoformat())
    versions = "\n".join(f"- {p} {importlib.metadata.version(p)}" for p in PACKAGES)
    path = evals_dir / f"{day}-temporal-cv-demo.md"
    path.write_text(
        f"# Temporal-CV demo run — {day}\n\n"
        f"Notebook: `{out.as_posix()}`, built by `scripts/build_temporal_demo.py`.\n\n"
        "```\n" + "\n".join(lines) + "\n```\n\n"
        f"Python {platform.python_version()} on {platform.system()}.\n\n{versions}\n\n"
        "Seeds: data `default_rng(7)`, `KFold(random_state=0)`, `RandomForestRegressor(random_state=0)`.\n"
        "The data is synthetic. The gap shows the protocol effect on this series, not a typical real-world size.\n",
        encoding="utf-8",
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--evals-dir")
    args = parser.parse_args()
    out = Path(args.out)
    executed = execute(build(), timeout=600)
    lines = metric_lines(executed)
    if len(lines) != 2 or not all(re.search(r"R2=-?\d", ln) for ln in lines):
        raise SystemExit(f"expected two metric lines, got {lines}")
    nbformat.write(executed, out)
    print("\n".join(lines))
    if args.evals_dir:
        print(f"wrote {write_eval(Path(args.evals_dir), lines, out)}")


if __name__ == "__main__":
    main()
