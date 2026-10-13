import json

import pytest

from waldean.bench.eval import evaluate_predictions, load_predictions


def _preds(tmp_path, preds):
    p = tmp_path / "preds.json"
    p.write_text(json.dumps(preds))
    return load_predictions(p)


def test_oracle_predictions_score_perfect(fake_corpus):
    preds = _preds(fake_corpus, {
        "mutated/m.ipynb": [{"flaw_id": "leakage-fit-before-split", "confidence": 1.0}],
    })
    r = evaluate_predictions(fake_corpus, preds)
    c = r["static_classes"]["leakage-fit-before-split"]
    assert (c["tp"], c["fn"], c["fp"]) == (1, 0, 0)
    assert r["clean_fp_rate"] == 0.0


def test_flag_on_clean_counts_as_fp_and_mutant_as_miss(fake_corpus):
    preds = _preds(fake_corpus, {
        "clean/c.ipynb": [{"flaw_id": "leakage-fit-before-split"}],
    })
    r = evaluate_predictions(fake_corpus, preds)
    c = r["static_classes"]["leakage-fit-before-split"]
    assert c["fp"] == 1 and c["fn"] == 1
    assert r["clean_fp_files"] == ["clean/c.ipynb"]


def test_below_floor_prediction_is_a_miss(fake_corpus):
    preds = _preds(fake_corpus, {
        "mutated/m.ipynb": [{"flaw_id": "leakage-fit-before-split", "confidence": 0.2}],
    })
    r = evaluate_predictions(fake_corpus, preds, floor=0.5)
    c = r["static_classes"]["leakage-fit-before-split"]
    assert (c["tp"], c["fn"]) == (0, 1)


def test_unknown_file_rejected(fake_corpus):
    preds = _preds(fake_corpus, {"mutated/typo.ipynb": []})
    with pytest.raises(SystemExit, match="typo"):
        evaluate_predictions(fake_corpus, preds)
