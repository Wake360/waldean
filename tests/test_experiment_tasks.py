import ast
import json

import nbformat
import numpy as np
import pandas as pd
import pytest

from waldean.analysis.dataflow import analyze
from waldean.analysis.ingest import parse_notebook
from waldean.checks.detect import run_static
from waldean.experiment.plan import TASKS, PlanError, contradictions, design, design_md
from waldean.experiment.profile import infer_task, profile
from waldean.experiment.render import render
from waldean.runtime.execute import execute, stdout_lines


def make_csv(path, task, n=1200, seed=0):
    rng = np.random.default_rng(seed)
    x1, x2 = rng.normal(size=n), rng.normal(size=n)
    signal = x1 + 0.5 * x2 + rng.normal(scale=0.5, size=n)
    df = pd.DataFrame({
        "customer_id": [f"C{i:05d}" for i in range(n)],
        "store": [f"S{i % 40:02d}" for i in range(n)],
        "x1": x1.round(3),
        "x2": x2.round(3),
        "plan": rng.choice(["basic", "pro"], n),
        "const": 1,
    })
    if task == "regression":
        df["spend"] = signal.round(3)
        df["spend_copy"] = (signal * 2).round(3)
        target = "spend"
    elif task == "multiclass":
        df["tier"] = pd.cut(signal, [-np.inf, -0.5, 0.5, np.inf], labels=["low", "mid", "high"]).astype(str)
        df["tier_code"] = df["tier"].map({"low": "L", "mid": "M", "high": "H"})
        target = "tier"
    else:
        df["churn"] = (signal > 1.0).astype(int)
        df["status"] = np.where(df["churn"] == 1, "closed", "open")
        target = "churn"
    df.to_csv(path, index=False)
    return path, target


@pytest.mark.parametrize("task", ["binary", "multiclass", "regression"])
def test_profile_infers_the_task(tmp_path, task):
    path, target = make_csv(tmp_path / "d.csv", task)
    assert profile(path, target)["task"] == task


def test_binary_profile_keeps_its_fields(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "binary")
    prof = profile(path, target)
    assert prof["target_values"] == [0, 1] and prof["positive_label"] == 1
    assert set(prof["class_counts"]) == {"0", "1"}
    assert 0 < prof["minority_share"] <= 0.5


def test_multiclass_profile_counts_classes(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "multiclass")
    prof = profile(path, target)
    assert prof["target_values"] == ["high", "low", "mid"]
    assert sum(prof["class_counts"].values()) == 1200
    assert "positive_label" not in prof


def test_regression_profile_has_target_stats(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "regression")
    prof = profile(path, target)
    assert set(prof["target_stats"]) == {"mean", "std", "min", "max"}
    assert "target_values" not in prof


def test_integer_valued_floats_with_few_levels_are_multiclass():
    assert infer_task(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0] * 20)) == "multiclass"


def test_many_integers_are_regression():
    assert infer_task(pd.Series(range(500))) == "regression"


def test_boolean_target_is_binary(tmp_path):
    path = tmp_path / "d.csv"
    pd.DataFrame({"x": range(40), "y": [True, False] * 20}).to_csv(path, index=False)
    prof = profile(path, "y")
    assert prof["task"] == "binary" and prof["positive_label"] is True


def test_class_counts_ignore_unlabelled_rows(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "multiclass")
    df = pd.read_csv(path)
    df.loc[df.index[:100], target] = None
    df.to_csv(path, index=False)
    prof = profile(path, target)
    assert sum(prof["class_counts"].values()) == 1100 and prof["rows"] == 1200


def test_task_override_is_checked_against_the_target(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "multiclass")
    with pytest.raises(ValueError, match="exactly 2 values"):
        profile(path, target, task="binary")
    with pytest.raises(ValueError, match="numeric target"):
        profile(path, target, task="regression")


def test_too_many_text_classes_are_refused(tmp_path):
    path = tmp_path / "d.csv"
    pd.DataFrame({"x": range(60), "y": [f"c{i}" for i in range(60)]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="at most 20 classes"):
        profile(path, "y")


def test_single_value_target_is_refused(tmp_path):
    path = tmp_path / "d.csv"
    pd.DataFrame({"x": range(30), "y": [1] * 30}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="at least 2"):
        profile(path, "y")


def suspects(prof):
    return {s["column"]: s["kind"] for s in prof["suspects"]}


def test_constant_and_id_columns_are_suspects(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "binary")
    found = suspects(profile(path, target))
    assert found["const"] == "constant" and found["customer_id"] == "id"
    assert "x1" not in found and "store" not in found and "plan" not in found


def test_all_null_column_is_constant(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "binary")
    df = pd.read_csv(path)
    df["empty"] = None
    df.to_csv(path, index=False)
    assert suspects(profile(path, target))["empty"] == "constant"


def test_high_cardinality_text_is_a_suspect(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "binary")
    df = pd.read_csv(path)
    df["note"] = [f"note {i // 2}" for i in range(len(df))]
    df.to_csv(path, index=False)
    prof = profile(path, target)
    assert suspects(prof)["note"] == "high_cardinality"
    assert "600 distinct values in 1200 rows" in next(s["reason"] for s in prof["suspects"] if s["column"] == "note")


def test_pure_category_is_a_target_leak_for_classification(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "binary")
    prof = profile(path, target)
    assert suspects(prof)["status"] == "target_leak"
    assert "every value maps to one target class" in next(s["reason"] for s in prof["suspects"] if s["column"] == "status")
    path, target = make_csv(tmp_path / "m.csv", "multiclass")
    assert suspects(profile(path, target))["tier_code"] == "target_leak"


def test_correlated_number_is_a_target_leak_for_regression(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "regression")
    prof = profile(path, target)
    assert suspects(prof)["spend_copy"] == "target_leak"
    assert "x1" not in suspects(prof)
    assert "spearman correlation 1.00" in next(s["reason"] for s in prof["suspects"] if s["column"] == "spend_copy")


def test_float_feature_distinct_per_row_is_not_an_id(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "binary")
    assert "x1" not in suspects(profile(path, target))


def test_time_columns_are_not_suspects(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "binary")
    df = pd.read_csv(path)
    df["day"] = pd.date_range("2024-01-01", periods=len(df), freq="h").strftime("%Y-%m-%d %H:%M")
    df.to_csv(path, index=False)
    prof = profile(path, target)
    assert "day" in [t["column"] for t in prof["time_columns"]]
    assert "day" not in suspects(prof)


def test_repeated_text_entity_is_a_group_candidate(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "binary")
    prof = profile(path, target)
    assert prof["group_columns"] == [{"column": "store", "groups": 40, "max_size": 30}]


def test_integer_column_is_a_group_only_with_an_id_like_name(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "binary")
    df = pd.read_csv(path)
    df["age"] = [18 + i % 60 for i in range(len(df))]
    df["household_id"] = [i % 100 for i in range(len(df))]
    df.to_csv(path, index=False)
    names = [g["column"] for g in profile(path, target)["group_columns"]]
    assert "age" not in names and "household_id" in names


def test_id_time_and_binary_columns_are_not_groups(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "binary")
    df = pd.read_csv(path)
    df["day"] = pd.date_range("2024-01-01", periods=len(df), freq="h").strftime("%Y-%m-%d %H:%M")
    df.to_csv(path, index=False)
    names = [g["column"] for g in profile(path, target)["group_columns"]]
    assert names == ["store"]


def designed(tmp_path, task, **kw):
    path, target = make_csv(tmp_path / "d.csv", task)
    prof = profile(path, target)
    args = {"goal": "", "exclude": [], "time_column": None, "seed": 0} | kw
    return design(prof, path, tmp_path / "exp", **args), prof


@pytest.mark.parametrize("task", ["binary", "multiclass", "regression"])
def test_plan_takes_models_and_metrics_from_the_task(tmp_path, task):
    plan, _ = designed(tmp_path, task)
    assert plan["task"] == task
    assert plan["models"] == TASKS[task]["models"] and plan["metrics"] == TASKS[task]["metrics"]
    assert "accuracy" not in plan["metrics"]
    assert ("positive_label" in plan) == (task == "binary")


def test_suspects_are_excluded_with_their_reason(tmp_path):
    plan, prof = designed(tmp_path, "binary")
    excluded = {e["column"]: e["reason"] for e in plan["excluded_columns"]}
    assert set(excluded) >= {"const", "customer_id", "status", "store"}
    assert excluded["status"] == "every value maps to one target class"
    assert excluded["store"] == "group column, used for the split only"
    features = plan["features"]["numeric"] + plan["features"]["categorical"]
    assert set(features) == {"x1", "x2", "plan"}


def test_one_group_candidate_gives_group_kfold(tmp_path):
    plan, _ = designed(tmp_path, "binary")
    assert plan["split"] == {"kind": "group_kfold", "column": "store", "test_fraction": 0.2, "n_splits": 5}
    assert any("store" in a and "one side" in a for a in plan["assumptions"])


def test_group_none_opts_out(tmp_path):
    plan, _ = designed(tmp_path, "binary", group_column="none")
    assert plan["split"]["kind"] == "stratified_kfold"
    assert "store" in plan["features"]["categorical"]


def test_regression_without_time_or_group_gives_kfold(tmp_path):
    plan, prof = designed(tmp_path, "regression", group_column="none")
    assert plan["split"]["kind"] == "kfold" and plan["split"]["column"] is None
    assert plan["split"]["override_reason"] == "group split declined by the user (--group-column none)"
    assert contradictions(plan, prof) == []
    path = tmp_path / "plain.csv"
    pd.DataFrame({"x": np.linspace(0, 1, 200), "y": np.linspace(0, 2, 200)}).to_csv(path, index=False)
    plan = design(profile(path, "y"), path, tmp_path / "exp", "", [], None, 0)
    assert plan["split"] == {"kind": "kfold", "column": None, "test_fraction": 0.2, "n_splits": 5}


def test_several_group_candidates_need_a_choice(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "binary")
    df = pd.read_csv(path)
    df["region"] = [f"R{i % 25}" for i in range(len(df))]
    df.to_csv(path, index=False)
    prof = profile(path, target)
    with pytest.raises(PlanError, match="--group-column"):
        design(prof, path, tmp_path / "exp", "", [], None, 0)
    plan = design(prof, path, tmp_path / "exp", "", [], None, 0, group_column="region")
    assert plan["split"]["column"] == "region" and "store" in plan["features"]["categorical"]


def test_unknown_group_column_is_refused(tmp_path):
    with pytest.raises(PlanError, match="not a group column"):
        designed(tmp_path, "binary", group_column="plan")


def test_time_column_beats_group_column(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "binary")
    df = pd.read_csv(path)
    df["month"] = pd.period_range("2022-01", periods=24, freq="M").astype(str)[np.arange(len(df)) % 24]
    df.to_csv(path, index=False)
    plan = design(profile(path, target), path, tmp_path / "exp", "", [], None, 0)
    assert plan["split"]["kind"] == "temporal_holdout" and plan["split"]["column"] == "month"
    assert "store" in plan["features"]["categorical"]
    assert any("store" in a and "several periods" in a for a in plan["assumptions"])


def test_keep_puts_a_suspect_back_with_a_note(tmp_path):
    plan, prof = designed(tmp_path, "binary", keep=["status"])
    assert "status" in plan["features"]["categorical"] and plan["kept_columns"] == ["status"]
    assert "status" not in {e["column"] for e in plan["excluded_columns"]}
    text = design_md(plan, prof)
    assert "status" in text and "kept by the user (--keep)" in text


def test_keep_of_a_non_suspect_is_refused(tmp_path):
    with pytest.raises(PlanError, match="was not excluded"):
        designed(tmp_path, "binary", keep=["x1"])


def test_design_md_explains_task_imbalance_and_split(tmp_path):
    plan, prof = designed(tmp_path, "multiclass")
    text = design_md(plan, prof)
    assert "Task: multiclass (3 classes)" in text
    assert "group_kfold on store" in text and "40 distinct values" in text
    assert "accuracy is not among the metrics" in text or "not imbalanced" in text
    plan, prof = designed(tmp_path, "regression", group_column="none")
    text = design_md(plan, prof)
    assert "Task: regression" in text and "5-fold CV" in text and "Positive class" not in text


def test_group_contradictions(tmp_path):
    plan, prof = designed(tmp_path, "binary")
    assert contradictions(plan, prof) == []
    plan["split"]["kind"] = "stratified_kfold"
    plan["split"]["column"] = None
    assert contradictions(plan, prof) == ["split.kind"]
    plan["split"]["override_reason"] = "stores are interchangeable here"
    assert contradictions(plan, prof) == []
    plan["split"] = {"kind": "group_kfold", "column": "plan", "test_fraction": 0.2, "n_splits": 5}
    assert "split.column" in contradictions(plan, prof)


def test_task_mismatch_is_a_contradiction(tmp_path):
    plan, prof = designed(tmp_path, "binary")
    plan["task"] = "regression"
    assert "task" in contradictions(plan, prof)


def rendered(tmp_path, task, **kw):
    plan, prof = designed(tmp_path, task, **kw)
    (tmp_path / "exp").mkdir(exist_ok=True)
    return render(plan), plan


def run_rendered(tmp_path, nb, probe=""):
    if probe:
        nb.cells.append(nbformat.v4.new_code_cell(probe))
    return execute(nb, cwd=str(tmp_path / "exp"))


def metrics_of(tmp_path, nb):
    line = stdout_lines(run_rendered(tmp_path, nb), "WALDEAN_METRICS ")[-1]
    return json.loads(line.removeprefix("WALDEAN_METRICS "))


@pytest.mark.parametrize("task, kw", [
    ("binary", {}), ("multiclass", {}), ("regression", {}),
    ("binary", {"group_column": "none"}), ("regression", {"group_column": "none"}),
])
def test_rendered_notebook_parses_and_is_clean_under_check(tmp_path, task, kw):
    nb, plan = rendered(tmp_path, task, **kw)
    for cell in nb.cells:
        if cell.cell_type == "code":
            assert cell.metadata["waldean"]["plan_field"]
            ast.parse(cell.source)
    assert nb.metadata["waldean"]["task"] == task
    path = tmp_path / "exp" / "experiment.ipynb"
    nbformat.write(nb, path)
    parsed = parse_notebook(path)
    assert [f.flaw_id for f in run_static(parsed, analyze(parsed)) if f.confidence >= 0.8] == []
    assert nbformat.writes(nb) == nbformat.writes(render(plan))


@pytest.mark.parametrize("task", ["binary", "multiclass", "regression"])
def test_metrics_line_matches_the_plan(tmp_path, task):
    nb, plan = rendered(tmp_path, task)
    metrics = metrics_of(tmp_path, nb)
    assert set(metrics["holdout"]) == {"baseline", "candidate"}
    assert set(metrics["holdout"]["candidate"]) == set(plan["metrics"])
    assert len(metrics["cv"]["candidate"]) == 5 and metrics["skipped_folds"] == 0


def test_candidate_beats_baseline_on_every_task(tmp_path):
    for task, metric, better in [("binary", "roc_auc", 1), ("multiclass", "macro_f1", 1), ("regression", "rmse", -1)]:
        nb, _ = rendered(tmp_path, task)
        m = metrics_of(tmp_path, nb)["holdout"]
        assert better * (m["candidate"][metric] - m["baseline"][metric]) > 0


def test_no_group_crosses_any_split(tmp_path):
    nb, _ = rendered(tmp_path, "binary")
    probe = (
        "_g = df['store']\n"
        "_ok = not (set(_g[train]) & set(_g[test])) and all(not (set(_g.iloc[a]) & set(_g.iloc[b])) for a, b in folds)\n"
        "print('PROBE', bool(_ok), len(folds))"
    )
    out = stdout_lines(run_rendered(tmp_path, nb, probe), "PROBE")
    assert out and out[-1].split()[1:] == ["True", "5"]


def test_ungrouped_rows_are_in_neither_split(tmp_path):
    path, target = make_csv(tmp_path / "d.csv", "binary")
    df = pd.read_csv(path)
    df.loc[df.index[:15], "store"] = None
    df.to_csv(path, index=False)
    prof = profile(path, target)
    plan = design(prof, path, tmp_path / "exp", "", [], None, 0)
    (tmp_path / "exp").mkdir()
    probe = (
        "_missing = df['store'].isna().to_numpy()\n"
        "_ok = not (train & test).any() and not (train | test)[_missing].any() and int(_missing.sum()) == 15\n"
        "print('PROBE', bool(_ok))"
    )
    out = stdout_lines(run_rendered(tmp_path, render(plan), probe), "PROBE")
    assert out and out[-1].split()[1:] == ["True"]


def test_multiclass_fold_missing_a_class_is_skipped(tmp_path):
    from sklearn.model_selection import GroupShuffleSplit

    path, target = make_csv(tmp_path / "d.csv", "multiclass")
    df = pd.read_csv(path)
    rows = np.arange(len(df))
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=0)
    train_rows, _ = next(splitter.split(rows, groups=df["store"].to_numpy()))
    store = df["store"].iloc[train_rows[0]]
    df["tier"] = df["tier"].replace({"low": "mid"})
    df.loc[df["store"] == store, "tier"] = "low"
    df.to_csv(path, index=False)
    prof = profile(path, target)
    plan = design(prof, path, tmp_path / "exp", "", [], None, 0)
    assert plan["split"]["kind"] == "group_kfold"
    (tmp_path / "exp").mkdir()
    assert metrics_of(tmp_path, render(plan))["skipped_folds"] == 1
