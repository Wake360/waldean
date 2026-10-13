import importlib.util
import json
import re
import shutil
from pathlib import Path

import nbformat
import pytest

from waldean.cli import main

REPO = Path(__file__).parent.parent
DEMO_REL = "examples/temporal-cv-before-after.ipynb"
DEMO = REPO / DEMO_REL
GOLDEN = Path(__file__).parent / "golden" / "temporal-cv.md"
LINE_RE = re.compile(r"R2=(-?\d+\.\d+) MAE=(\d+\.\d+)")


def _load_build_script():
    spec = importlib.util.spec_from_file_location("build_temporal_demo", REPO / "scripts" / "build_temporal_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metrics(nb):
    lines = _load_build_script().metric_lines(nb)
    assert len(lines) == 2
    return [tuple(float(v) for v in LINE_RE.search(ln).groups()) for ln in lines]


def test_demo_flags_only_the_shuffled_protocol(monkeypatch, capsys):
    monkeypatch.chdir(REPO)
    rc = main(["check", DEMO_REL, "--format", "json"])
    report = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert [f["flaw_id"] for f in report["flags"]] == ["leakage-temporal-shuffle"]
    nb = nbformat.read(DEMO, as_version=4)
    assert "cv=kf" in nb.cells[report["flags"][0]["cell"]].source


def test_demo_check_matches_golden(monkeypatch, capsys):
    monkeypatch.chdir(REPO)
    main(["check", DEMO_REL])
    assert capsys.readouterr().out == GOLDEN.read_text(encoding="utf-8")


def test_demo_outputs_show_the_measured_gap():
    (r2_shuffled, mae_shuffled), (r2_temporal, mae_temporal) = _metrics(nbformat.read(DEMO, as_version=4))
    assert r2_shuffled - r2_temporal >= 0.3
    assert mae_temporal >= 2 * mae_shuffled


def test_demo_rebuild_matches_stored_metrics():
    pytest.importorskip("sklearn")
    from waldean.execute import execute

    stored = _metrics(nbformat.read(DEMO, as_version=4))
    try:
        rebuilt = _metrics(execute(_load_build_script().build(), timeout=600))
    except Exception as e:
        pytest.skip(f"no kernel available: {e}")
    stored_flat = [v for pair in stored for v in pair]
    rebuilt_flat = [v for pair in rebuilt for v in pair]
    assert rebuilt_flat == pytest.approx(stored_flat, rel=0.05)


LEAKY = REPO / "examples" / "temporal-cv-leaky.ipynb"


def _repair_leaky_demo(tmp_path):
    from waldean.repair import propose

    work = tmp_path / "demand.ipynb"
    shutil.copyfile(LEAKY, work)
    written, unsupported = propose(work, out_root=tmp_path / "repairs")
    assert unsupported == []
    assert len(written) == 1
    nb = nbformat.read(work, as_version=4)
    nb.cells[4].source = _load_build_script().AFTER
    nbformat.write(nb, work)
    return written[0]


def test_leaky_demo_matches_build_script():
    stored = [c.source for c in nbformat.read(LEAKY, as_version=4).cells]
    assert stored == [c.source for c in _load_build_script().build_leaky().cells]


def test_leaky_demo_repair_passes_static_checks(tmp_path):
    from waldean.repair import verify

    repair_dir = _repair_leaky_demo(tmp_path)
    assert json.loads((repair_dir / "protocol.json").read_text())["edit_scope"] == [4]
    assert verify(repair_dir)["status"] == "static-pass"


def test_leaky_demo_repair_measures_the_gap(tmp_path):
    pytest.importorskip("sklearn")
    from waldean.repair import verify

    evidence = verify(_repair_leaky_demo(tmp_path), metric=re.compile(r"R2=(-?\d+\.\d+)"))
    run = evidence["execution"]
    if run["error"] and "kernel" in run["error"].lower():
        pytest.skip(run["error"])
    assert evidence["status"] == "verified", run["error"]
    (before,), (after,) = run["before"], run["after"]
    stored = _metrics(nbformat.read(DEMO, as_version=4))
    assert before == pytest.approx(stored[0][0], rel=0.05)
    assert after == pytest.approx(stored[1][0], rel=0.05)
