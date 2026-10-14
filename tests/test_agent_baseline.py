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


def test_headline_is_auc_accepts_roc_names_only():
    for name in ["test_roc_auc", "test_auc", "oof_roc_auc", "roc_auc", "auc"]:
        assert ab.headline_is_auc(f"('{name}', 0.74)")
    for name in ["pr_auc", "average_precision", "f1"]:
        assert not ab.headline_is_auc(f"('{name}', 0.74)")


def test_gap_needs_both_numbers():
    assert round(ab.gap({"headline": "('roc_auc', 0.75)", "future_auc": "0.70"}), 3) == 0.05
    assert ab.gap({"headline": "('roc_auc', 0.75)", "future_auc": "None"}) is None
    assert round(ab.gap({"headline": "('ROC AUC', 0.75)", "future_auc": "0.70"}), 3) == 0.05
    assert ab.gap({"headline": "('average_precision', 0.75)", "future_auc": "0.70"}) is None


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
    for name in ("s-claude-C-0", "s-claude-B-0"):
        (runs / name).mkdir(parents=True)
        nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell("h = pd.read_csv('holdout.csv')\nprint('protocol')\ncv = TimeSeriesSplit(5)\nkind = 'walk_forward'")])
        nb.metadata = {"kernelspec": {"name": "waldean-agent-baseline"}}
        nb.cells[0].metadata = {"tags": ["protocol"]}
        nbformat.write(nb, runs / name / "experiment.ipynb")
    (tmp_path / "runs-redacted").mkdir()
    (tmp_path / "runs-redacted" / "nb-009.ipynb").write_text("stale")
    args = type("A", (), {"runs": runs, "seed": 1, "arms": ["C"]})()
    assert ab.cmd_redact(args) == 0
    assert sorted(p.name for p in (tmp_path / "runs-redacted").iterdir()) == ["nb-000.ipynb"]
    out = nbformat.read(tmp_path / "runs-redacted" / "nb-000.ipynb", as_version=4)
    assert "holdout.csv" not in out.cells[0].source and "protocol" not in out.cells[0].source
    assert "TimeSeriesSplit" not in out.cells[0].source and "walk_forward" not in out.cells[0].source
    assert out.metadata == {} and out.cells[0].metadata == {}
    key = json.loads((tmp_path / "runs-redaction-key.json").read_text())
    assert key == {"nb-000": "s-claude-C-0"}


def test_render_arms_primary_needs_completion():
    m = {"arms": {"B": {}, "C": {}}, "criteria": {"selection": {}}, "comparisons": [], "primary": ["B", "C"],
         "prompt": "p", "datasets": [{"name": "s", "criteria": {"selection": ""}}]}
    rows = [{"run": f"s-claude-{a}-{i}", "variant": a, "dataset": "s", "sha256": "" if a == "C" and i < 4 else "x",
             "cli_version": "1", "selection": "fail" if a == "B" and i < 6 else "pass",
             "headline": "", "future_auc": "", "check": ""} for a in ("B", "C") for i in range(20)]
    text = ab.render_arms(m, rows)
    assert "completion B 100% vs C 80%" in text
    assert "no evidence that C is better" in text


def test_secondary_reports_all_five():
    m = {"arms": {"B": {}, "C": {}}, "criteria": {"selection": {}}, "comparisons": [], "primary": ["B", "C"],
         "prompt": "p", "datasets": [{"name": "s", "criteria": {"selection": ""}},
                                     {"name": "t", "criteria": {"selection": ""}}]}
    rows = [{"run": f"{ds}-claude-{a}-{i}", "variant": a, "dataset": ds, "sha256": "x", "cli_version": "1",
             "selection": "fail" if a == "B" and i < 3 else "pass", "headline": "", "future_auc": "", "check": ""}
            for ds in ("s", "t") for a in ("B", "C") for i in range(10)]
    text = ab.render_arms(m, rows)
    assert "1. Boschloo exact, two-sided, B 6/20 vs C 0/20: p = 0." in text
    assert "mean B 0.300 vs C 0.000" in text
    assert "3. Beta(1,1) posterior P(failure rate C < B) = 0.99" in text
    assert "4. Mantel-Haenszel odds ratio of failure B vs C, stratified by dataset: undefined" in text
    assert "5. Failure counts per criterion" in text


def test_mantel_haenszel_two_strata():
    odds, low, high = ab.mantel_haenszel([(4, 16, 1, 19), (3, 17, 1, 19)])
    assert 4.0 < odds < 4.5
    assert low < odds < high


def test_kappa_matches_hand_computation():
    first = {"a": "fail", "b": "pass", "c": "pass", "d": "fail"}
    second = {"a": "fail", "b": "pass", "c": "fail", "d": "fail", "e": "pass"}
    agree, n, k = ab.kappa(first, second)
    assert (agree, n) == (3, 4)
    assert abs(k - 0.5) < 1e-9


def test_kappa_all_pass_is_undefined():
    assert ab.kappa({"a": "pass"}, {"a": "pass"}) == (1, 1, None)


def test_cmd_kappa_reads_per_criterion(tmp_path, monkeypatch, capsys):
    import json
    runs = tmp_path / "runs"
    runs.mkdir()
    (tmp_path / "runs-redaction-key.json").write_text(json.dumps({"nb-000": "s-claude-B-0", "nb-001": "s-claude-C-0"}))
    bench = tmp_path / "bench"
    bench.mkdir()
    (bench / "MANIFEST.json").write_text(json.dumps({"criteria": {"temporal": {}, "selection": {}}}))
    (bench / "second-rater.tsv").write_text("run\tcriterion\truling\nnb-000\ttemporal\tfail\nnb-000\tselection\tpass\n"
                                            "nb-001\ttemporal\tpass\nnb-001\tselection\tpass\n")
    (bench / "results-first-rater.tsv").write_text("run\tvariant\ttemporal\tselection\ns-claude-B-0\tB\tpass\tpass\n"
                                                   "s-claude-C-0\tC\tpass\tpass\ns-claude-A-0\tA\tfail\tfail\n")
    monkeypatch.setattr(ab, "BENCH", bench)
    monkeypatch.setattr(ab, "MANIFEST", bench / "MANIFEST.json")
    args = type("A", (), {"runs": runs})()
    assert ab.cmd_kappa(args) == 0
    out = capsys.readouterr().out
    assert "temporal: agreement 1/2" in out
    assert "temporal: disagree ['s-claude-B-0']" in out
    assert "selection: agreement 2/2 kappa -" in out
    assert "pooled: agreement 3/4" in out
