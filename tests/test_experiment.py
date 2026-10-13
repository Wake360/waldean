import numpy as np
import pandas as pd
import pytest

from waldean.experiment.plan import PlanError, contradictions, design, design_md, read_plan, write_plan
from waldean.experiment.profile import profile


def write_csv(path, n=1200, seed=0, extra_dates=False, single_class_month=None):
    rng = np.random.default_rng(seed)
    month = rng.integers(0, 24, n)
    x = rng.normal(size=n)
    y = (x + month / 12 + rng.normal(size=n) > 1.5).astype(int)
    if single_class_month is not None:
        y[month == single_class_month] = 0
    periods = pd.period_range("2024-01", periods=24, freq="M").astype(str)
    df = pd.DataFrame({
        "account": [f"A{i % 50:03d}" for i in range(n)],
        "snapshot": np.asarray(periods)[month],
        "x": x.round(3),
        "plan": rng.choice(["basic", "pro"], n),
        "churn": y,
    })
    if extra_dates:
        df["birth_date"] = pd.to_datetime("1960-01-01") + pd.to_timedelta(rng.integers(0, 15000, n), unit="D")
        df["birth_date"] = df["birth_date"].dt.strftime("%Y-%m-%d")
    df.to_csv(path, index=False)
    return path


def test_profile_finds_the_month_column(tmp_path):
    prof = profile(write_csv(tmp_path / "d.csv"), "churn")
    assert [t["column"] for t in prof["time_columns"]] == ["snapshot"]
    assert prof["time_columns"][0]["periods"] == 24
    assert prof["target_values"] == [0, 1]
    assert prof["positive_label"] == 1
    assert prof["numeric"] == ["x"]
    assert len(prof["sha256"]) == 64


def test_ids_and_categories_are_not_time_columns(tmp_path):
    prof = profile(write_csv(tmp_path / "d.csv"), "churn")
    assert "account" not in [t["column"] for t in prof["time_columns"]]
    assert "plan" not in [t["column"] for t in prof["time_columns"]]


def test_numeric_strings_are_not_time_columns(tmp_path):
    path = tmp_path / "d.csv"
    pd.DataFrame({"code": [str(2000 + i % 30) for i in range(200)], "y": [i % 2 for i in range(200)]}).to_csv(path, index=False)
    assert profile(path, "y")["time_columns"] == []


def test_few_distinct_dates_are_not_a_time_column(tmp_path):
    path = tmp_path / "d.csv"
    pd.DataFrame({"d": ["2024-01-01", "2024-02-01"] * 100, "y": [0, 1] * 100}).to_csv(path, index=False)
    assert profile(path, "y")["time_columns"] == []


def test_non_binary_target_is_refused(tmp_path):
    path = tmp_path / "d.csv"
    pd.DataFrame({"x": range(30), "y": [0, 1, 2] * 10}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="exactly 2 values"):
        profile(path, "y")


def test_missing_target_is_refused(tmp_path):
    with pytest.raises(ValueError, match="not in"):
        profile(write_csv(tmp_path / "d.csv"), "nope")


def planned(tmp_path, **kw):
    csv = write_csv(tmp_path / "d.csv", extra_dates=kw.pop("extra_dates", False))
    prof = profile(csv, "churn")
    args = {"goal": "churn?", "exclude": [], "time_column": None, "seed": 0} | kw
    return design(prof, csv, tmp_path / "exp", **args), prof


def test_time_column_gives_temporal_holdout(tmp_path):
    plan, _ = planned(tmp_path)
    assert plan["split"] == {"kind": "temporal_holdout", "column": "snapshot", "test_fraction": 0.2, "n_splits": 5}
    assert "snapshot" not in plan["features"]["numeric"] + plan["features"]["categorical"]
    assert plan["dataset"]["path"] == "../d.csv"


def test_two_time_columns_need_a_choice(tmp_path):
    with pytest.raises(PlanError, match="birth_date.*snapshot|snapshot.*birth_date"):
        planned(tmp_path, extra_dates=True)
    plan, _ = planned(tmp_path, extra_dates=True, time_column="snapshot")
    assert plan["split"]["column"] == "snapshot"


def test_unknown_time_column_is_refused(tmp_path):
    with pytest.raises(PlanError, match="not a time column"):
        planned(tmp_path, time_column="plan")


def test_exclude_unknown_column_is_refused(tmp_path):
    with pytest.raises(PlanError, match="not a column"):
        planned(tmp_path, exclude=["nope"])


def test_excluded_columns_leave_the_features(tmp_path):
    plan, _ = planned(tmp_path, exclude=["account"])
    assert "account" not in plan["features"]["categorical"]
    assert {"column": "account", "reason": "excluded by the user (--exclude)"} in plan["excluded_columns"]


def test_no_time_column_gives_stratified(tmp_path):
    path = tmp_path / "d.csv"
    pd.DataFrame({"x": range(100), "y": [0, 1] * 50}).to_csv(path, index=False)
    plan = design(profile(path, "y"), path, tmp_path / "exp", "", [], None, 0)
    assert plan["split"]["kind"] == "stratified_kfold"


def test_contradictions(tmp_path):
    plan, prof = planned(tmp_path)
    assert contradictions(plan, prof) == []
    plan["split"]["kind"] = "stratified_kfold"
    assert contradictions(plan, prof) == ["split.kind"]
    plan["split"]["override_reason"] = "rows are i.i.d. snapshots"
    assert contradictions(plan, prof) == []
    plan["split"] = {"kind": "temporal_holdout", "column": "plan", "test_fraction": 0.2, "n_splits": 5}
    assert contradictions(plan, prof) == ["split.column"]


def test_unknown_split_kind_is_refused(tmp_path):
    plan, prof = planned(tmp_path)
    plan["split"]["kind"] = "group_kfold"
    with pytest.raises(PlanError, match="split.kind"):
        contradictions(plan, prof)


def test_plan_round_trips_and_design_md_names_the_fact(tmp_path):
    plan, prof = planned(tmp_path)
    write_plan(plan, tmp_path / "plan.yaml")
    assert read_plan(tmp_path / "plan.yaml") == plan
    text = design_md(plan, prof)
    assert "temporal_holdout on snapshot" in text
    assert "24 distinct periods" in text
