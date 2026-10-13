import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("nbclient")

spec = importlib.util.spec_from_file_location(
    "agent_baseline", Path(__file__).resolve().parent.parent / "scripts" / "agent_baseline.py")
ab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ab)


def test_usage_limited_codex_message():
    log = "ERROR: You’ve hit your usage limit. Upgrade to Pro or try again at 3:18 PM.\n"
    assert ab.usage_limited(log)


def test_usage_limited_claude_message():
    assert ab.usage_limited("Claude AI usage limit reached|1791900000\n")


def test_usage_limited_ignores_normal_log():
    assert not ab.usage_limited("wrote experiment.ipynb\nroc_auc 0.71 within the limit of the data\n")


def test_wilson_matches_manifest_example():
    low, high = ab.wilson(2, 10)
    assert round(low, 3) == 0.057 and round(high, 3) == 0.510


def test_wilson_zero_runs():
    assert ab.wilson(0, 0) == (0.0, 1.0)


def test_detector_counts_skips_unscored_rows():
    rows = [
        {"selection": "fail", "check": "leakage-test-selection"},
        {"selection": "pass", "check": "leakage-test-selection,leakage-fit-before-split"},
        {"selection": "fail", "check": ""},
        {"selection": "pass", "check": ""},
        {"selection": "unbound", "check": "leakage-test-selection"},
        {"check": ""},
    ]
    assert ab.detector_counts(rows) == {"flag_fail": 1, "flag_pass": 1, "noflag_fail": 1, "noflag_pass": 1}
