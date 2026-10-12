import importlib.util
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
