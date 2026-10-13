import copy
import json
import os
import re
from pathlib import Path

import nbformat
import pytest

from waldean.repair import counterfactual, metric_values, propose, render_brief, scrubbed_env, supported, verify
from waldean.taxonomy import load_taxonomy

IMPORTS = """import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold, cross_val_score"""

DATA = """dates = pd.date_range("2024-01-01", periods=400, freq="D")
df = pd.DataFrame({"date": dates, "y": np.arange(400.0)})"""

FEATURES = """df["lag_1"] = df["y"].shift(1)
df = df.dropna()
X = df[["lag_1"]]
y = df["y"]"""

SHUFFLED = """kf = KFold(n_splits=5, shuffle=True, random_state=0)
scores = cross_val_score(Ridge(), X, y, cv=kf)
print(f"R2={scores.mean():.3f}")"""

TEMPORAL = """from sklearn.model_selection import TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=5)
scores = cross_val_score(Ridge(), X, y, cv=tscv)
print(f"R2={scores.mean():.3f}")"""


def write_nb(path: Path, sources: list[str]) -> Path:
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_markdown_cell("# Demand")] + [nbformat.v4.new_code_cell(s) for s in sources]
    nbformat.write(nb, path)
    return path


@pytest.fixture
def leaky(tmp_path):
    return write_nb(tmp_path / "demand.ipynb", [IMPORTS, DATA, FEATURES, SHUFFLED])


def test_only_temporal_shuffle_has_a_repair_contract():
    assert {fid for fid in load_taxonomy() if supported(fid)} == {"leakage-temporal-shuffle"}


def test_propose_writes_protocol_brief_and_snapshot(leaky, tmp_path):
    written, unsupported = propose(leaky, out_root=tmp_path / "repairs")
    assert unsupported == []
    assert [p.name for p in written] == ["demand--leakage-temporal-shuffle"]
    repair_dir = written[0]
    protocol = json.loads((repair_dir / "protocol.json").read_text())
    assert protocol["status"] == "proposed"
    assert protocol["edit_scope"] == [4]
    assert [(t["cell"], t["line"], t["sink"]) for t in protocol["targets"]] == [(4, 2, "cross_val_score")]
    assert (repair_dir / "original.ipynb").read_bytes() == leaky.read_bytes()
    brief = (repair_dir / "brief.md").read_text()
    assert "Edit scope: cells 4" in brief
    assert f"waldean verify {repair_dir.as_posix()}" in brief
    assert load_taxonomy()["leakage-temporal-shuffle"].repair_invariant in brief


def test_scope_includes_the_cell_that_builds_the_splitter(tmp_path):
    split_def = "kf = KFold(n_splits=5, shuffle=True, random_state=0)"
    sink = 'scores = cross_val_score(Ridge(), X, y, cv=kf)\nprint(f"R2={scores.mean():.3f}")'
    nb = write_nb(tmp_path / "split.ipynb", [IMPORTS, DATA, FEATURES, split_def, sink])
    written, _ = propose(nb, out_root=tmp_path / "repairs")
    protocol = json.loads((written[0] / "protocol.json").read_text())
    assert protocol["edit_scope"] == [4, 5]


def test_two_findings_in_one_file_share_one_contract(tmp_path):
    second = SHUFFLED.replace("kf", "kf2").replace("scores", "scores2")
    nb = write_nb(tmp_path / "two.ipynb", [IMPORTS, DATA, FEATURES, SHUFFLED, second])
    written, _ = propose(nb, out_root=tmp_path / "repairs")
    protocol = json.loads((written[0] / "protocol.json").read_text())
    assert len(written) == 1
    assert [t["cell"] for t in protocol["targets"]] == [4, 5]
    assert protocol["edit_scope"] == [4, 5]


def test_unsupported_class_is_listed_not_written(tmp_path):
    written, unsupported = propose(Path(__file__).parent.parent / "examples" / "leaky.ipynb",
                                   out_root=tmp_path / "repairs")
    assert written == []
    assert unsupported and all("no repair contract for this class yet" in u for u in unsupported)


def test_script_brief_names_file_lines(tmp_path):
    script = tmp_path / "demand.py"
    script.write_text("\n\n".join([IMPORTS, DATA, FEATURES, SHUFFLED]) + "\n", encoding="utf-8")
    written, _ = propose(script, out_root=tmp_path / "repairs")
    protocol = json.loads((written[0] / "protocol.json").read_text())
    assert protocol["targets"][0]["where"] == "line 15"
    assert "# %%" in render_brief(protocol, written[0])


def _repair(leaky, tmp_path):
    written, _ = propose(leaky, out_root=tmp_path / "repairs")
    return written[0]


def _fixed(tmp_path, sources, name="fixed.ipynb"):
    return write_nb(tmp_path / name, sources)


def test_temporal_fix_passes_static_checks(leaky, tmp_path):
    repair_dir = _repair(leaky, tmp_path)
    fixed = _fixed(tmp_path, [IMPORTS, DATA, FEATURES, TEMPORAL])
    evidence = verify(repair_dir, fixed)
    assert evidence["status"] == "static-pass"
    assert evidence["static"]["reasons"] == []
    assert evidence["execution"] is None
    assert json.loads((repair_dir / "evidence.json").read_text())["status"] == "static-pass"


def test_verify_defaults_to_the_proposed_file(leaky, tmp_path):
    repair_dir = _repair(leaky, tmp_path)
    write_nb(leaky, [IMPORTS, DATA, FEATURES, TEMPORAL])
    assert verify(repair_dir)["fixed"]["path"] == leaky.as_posix()
    assert verify(repair_dir)["status"] == "static-pass"


def test_unchanged_file_is_rejected(leaky, tmp_path):
    evidence = verify(_repair(leaky, tmp_path), leaky)
    assert evidence["status"] == "rejected"
    assert any("still reported at cell 4" in r for r in evidence["static"]["reasons"])


def test_import_line_outside_scope_is_allowed(leaky, tmp_path):
    imports = IMPORTS + "\nfrom sklearn.model_selection import TimeSeriesSplit"
    temporal = TEMPORAL.replace("from sklearn.model_selection import TimeSeriesSplit\n", "")
    fixed = _fixed(tmp_path, [imports, DATA, FEATURES, temporal])
    assert verify(_repair(leaky, tmp_path), fixed)["status"] == "static-pass"


def test_unshuffled_kfold_is_still_rejected(leaky, tmp_path):
    plain = SHUFFLED.replace("shuffle=True, random_state=0", "shuffle=False")
    evidence = verify(_repair(leaky, tmp_path), _fixed(tmp_path, [IMPORTS, DATA, FEATURES, plain]))
    assert evidence["status"] == "rejected"
    assert any("confidence 0.75" in r for r in evidence["static"]["reasons"])


def test_edit_outside_scope_is_rejected(leaky, tmp_path):
    trimmed = FEATURES + "\nX = X.iloc[:100]\ny = y.iloc[:100]"
    evidence = verify(_repair(leaky, tmp_path), _fixed(tmp_path, [IMPORTS, DATA, trimmed, TEMPORAL]))
    assert evidence["status"] == "rejected"
    assert "cell 3 changed outside the edit scope" in evidence["static"]["reasons"]


def test_stored_outputs_outside_scope_do_not_count(leaky, tmp_path):
    repair_dir = _repair(leaky, tmp_path)
    fixed = _fixed(tmp_path, [IMPORTS, DATA, FEATURES, TEMPORAL])
    nb = nbformat.read(fixed, as_version=4)
    nb.cells[2].outputs = [nbformat.v4.new_output("stream", text="rows: 400\n")]
    nbformat.write(nb, fixed)
    assert verify(repair_dir, fixed)["status"] == "static-pass"


def test_removed_evaluation_is_rejected(leaky, tmp_path):
    evidence = verify(_repair(leaky, tmp_path), _fixed(tmp_path, [IMPORTS, DATA, FEATURES, "scores = None"]))
    assert evidence["status"] == "rejected"
    assert "the evaluation call `cross_val_score` is no longer in the edit scope" in evidence["static"]["reasons"]


def test_added_cell_is_rejected(leaky, tmp_path):
    evidence = verify(_repair(leaky, tmp_path), _fixed(tmp_path, [IMPORTS, DATA, FEATURES, TEMPORAL, "pass"]))
    assert evidence["status"] == "rejected"
    assert evidence["static"]["reasons"] == ["cells were added, removed or retyped; this version compares cell by cell"]


def test_changed_snapshot_is_refused(leaky, tmp_path):
    repair_dir = _repair(leaky, tmp_path)
    (repair_dir / "original.ipynb").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="no longer matches"):
        verify(repair_dir, leaky)


R2 = re.compile(r"R2=(-?\d+\.\d+)")


def _with_stdout(nb_node, text):
    nb = copy.deepcopy(nb_node)
    nb.cells[-1].outputs = [nbformat.v4.new_output("stream", text=text)]
    return nb


def test_scrubbed_env_hides_and_restores_secrets(monkeypatch):
    monkeypatch.setenv("WALDEAN_TEST_TOKEN", "s3cret")
    monkeypatch.setenv("WALDEAN_TEST_PLAIN", "ok")
    with scrubbed_env() as removed:
        assert "WALDEAN_TEST_TOKEN" in removed
        assert "WALDEAN_TEST_TOKEN" not in os.environ
        assert os.environ["WALDEAN_TEST_PLAIN"] == "ok"
    assert os.environ["WALDEAN_TEST_TOKEN"] == "s3cret"


def test_metric_values_reads_stream_lines_only():
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_code_cell("x")]
    nb.cells[0].outputs = [
        nbformat.v4.new_output("stream", text="R2=0.992 MAE=2.98\nnoise\nR2=0.465\n"),
        nbformat.v4.new_output("execute_result", data={"text/plain": "R2=0.111"}),
    ]
    assert metric_values(nb, R2) == [0.992, 0.465]


def _fake_execute(calls, outputs):
    def fake(nb_node, timeout=180, cwd=None, kernel_name="python3"):
        calls.append({"cwd": cwd, "kernel_name": kernel_name, "timeout": timeout})
        return _with_stdout(nb_node, outputs[len(calls) - 1])
    return fake


def test_counterfactual_measures_both_runs(leaky, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("waldean.execute.execute", _fake_execute(calls, ["R2=0.992\n", "R2=0.465\n"]))
    repair_dir = _repair(leaky, tmp_path)
    fixed = _fixed(tmp_path, [IMPORTS, DATA, FEATURES, TEMPORAL])
    evidence = verify(repair_dir, fixed, metric=R2, timeout=30)
    assert evidence["status"] == "verified"
    assert evidence["execution"]["before"] == [0.992]
    assert evidence["execution"]["after"] == [0.465]
    assert evidence["execution"]["delta"] == [-0.527]
    assert [c["kernel_name"] for c in calls] == ["waldean-verify", "waldean-verify"]
    assert {c["cwd"] for c in calls} == {str(fixed.resolve().parent)}


def test_counterfactual_is_not_run_after_rejection(leaky, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("waldean.execute.execute", _fake_execute(calls, ["R2=0.9\n", "R2=0.9\n"]))
    evidence = verify(_repair(leaky, tmp_path), leaky, metric=R2)
    assert evidence["status"] == "rejected"
    assert calls == []


def test_mismatched_metric_lines_are_inconclusive(leaky, tmp_path, monkeypatch):
    monkeypatch.setattr("waldean.execute.execute", _fake_execute([], ["R2=0.9\nR2=0.8\n", "R2=0.5\n"]))
    fixed = _fixed(tmp_path, [IMPORTS, DATA, FEATURES, TEMPORAL])
    evidence = verify(_repair(leaky, tmp_path), fixed, metric=R2)
    assert evidence["status"] == "inconclusive"
    assert "different number of lines" in evidence["execution"]["error"]


def test_execution_error_is_inconclusive(leaky, tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("cell 3 failed\nTraceback ...")
    monkeypatch.setattr("waldean.execute.execute", boom)
    fixed = _fixed(tmp_path, [IMPORTS, DATA, FEATURES, TEMPORAL])
    evidence = verify(_repair(leaky, tmp_path), fixed, metric=R2)
    assert evidence["status"] == "inconclusive"
    assert evidence["execution"]["error"] == "RuntimeError: cell 3 failed"


def test_live_counterfactual_hides_secrets(tmp_path, monkeypatch):
    pytest.importorskip("nbclient")
    monkeypatch.setenv("WALDEAN_TEST_TOKEN", "s3cret")
    probe = 'import os\nprint(f"LEAK={int(bool(os.environ.get(\'WALDEAN_TEST_TOKEN\')))}.0")'
    a = write_nb(tmp_path / "a.ipynb", [probe])
    b = write_nb(tmp_path / "b.ipynb", [probe])
    run = counterfactual(a, b, re.compile(r"LEAK=(\d\.\d)"), timeout=60)
    if run["error"] and "kernel" in run["error"].lower():
        pytest.skip(run["error"])
    assert run["complete"], run["error"]
    assert run["before"] == run["after"] == [0.0]
