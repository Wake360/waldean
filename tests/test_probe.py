import dataclasses

import nbformat
import pytest

from waldean.core.flag import Flag
from waldean.runtime.probe import probe_fit_before_split

pytest.importorskip("nbclient")


def flag(**extra):
    return Flag("leakage-fit-before-split", "high", 0.92, 1, 1, "scaler fit", "", "", extra=extra)


def notebook(*sources):
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_code_cell(s) for s in sources]
    return nb


LEAKY = notebook(
    "import numpy as np\nfrom sklearn.preprocessing import StandardScaler\nX = np.arange(40.0).reshape(20, 2)\ny = np.arange(20)",
    "scaler = StandardScaler()\nX = scaler.fit_transform(X)",
    "from sklearn.model_selection import train_test_split\nX_tr, X_te, y_tr, y_te = train_test_split(X, y)",
    "raise SystemExit('never reached')",
)


def test_probe_confirms_full_fit():
    out = probe_fit_before_split(LEAKY, [flag(receiver="scaler", arg="X", sink_cell=2)])
    assert out[0].confidence == 0.97
    assert "probe: n_samples_seen_ = 20 of 20 rows" in out[0].evidence


def test_probe_demotes_partial_fit():
    nb = notebook(
        LEAKY.cells[0].source,
        "scaler = StandardScaler()\nscaler.fit(X[:15])",
        LEAKY.cells[2].source,
    )
    out = probe_fit_before_split(nb, [flag(receiver="scaler", arg="X", sink_cell=2)])
    assert out[0].confidence == 0.5
    assert "15 of 20 rows" in out[0].evidence


def test_probe_error_keeps_static_confidence():
    nb = notebook(LEAKY.cells[0].source, "scaler = StandardScaler()\nX = scaler.fit_transform(X)", "1/0")
    out = probe_fit_before_split(nb, [flag(receiver="scaler", arg="X", sink_cell=2)])
    assert out[0].confidence == 0.92
    assert "probe: error (ZeroDivisionError" in out[0].evidence


def test_probe_passes_other_classes_through():
    other = Flag("leakage-temporal-shuffle", "high", 0.9, 0, 1, "", "", "")
    assert probe_fit_before_split(LEAKY, [other]) == [other]


def test_probe_timeout_keeps_static_confidence():
    nb = notebook(LEAKY.cells[0].source, "scaler = StandardScaler()\nX = scaler.fit_transform(X)", "import time; time.sleep(5)")
    out = probe_fit_before_split(nb, [flag(receiver="scaler", arg="X", sink_cell=2)], timeout=1)
    assert out[0].confidence == 0.92
    assert "probe: error" in out[0].evidence


def test_probe_never_raises_a_candidate():
    candidate = dataclasses.replace(flag(receiver="scaler", arg="X", sink_cell=2), confidence=0.75)
    out = probe_fit_before_split(LEAKY, [candidate])
    assert out[0].confidence == 0.75
    assert "probe: n_samples_seen_ = 20 of 20 rows" in out[0].evidence
