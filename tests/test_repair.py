import json
from pathlib import Path

import nbformat
import pytest

from waldean.repair import propose, render_brief, supported
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
