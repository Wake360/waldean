import json

import pytest

MINIMAL_NB = json.dumps(
    {"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
)


@pytest.fixture
def fake_corpus(tmp_path):
    """Two-notebook corpus: one clean, one fit-before-split mutant."""
    (tmp_path / "clean").mkdir()
    (tmp_path / "mutated").mkdir()
    (tmp_path / "clean" / "c.ipynb").write_text(MINIMAL_NB)
    (tmp_path / "mutated" / "m.ipynb").write_text(MINIMAL_NB)
    manifest = {
        "built": "2026-08-01",
        "provenance": {},
        "clean": [{"file": "clean/c.ipynb", "family": "t", "seed": 1, "split": "dev"}],
        "mutants": [{
            "file": "mutated/m.ipynb",
            "base": "clean/c.ipynb",
            "flaw_id": "leakage-fit-before-split",
            "mutation_seed": 0,
            "split": "dev",
            "verified": True,
            "evidence": {},
        }],
        "discarded": [],
    }
    (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest))
    return tmp_path
