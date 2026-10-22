from waldean.analysis.dataflow import analyze
from waldean.checks.detect import detect_leakage_lag_full_series

from test_detect import nb

TTS = "X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, shuffle=False)"
CV = "scores = cross_val_score(Ridge(), X, y, cv=TimeSeriesSplit(n_splits=5))"


def flags(feature_line, features="['lag1', 'feat']", sink=TTS):
    cells = [
        "df['lag1'] = df['demand'].shift(1)\n" + feature_line,
        f"feature_cols = {features}\nX = df[feature_cols]\ny = df['demand']\n" + sink,
    ]
    notebook = nb([("code", c) for c in cells])
    return detect_leakage_lag_full_series(notebook, analyze(notebook))


def test_unshifted_rolling_mean_of_target():
    out = flags("df['feat'] = df['demand'].rolling(14).mean()")
    assert [(f.cell, f.line, f.confidence) for f in out] == [(0, 2, 0.9)]
    assert out[0].extra == {"column": "feat", "target": "demand", "reason": "window-includes-current"}


def test_centered_window_of_target():
    out = flags("df['feat'] = df['demand'].shift(1).rolling(14, center=True).mean()")
    assert [f.extra["reason"] for f in out] == ["centered-window"]


def test_negative_shift_of_target():
    assert [f.extra["reason"] for f in flags("df['feat'] = df['demand'].shift(-1)")] == ["negative-shift"]


def test_unshifted_diff_of_target():
    assert [f.extra["reason"] for f in flags("df['feat'] = df['demand'].diff()")] == ["window-includes-current"]


def test_temporal_cv_does_not_hide_it():
    assert len(flags("df['feat'] = df['demand'].rolling(7).mean()", sink=CV)) == 1


def test_shifted_window_is_silent():
    for line in (
        "df['feat'] = df['demand'].shift(1).rolling(14).mean()",
        "df['feat'] = df['demand'].shift().rolling(7).mean()",
        "df['feat'] = df['demand'].shift(h).rolling(7).mean()",
        "df['feat'] = df['demand'].shift(periods=7).ewm(span=7).mean()",
    ):
        assert not flags(line), line


def test_window_of_exogenous_column_is_silent():
    assert not flags("df['feat'] = df['temp'].rolling(7).mean()")


def test_unused_column_is_silent():
    assert not flags("df['feat'] = df['demand'].rolling(14).mean()", features="['lag1']")


def test_target_smoothing_is_silent():
    assert not flags("df['demand'] = df['demand'].rolling(7).mean()")
