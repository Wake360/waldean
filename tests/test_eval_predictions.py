import json

import pytest

from wald.eval import evaluate_predictions


def _preds_file(tmp_path, preds):
    p = tmp_path / "preds.json"
    p.write_text(json.dumps(preds))
    return p


def test_oracle_predictions_score_perfect(fake_corpus):
    p = _preds_file(fake_corpus, {
        "mutated/m.ipynb": [{"flaw_id": "leakage-fit-before-split", "confidence": 1.0}],
    })
    r = evaluate_predictions(fake_corpus, p)
    c = r["static_classes"]["leakage-fit-before-split"]
    assert (c["tp"], c["fn"], c["fp"]) == (1, 0, 0)
    assert r["clean_fp_rate"] == 0.0
    assert r["predictions_file"] == str(p)


def test_flag_on_clean_counts_as_fp(fake_corpus):
    p = _preds_file(fake_corpus, {
        "clean/c.ipynb": [{"flaw_id": "leakage-fit-before-split"}],
    })
    r = evaluate_predictions(fake_corpus, p)
    c = r["static_classes"]["leakage-fit-before-split"]
    assert c["fp"] == 1 and c["fn"] == 1  # missed the mutant, flagged the clean
    assert r["clean_fp_files"] == ["clean/c.ipynb"]


def test_below_floor_prediction_is_a_miss(fake_corpus):
    p = _preds_file(fake_corpus, {
        "mutated/m.ipynb": [{"flaw_id": "leakage-fit-before-split", "confidence": 0.2}],
    })
    r = evaluate_predictions(fake_corpus, p, floor=0.5)
    c = r["static_classes"]["leakage-fit-before-split"]
    assert (c["tp"], c["fn"]) == (0, 1)


def test_unknown_file_rejected(fake_corpus):
    p = _preds_file(fake_corpus, {"mutated/typo.ipynb": []})
    with pytest.raises(SystemExit, match="typo"):
        evaluate_predictions(fake_corpus, p)
