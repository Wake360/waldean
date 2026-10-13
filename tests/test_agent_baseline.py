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
