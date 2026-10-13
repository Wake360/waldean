import numpy as np
import pandas as pd
import pytest

from waldean.experiment.profile import infer_task, profile


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
