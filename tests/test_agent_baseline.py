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


def test_wilson_clamps_zero_failures():
    assert ab.wilson(0, 15)[0] == 0.0


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


ARMS_MANIFEST = {
    "prompt": "Predict {question}.",
    "arms": {
        "A": {"suffix": "", "files": [], "tools": []},
        "C": {"suffix": " Follow protocol.yaml.", "files": ["protocol.yaml"], "tools": ["Bash(waldean *)"]},
    },
    "agents": {"claude": {"cli": "claude", "model": "sonnet"}},
}


def test_prompt_appends_arm_suffix():
    d = {"question": "churn"}
    assert ab.prompt(ARMS_MANIFEST, d, "C") == "Predict churn. Follow protocol.yaml."
    assert ab.prompt(ARMS_MANIFEST, d, "A") == "Predict churn."


def test_agent_command_adds_arm_tools(tmp_path):
    cmd, _ = ab.agent_command("claude", ARMS_MANIFEST, "x", tmp_path, tmp_path, tools=["Bash(waldean *)"])
    assert cmd[-1] == "Bash(waldean *)"
    assert "Bash(python *)" in cmd


def test_sweep_shared_tmp_moves_everything(tmp_path, monkeypatch):
    shared = tmp_path / "claude"
    (shared / "nb").mkdir(parents=True)
    (shared / "nb" / "build.py").write_text("print(1)")
    (shared / "x.txt").write_text("x")
    monkeypatch.setattr(ab, "SHARED_TMP", shared)
    moved = ab.sweep_shared_tmp(tmp_path / "run" / ".agent-tmp")
    assert moved == ["nb", "x.txt"]
    assert (tmp_path / "run" / ".agent-tmp" / "nb" / "build.py").exists()
    assert list(shared.iterdir()) == []


def test_sweep_shared_tmp_missing_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ab, "SHARED_TMP", tmp_path / "absent")
    assert ab.sweep_shared_tmp(tmp_path / "dest") == []
