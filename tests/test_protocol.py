from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from waldean.experiment.plan import PlanError
from waldean.experiment.protocol import create_protocol


def write_data(path: Path, time=True, group=True, n=600, seed=0, missing_target=0, second_group=False):
    rng = np.random.default_rng(seed)
    month = rng.integers(0, 24, n)
    x = rng.normal(size=n)
    df = pd.DataFrame({
        "row_ref": [f"R{i:05d}" for i in range(n)],
        "account": [f"A{a:03d}" for a in rng.integers(0, 60, n)],
        "x": x.round(3),
        "churn": (x + rng.normal(size=n) > 0.8).astype(float),
    })
    desc = {"row_ref": "Identifier of the row.", "account": "Account key.", "x": "A measurement.",
            "churn": "1 if churned."}
    if time:
        df.insert(2, "snapshot", np.asarray(pd.period_range("2024-01", periods=24, freq="M").astype(str))[month])
        desc["snapshot"] = "Month of the snapshot."
    if second_group:
        df.insert(2, "site", [f"S{s:02d}" for s in rng.integers(0, 20, n)])
        desc["site"] = "Site identifier."
    if not group:
        df = df.drop(columns="account")
    if missing_target:
        df.loc[: missing_target - 1, "churn"] = np.nan
    df.to_csv(path / "data.csv", index=False)
    pd.DataFrame({"column": list(df.columns), "description": [desc[c] for c in df.columns]}).to_csv(
        path / "columns.csv", index=False)
    return path / "data.csv", path / "columns.csv"


def made(tmp_path, **kw):
    csv, cols = write_data(tmp_path, **kw)
    out = create_protocol(csv, cols, "churn", tmp_path)
    proto = yaml.safe_load((out / "protocol.yaml").read_text())
    holdout = pd.read_csv(out / "holdout.csv")["row"].tolist()
    return proto, holdout, pd.read_csv(csv)


def test_temporal_holdout_is_latest_periods(tmp_path):
    proto, holdout, df = made(tmp_path)
    assert proto["split"]["kind"] == "temporal_holdout"
    assert proto["cv"]["kind"] == "walk_forward"
    rest = df.drop(index=holdout)
    assert df.loc[holdout, "snapshot"].min() > rest["snapshot"].max()
    assert len(df.loc[holdout, "snapshot"].unique()) == 5


def test_group_holdout_keeps_whole_entities(tmp_path):
    proto, holdout, df = made(tmp_path, time=False)
    assert proto["split"] == {**proto["split"], "kind": "group_holdout", "column": "account"}
    assert proto["cv"]["kind"] == "group_kfold"
    assert not set(df.loc[holdout, "account"]) & set(df.drop(index=holdout)["account"])


def test_random_holdout_without_time_or_group(tmp_path):
    proto, holdout, df = made(tmp_path, time=False, group=False)
    assert proto["split"]["kind"] == "random_holdout"
    assert proto["cv"]["kind"] == "stratified_kfold"
    assert len(holdout) == 120


def test_unique_identifier_is_excluded_not_grouped(tmp_path):
    proto, _, _ = made(tmp_path, time=False)
    reasons = {e["column"]: e["reason"] for e in proto["excluded_columns"]}
    assert reasons["row_ref"].startswith("identifier")
    assert reasons["account"].startswith("entity key")


def test_same_input_same_holdout(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    write_data(a)
    write_data(b)
    create_protocol(a / "data.csv", a / "columns.csv", "churn", a)
    create_protocol(b / "data.csv", b / "columns.csv", "churn", b)
    assert (a / "holdout.csv").read_bytes() == (b / "holdout.csv").read_bytes()


def test_two_repeated_identifiers_refused(tmp_path):
    csv, cols = write_data(tmp_path, time=False, second_group=True)
    with pytest.raises(PlanError, match="several repeated identifier columns"):
        create_protocol(csv, cols, "churn", tmp_path)


def test_missing_target_rows_are_unused(tmp_path):
    proto, holdout, _ = made(tmp_path, missing_target=10)
    unused = pd.read_csv(tmp_path / proto["split"]["unused_file"])["row"].tolist()
    assert unused == list(range(10))
    assert not set(unused) & set(holdout)


def test_protocol_source_names_no_benchmark_dataset():
    src = Path("waldean/experiment/protocol.py").read_text()
    names = ("shipments", "tutoring", "meters", "warranty", "maintenance", "clinic", "subscriptions",
             "consignment", "student_key", "meter_ref", "person_key", "account_ref", "asset_tag")
    assert not [n for n in names if n in src]
