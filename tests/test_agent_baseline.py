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


def test_tmp_entries_lists_user_tmp(tmp_path, monkeypatch):
    user = tmp_path / "claude-501"
    (user / "build").mkdir(parents=True)
    (user / "nbdump_1.txt").write_text("x")
    monkeypatch.setattr(ab, "USER_TMP", user)
    assert ab.tmp_entries() == {"build", "nbdump_1.txt"}
    monkeypatch.setattr(ab, "USER_TMP", tmp_path / "absent")
    assert ab.tmp_entries() == set()


def test_newcombe_matches_published_example():
    low, high = ab.newcombe(56, 70, 48, 80)
    assert round(low, 4) == 0.0524 and round(high, 4) == 0.3339


def test_headline_value_reads_numpy_float():
    assert ab.headline_value("('roc_auc', np.float64(0.7566))") == 0.7566
    assert ab.headline_value("('roc_auc', 0.71)") == 0.71


def test_headline_value_rejects_text():
    assert ab.headline_value("('roc_auc', 'text: about 0.69')") is None
    assert ab.headline_value("") is None


def test_gap_needs_both_numbers():
    assert round(ab.gap({"headline": "('roc_auc', 0.75)", "future_auc": "0.70"}), 3) == 0.05
    assert ab.gap({"headline": "('roc_auc', 0.75)", "future_auc": "None"}) is None


def test_render_arms_counts_invalid_runs():
    m = {"arms": {"B": {}, "C": {}}, "criteria": {"selection": {}, "temporal": {}},
         "comparisons": [["B", "C"]], "primary": ["B", "C"], "prompt": "p",
         "datasets": [{"name": "s", "criteria": {"selection": "", "temporal": ""}}]}
    rows = [{"run": f"s-claude-{a}-{i}", "variant": a, "dataset": "s", "sha256": "x", "cli_version": "1",
             "selection": "fail" if a == "B" and i < 6 else "pass", "temporal": "pass",
             "headline": "", "future_auc": "", "check": ""} for a in ("B", "C") for i in range(20)]
    text = ab.render_arms(m, rows)
    assert "| B | 20 | 20 | 14/20" in text
    assert "| C | 20 | 20 | 20/20" in text
    assert "C better" in text


def test_similar_finds_copy(tmp_path):
    import nbformat
    for name, src in (("a", "x = 1\ny = 2\nprint(x + y)"), ("b", "x = 1\ny = 2\nprint(x + y)"), ("c", "z = 9")):
        (tmp_path / name).mkdir()
        nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(src)])
        nbformat.write(nb, tmp_path / name / "experiment.ipynb")
    args = type("A", (), {"runs": tmp_path, "threshold": 0.6})()
    assert ab.cmd_similar(args) == 1


def test_redact_hides_arm_words(tmp_path):
    import json
    import nbformat
    runs = tmp_path / "runs"
    (runs / "s-claude-C-0").mkdir(parents=True)
    nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell("h = pd.read_csv('holdout.csv')\nprint('protocol')")])
    nbformat.write(nb, runs / "s-claude-C-0" / "experiment.ipynb")
    args = type("A", (), {"runs": runs, "seed": 1})()
    assert ab.cmd_redact(args) == 0
    out = nbformat.read(tmp_path / "runs-redacted" / "nb-000.ipynb", as_version=4)
    assert "holdout.csv" not in out.cells[0].source and "protocol" not in out.cells[0].source
    key = json.loads((tmp_path / "runs-redaction-key.json").read_text())
    assert key == {"nb-000": "s-claude-C-0"}
