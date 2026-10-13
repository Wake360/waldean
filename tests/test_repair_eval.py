import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "corpus"


def _load():
    spec = importlib.util.spec_from_file_location("repair_eval", REPO / "scripts" / "repair_eval.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not (CORPUS / "MANIFEST.json").exists(), reason="corpus not built")
def test_verifier_separates_true_repairs_from_bad_ones():
    repair_eval = _load()
    rows = repair_eval.run(CORPUS, execute=False)
    assert len(rows) == 16
    for row in rows:
        assert row["contracts"] == 1, row
        for case, expected in repair_eval.EXPECTED.items():
            assert row[case] == expected, (row["mutant"], case)
