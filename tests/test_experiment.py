import ast
import json

import nbformat
import numpy as np
import pandas as pd
import pytest

from waldean.analysis.dataflow import analyze
from waldean.analysis.ingest import parse_notebook
from waldean.checks.detect import run_static
from waldean.experiment.plan import PlanError, contradictions, design, design_md, read_plan, write_plan
from waldean.experiment.profile import profile
from waldean.experiment.render import render
from waldean.experiment.workflow import build, create, run
from waldean.runtime.execute import execute, stdout_lines


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


def test_three_value_target_is_multiclass(tmp_path):
    path = tmp_path / "d.csv"
    pd.DataFrame({"x": range(30), "y": [0, 1, 2] * 10}).to_csv(path, index=False)
    assert profile(path, "y")["task"] == "multiclass"


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
    assert contradictions(plan, prof) == ["split.column", "features"]


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


def rendered(tmp_path, **kw):
    plan, prof = planned(tmp_path, **kw)
    (tmp_path / "exp").mkdir(exist_ok=True)
    return render(plan), plan


def run_rendered(tmp_path, nb, probe=""):
    if probe:
        nb.cells.append(nbformat.v4.new_code_cell(probe))
    return execute(nb, cwd=str(tmp_path / "exp"))


def test_render_is_byte_deterministic(tmp_path):
    nb, plan = rendered(tmp_path)
    assert nbformat.writes(nb) == nbformat.writes(render(plan))


def test_every_code_cell_names_its_plan_field_and_parses(tmp_path):
    nb, _ = rendered(tmp_path)
    for cell in nb.cells:
        if cell.cell_type == "code":
            assert cell.metadata["waldean"]["plan_field"]
            ast.parse(cell.source)


def test_rendered_notebook_is_clean_under_check(tmp_path):
    nb, _ = rendered(tmp_path)
    path = tmp_path / "exp" / "experiment.ipynb"
    nbformat.write(nb, path)
    parsed = parse_notebook(path)
    assert [f.flaw_id for f in run_static(parsed, analyze(parsed)) if f.confidence >= 0.8] == []


def test_no_period_crosses_any_split(tmp_path):
    nb, _ = rendered(tmp_path)
    probe = (
        "_t = pd.to_datetime(df['snapshot'], format='mixed')\n"
        "_ok = _t[train].max() < _t[test].min() and all(_t.iloc[a].max() < _t.iloc[b].min() for a, b in folds)\n"
        "print('PROBE', bool(_ok), len(folds))"
    )
    out = stdout_lines(run_rendered(tmp_path, nb, probe), "PROBE")
    assert out and out[-1].split()[1:] == ["True", "5"]


def test_metrics_line_has_both_models(tmp_path):
    nb, _ = rendered(tmp_path)
    line = stdout_lines(run_rendered(tmp_path, nb), "WALDEAN_METRICS ")[-1]
    metrics = json.loads(line.removeprefix("WALDEAN_METRICS "))
    assert set(metrics["holdout"]) == {"baseline", "candidate"}
    assert set(metrics["holdout"]["candidate"]) == {"roc_auc", "average_precision", "balanced_accuracy"}
    assert len(metrics["cv"]["candidate"]) == 5
    assert metrics["skipped_folds"] == 0


def test_single_class_fold_is_skipped_and_counted(tmp_path):
    csv = write_csv(tmp_path / "d.csv", single_class_month=3)
    prof = profile(csv, "churn")
    plan = design(prof, csv, tmp_path / "exp", "", [], None, 0)
    plan["split"]["n_splits"] = 18
    (tmp_path / "exp").mkdir()
    line = stdout_lines(run_rendered(tmp_path, render(plan)), "WALDEAN_METRICS ")[-1]
    assert json.loads(line.removeprefix("WALDEAN_METRICS "))["skipped_folds"] >= 1


def test_stratified_plan_renders_and_runs(tmp_path):
    plan, _ = planned(tmp_path)
    plan["split"] = {"kind": "stratified_kfold", "column": None, "test_fraction": 0.2, "n_splits": 5,
                     "override_reason": "test"}
    (tmp_path / "exp").mkdir()
    assert stdout_lines(run_rendered(tmp_path, render(plan)), "WALDEAN_METRICS ")


def test_undated_rows_are_in_neither_split(tmp_path):
    csv = write_csv(tmp_path / "d.csv")
    df = pd.read_csv(csv)
    df["snapshot"] = df["snapshot"].astype(object)
    df.loc[df.index[:10], "snapshot"] = None
    df.loc[df.index[10:20], "snapshot"] = "garbage"
    df.to_csv(csv, index=False)
    prof = profile(csv, "churn")
    plan = design(prof, csv, tmp_path / "exp", "", [], None, 0)
    (tmp_path / "exp").mkdir()
    probe = (
        "_t = pd.to_datetime(df['snapshot'], errors='coerce', format='mixed')\n"
        "_ok = _t[test].notna().all() and _t[train].notna().all() and not (train & test).any()"
        " and not (train | test)[_t.isna().to_numpy()].any() and int(_t.isna().sum()) == 20\n"
        "print('PROBE', bool(_ok))"
    )
    out = stdout_lines(run_rendered(tmp_path, render(plan), probe), "PROBE")
    assert out and out[-1].split()[1:] == ["True"]


def made(tmp_path, **kw):
    csv = write_csv(tmp_path / "d.csv")
    return create(csv, "churn", tmp_path / "exp", goal="churn?", **kw)


def test_create_writes_plan_and_design(tmp_path):
    exp = made(tmp_path)
    assert (exp / "plan.yaml").exists() and "temporal_holdout" in (exp / "design.md").read_text()
    assert not (exp / "experiment.ipynb").exists()


def test_build_writes_notebook_hashes_and_check(tmp_path):
    exp = made(tmp_path)
    fields, flags = build(exp)
    assert fields == [] and [f for f in flags if f.confidence >= 0.8] == []
    meta = json.loads((exp / "build.json").read_text())
    assert set(meta) == {"dataset", "plan", "notebook"}
    first = (exp / "experiment.ipynb").read_bytes()
    build(exp)
    assert (exp / "experiment.ipynb").read_bytes() == first


def test_build_returns_the_contradicting_field(tmp_path):
    exp = made(tmp_path)
    plan = read_plan(exp / "plan.yaml")
    plan["split"]["kind"] = "stratified_kfold"
    write_plan(plan, exp / "plan.yaml")
    assert build(exp) == (["split.kind"], [])
    assert not (exp / "experiment.ipynb").exists()


def test_build_refuses_a_changed_dataset(tmp_path):
    exp = made(tmp_path)
    write_csv(tmp_path / "d.csv", seed=1)
    with pytest.raises(PlanError, match="d.csv"):
        build(exp)


def test_run_writes_evidence(tmp_path):
    exp = made(tmp_path)
    build(exp)
    ev = run(exp)
    names = {p.name for p in ev.iterdir()}
    assert names == {"experiment.ipynb", "plan.yaml", "build.json", "check.json", "metrics.json",
                     "environment.json", "limitations.md"}
    assert json.loads((ev / "metrics.json").read_text())["holdout"]["candidate"]["roc_auc"] > 0.5


def test_run_metrics_are_identical_twice(tmp_path):
    exp = made(tmp_path)
    build(exp)
    first = (run(exp) / "metrics.json").read_text()
    assert (run(exp) / "metrics.json").read_text() == first


def test_override_is_quoted_in_limitations(tmp_path):
    exp = made(tmp_path)
    plan = read_plan(exp / "plan.yaml")
    plan["split"] = {"kind": "stratified_kfold", "column": None, "test_fraction": 0.2, "n_splits": 5,
                     "override_reason": "snapshots are i.i.d. here"}
    write_plan(plan, exp / "plan.yaml")
    assert build(exp)[0] == []
    assert "snapshots are i.i.d. here" in (run(exp) / "limitations.md").read_text()


@pytest.mark.parametrize("name", ["d.csv", "plan.yaml", "experiment.ipynb"])
def test_run_refuses_changed_inputs(tmp_path, name):
    exp = made(tmp_path)
    build(exp)
    target = tmp_path / "d.csv" if name == "d.csv" else exp / name
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(PlanError, match=name):
        run(exp)


def edited(tmp_path, edit):
    exp = made(tmp_path)
    plan = read_plan(exp / "plan.yaml")
    edit(plan)
    write_plan(plan, exp / "plan.yaml")
    return exp


@pytest.mark.parametrize("edit, field", [
    (lambda p: p["split"].update(n_splits="5); import os#"), "split.n_splits"),
    (lambda p: p.update(seed="0); import os#"), "seed"),
    (lambda p: p["split"].update(test_fraction=1.5), "split.test_fraction"),
    (lambda p: p["features"].update(numeric=["x", 3]), "features"),
])
def test_build_rejects_bad_field_types(tmp_path, edit, field):
    exp = edited(tmp_path, edit)
    with pytest.raises(PlanError, match=field):
        build(exp)
    assert not (exp / "experiment.ipynb").exists()


def test_ids_parsing_to_implausible_years_are_not_time_columns(tmp_path):
    path = tmp_path / "d.csv"
    pd.DataFrame({
        "asset_tag": [f"AT-{i:05d}" for i in range(200)],
        "inspected_at": pd.date_range("2024-01-01", periods=200, freq="D").strftime("%Y-%m-%d"),
        "y": [i % 2 for i in range(200)],
    }).to_csv(path, index=False)
    assert [t["column"] for t in profile(path, "y")["time_columns"]] == ["inspected_at"]


def dmy_csv(path):
    pd.DataFrame({
        "seen": pd.date_range("2024-01-01", periods=200, freq="D").strftime("%d/%m/%Y"),
        "x": [i % 7 for i in range(200)],
        "y": [i % 2 for i in range(200)],
    }).to_csv(path, index=False)
    return path


def test_day_first_dates_are_ambiguous_and_refused(tmp_path):
    csv = dmy_csv(tmp_path / "d.csv")
    prof = profile(csv, "y")
    assert [(t["column"], t["ambiguous"]) for t in prof["time_columns"]] == [("seen", True)]
    with pytest.raises(PlanError, match="YYYY-MM-DD"):
        design(prof, csv, tmp_path / "exp", "", [], None, 0)


def test_iso_and_month_columns_are_not_ambiguous(tmp_path):
    prof = profile(write_csv(tmp_path / "d.csv", extra_dates=True), "churn")
    assert {t["column"]: t["ambiguous"] for t in prof["time_columns"]} == {"snapshot": False, "birth_date": False}


def test_one_class_holdout_fails_with_the_reason(tmp_path):
    csv = write_csv(tmp_path / "d.csv")
    df = pd.read_csv(csv)
    df.loc[df["snapshot"] >= "2025-08", "churn"] = 0
    df.to_csv(csv, index=False)
    exp = create(csv, "churn", tmp_path / "exp")
    build(exp)
    with pytest.raises(RuntimeError, match="one class"):
        run(exp)


def test_single_class_train_fold_is_skipped(tmp_path):
    csv = write_csv(tmp_path / "d.csv", single_class_month=0)
    plan = design(profile(csv, "churn"), csv, tmp_path / "exp", "", [], None, 0)
    plan["split"]["n_splits"] = 18
    (tmp_path / "exp").mkdir()
    line = stdout_lines(run_rendered(tmp_path, render(plan)), "WALDEAN_METRICS ")[-1]
    metrics = json.loads(line.removeprefix("WALDEAN_METRICS "))
    assert metrics["skipped_folds"] >= 1 and len(metrics["cv"]["candidate"]) == 18 - metrics["skipped_folds"]


@pytest.mark.parametrize("name", ["churn", "nope", "snapshot", "account"])
def test_bad_feature_names_contradict_the_plan(tmp_path, name):
    plan, prof = planned(tmp_path, exclude=["account"])
    assert contradictions(plan, prof) == []
    plan["features"]["categorical"].append(name)
    assert contradictions(plan, prof) == ["features"]
    plan["split"]["override_reason"] = "test"
    assert contradictions(plan, prof) == ["features"]


def test_split_fields_come_before_features(tmp_path):
    plan, prof = planned(tmp_path)
    plan["split"]["kind"] = "stratified_kfold"
    plan["features"]["numeric"] += ["churn", "nope"]
    assert contradictions(plan, prof) == ["split.kind", "features"]


def test_excluding_the_target_is_refused(tmp_path):
    with pytest.raises(PlanError, match="is the target"):
        planned(tmp_path, exclude=["churn"])
