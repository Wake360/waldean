import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


conv = _load("scicode_to_predictions")


def _result(root, rel, findings, error=None):
    r = {"file": str(root / rel), "findings": findings, "summary": {}}
    if error:
        r["error"] = error
    return r


def test_convert_maps_ids(fake_corpus):
    results = [
        _result(fake_corpus, "mutated/m.ipynb", [{"id": "ml-001", "confidence": 0.9}]),
        _result(fake_corpus, "clean/c.ipynb", [{"id": "ml-005-cv-temporal-shuffle", "confidence": 0.9}]),
    ]
    preds = conv.convert(results, fake_corpus)
    assert preds["mutated/m.ipynb"] == [{"flaw_id": "leakage-fit-before-split", "confidence": 1.0}]
    assert preds["clean/c.ipynb"] == [{"flaw_id": "leakage-temporal-shuffle", "confidence": 1.0}]


def test_convert_ignores_scicode_confidence(fake_corpus):
    results = [
        _result(fake_corpus, "mutated/m.ipynb", [{"id": "ml-007", "confidence": 0.5}]),
        _result(fake_corpus, "clean/c.ipynb", []),
    ]
    assert conv.convert(results, fake_corpus)["mutated/m.ipynb"][0]["confidence"] == 1.0


def test_convert_drops_unmapped_ids(fake_corpus):
    results = [
        _result(fake_corpus, "mutated/m.ipynb", [{"id": "rep-004", "confidence": 0.9}]),
        _result(fake_corpus, "clean/c.ipynb", [{"id": "pt-007", "confidence": 0.9}]),
    ]
    assert conv.convert(results, fake_corpus) == {"mutated/m.ipynb": [], "clean/c.ipynb": []}


def test_convert_rejects_errored_file(fake_corpus):
    results = [
        _result(fake_corpus, "mutated/m.ipynb", [], error={"error_type": "ContextLengthError"}),
        _result(fake_corpus, "clean/c.ipynb", []),
    ]
    with pytest.raises(ValueError, match="mutated/m.ipynb"):
        conv.convert(results, fake_corpus)


def test_convert_rejects_missing_file(fake_corpus):
    results = [_result(fake_corpus, "clean/c.ipynb", [])]
    with pytest.raises(ValueError, match="mutated/m.ipynb"):
        conv.convert(results, fake_corpus)


yang = _load("yang_eval")


def test_notebook_path_maps_label_to_zip_member(tmp_path):
    got = yang.notebook_path("GitHub-data/notebooks/2021-09-05/nb_1244.py", tmp_path)
    assert got == tmp_path / "2021-09-05-nb_1244.ipynb"


def test_confusion_reads_label_prefix():
    rows = [
        {"nb": "a", "pre": "Y (MinMaxScaler)"},
        {"nb": "b", "pre": "N [no model]"},
        {"nb": "c", "pre": "Y"},
        {"nb": "d", "pre": "N"},
    ]
    assert yang.confusion(rows, {"a", "b"}) == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}


def test_score_counts_errors_as_unflagged():
    rows = [{"nb": "a", "pre": "Y"}, {"nb": "b", "pre": "N"}]
    s = yang.score(rows, {"a": "error", "b": "clean"})
    assert s["confusion"] == {"tp": 0, "fp": 0, "fn": 1, "tn": 1}
    assert s["errors"] == ["a"]


def test_render_header_counts_rows_without_pre_label():
    rows = [{"nb": "a", "pre": "Y"}, {"nb": "b", "pre": ""}, {"nb": "c", "pre": "N"}]
    out = yang.render(yang.score(rows, {"a": "flagged", "b": "clean", "c": "clean"}), rows)
    assert "3 notebooks, 2 with a `pre` label; the 1 without one count as negatives" in out


def test_render_header_omits_unlabeled_clause_when_all_labeled():
    rows = [{"nb": "a", "pre": "Y"}, {"nb": "c", "pre": "N"}]
    out = yang.render(yang.score(rows, {"a": "flagged", "c": "clean"}), rows)
    assert "2 notebooks, 2 with a `pre` label;" in out
    assert "without one" not in out


def test_run_waldean_exit_3_is_error(monkeypatch, tmp_path):
    monkeypatch.setattr(yang.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 3, "", "too big"))
    assert yang.run_waldean(tmp_path / "x.ipynb") == "error"


def test_run_waldean_crash_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(yang.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "Traceback"))
    with pytest.raises(json.JSONDecodeError):
        yang.run_waldean(tmp_path / "x.ipynb")
