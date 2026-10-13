import json
import sys
from pathlib import Path

import pytest

from waldean.api import EmptyDir as _EmptyDir, expand_notebooks as _expand_notebooks
from waldean.cli import main
from waldean.llm.backends import BackendError

REPO = Path(__file__).parent.parent
LEAKY = str(REPO / "examples" / "leaky.ipynb")
LEAKY_PY = str(REPO / "examples" / "leaky.py")
GOLDEN = Path(__file__).parent / "golden" / "leaky.md"
GOLDEN_PY = Path(__file__).parent / "golden" / "leaky-py.md"

CLEAN_NB = json.dumps({"cells": [
    {"cell_type": "code", "source": "x = 1\n", "outputs": [],
     "execution_count": None, "metadata": {}},
], "metadata": {}, "nbformat": 4, "nbformat_minor": 5})


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


class _Det:
    provider = "anthropic"
    model = "det"
    kind = "api"

    @property
    def gate_eligible(self):
        return True

    def complete(self, system, user, schema=None):
        raise BackendError("upstream 503")


class _Ver:
    provider = "openai"
    model = "ver"
    kind = "api"

    @property
    def gate_eligible(self):
        return True

    def complete(self, system, user, schema=None):
        return {"verdict": "unsupported", "reason": "x"}


class _OkDet:
    provider = "anthropic"
    model = "det"
    kind = "api"

    @property
    def gate_eligible(self):
        return True

    def complete(self, system, user, schema=None):
        return {"claims": [], "findings": []}


def test_cli_llm_run_reports_narrative_provenance(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "y")
    monkeypatch.setattr("waldean.cli.llm_backends", lambda rd, subscription=False: (_OkDet(), _Ver()))
    nb = {"cells": [
        {"cell_type": "code", "source": "x = 1\n", "outputs": [],
         "execution_count": None, "metadata": {}},
    ], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
    p = _write(tmp_path, "clean.ipynb", json.dumps(nb))
    rc = main(["check", "--llm", p])
    out = capsys.readouterr().out
    assert "static + narrative layers" in out  # provenance reflects the --llm run
    assert rc == 0


def test_cli_llm_backend_failure_exits_3_fail_loud(monkeypatch, capsys):
    # an api outage during `check --llm` must not read like a clean notebook:
    # the dropped backend error propagates to the CLI, which exits 3.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "y")
    monkeypatch.setattr("waldean.cli.llm_backends", lambda rd, subscription=False: (_Det(), _Ver()))
    assert main(["check", "--llm", LEAKY]) == 3
    err = capsys.readouterr().err
    assert "narrative layer failed" in err
    assert "Traceback" not in err


def test_valid_json_missing_cells_exits_3(tmp_path, capsys):
    # valid JSON but not a notebook (no top-level "cells"): nbformat raises a
    # jsonschema ValidationError, which must still map to the exit-3 error path
    p = _write(tmp_path, "nocells.ipynb", '{"hello": "world"}')
    assert main(["check", p]) == 3
    err = capsys.readouterr().err
    assert err.startswith("waldean: ")
    assert "Traceback" not in err


def test_valid_json_missing_cells_json_format_exits_3(tmp_path, capsys):
    p = _write(tmp_path, "nocells.ipynb", '{"hello": "world"}')
    assert main(["check", "--format", "json", p]) == 3


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert capsys.readouterr().out.startswith("waldean ")


def test_version_short_flag(capsys):
    with pytest.raises(SystemExit) as e:
        main(["-V"])
    assert e.value.code == 0
    assert capsys.readouterr().out.startswith("waldean ")


def test_format_sarif_accepted_and_valid_json(tmp_path, capsys):
    nb = {"cells": [
        {"cell_type": "code", "source": "x = 1\n", "outputs": [],
         "execution_count": None, "metadata": {}},
    ], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
    p = _write(tmp_path, "clean.ipynb", json.dumps(nb))
    rc = main(["check", "--format", "sarif", p])
    data = json.loads(capsys.readouterr().out)  # must be a single valid JSON document
    assert data["version"] == "2.1.0"
    assert rc == 0


# --- WS1: TTY color -------------------------------------------------------


def test_check_color_absent_when_piped(capsys):
    rc = main(["check", LEAKY])
    out = capsys.readouterr().out
    assert out.startswith("# Waldean report")
    assert "\x1b[" not in out
    assert rc == 2


def test_check_color_present_on_tty(monkeypatch, capsys):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    main(["check", LEAKY])
    out = capsys.readouterr().out
    assert "\x1b[31m## HIGH:" in out
    assert "\x1b[2m## CLEAN (checked):" in out


def test_check_color_honors_no_color(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    main(["check", LEAKY])
    assert "\x1b[" not in capsys.readouterr().out


def test_check_piped_matches_golden(monkeypatch, capsys):
    monkeypatch.chdir(REPO)
    main(["check", "examples/leaky.ipynb"])
    assert capsys.readouterr().out == GOLDEN.read_text(encoding="utf-8")


# --- WS3: .py script support ------------------------------------------------


def test_check_py_md_reports_absolute_lines(tmp_path, capsys):
    src = (
        "# %% [markdown]\n# header\n# %%\n"
        "from sklearn.preprocessing import StandardScaler\n"
        "from sklearn.model_selection import train_test_split\n"
        "s = StandardScaler()\n"
        "X = s.fit_transform(X)\n"
        "X_tr, X_te = train_test_split(X, y)\n"
    )
    p = _write(tmp_path, "leak.py", src)
    rc = main(["check", p])
    out = capsys.readouterr().out
    assert rc == 2
    # fit_transform is on file line 7 (cell 1 starts at file line 4)
    assert "- **Where:** cell 1, line 7" in out


def test_check_py_sarif_startline_absolute(capsys):
    rc = main(["check", "--format", "sarif", LEAKY_PY])
    assert rc == 2
    sarif = json.loads(capsys.readouterr().out)
    result = sarif["runs"][0]["results"][0]
    assert result["locations"][0]["physicalLocation"]["region"]["startLine"] == 44
    assert "cell 5, line 44" in result["message"]["text"]
    assert result["properties"]["cell"] == 5


def test_py_json_line_is_file_absolute(capsys):
    rc = main(["check", "--format", "json", LEAKY_PY])
    assert rc == 2
    data = json.loads(capsys.readouterr().out)
    flag = data["flags"][0]
    assert flag["cell"] == 5 and flag["line"] == 44  # line is file-absolute


def test_py_oversized_single_cell_warns_partial(tmp_path, capsys):
    from waldean.analysis.dataflow import MAX_CELL_SOURCE_BYTES

    big = "a = 1  # " + "A" * (MAX_CELL_SOURCE_BYTES + 1) + "\n"
    p = _write(tmp_path, "big.py", big)
    rc = main(["check", p])
    out = capsys.readouterr().out
    assert rc == 0  # a skipped cell does not raise severity
    assert "results are partial" in out


def test_leaky_py_example_exits_2(monkeypatch, capsys):
    monkeypatch.chdir(REPO)
    rc = main(["check", "examples/leaky.py"])
    assert rc == 2
    assert capsys.readouterr().out == GOLDEN_PY.read_text(encoding="utf-8")


def test_expand_notebooks_ignores_py_in_dirs(tmp_path, capsys):
    (tmp_path / "a.py").write_text("x = 1\n")  # directory has .py but no .ipynb
    rc = main(["check", str(tmp_path)])
    assert rc == 3
    assert capsys.readouterr().err == f"waldean: {tmp_path}: no .ipynb files found\n"


# --- WS2: directory recursion ----------------------------------------------


def test_expand_notebooks_sorted_and_skips_checkpoints(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / ".ipynb_checkpoints").mkdir()
    _write(tmp_path, "b.ipynb", CLEAN_NB)
    _write(tmp_path / "sub", "a.ipynb", CLEAN_NB)
    _write(tmp_path / ".ipynb_checkpoints", "b-checkpoint.ipynb", CLEAN_NB)
    got = _expand_notebooks([str(tmp_path), LEAKY])
    assert got == [str(tmp_path / "b.ipynb"), str(tmp_path / "sub" / "a.ipynb"), LEAKY]


def test_check_empty_dir_exits_3(tmp_path, capsys):
    d = tmp_path / "empty"
    d.mkdir()
    rc = main(["check", str(d)])
    assert rc == 3
    assert capsys.readouterr().err == f"waldean: {d}: no .ipynb files found\n"


def test_heldout_dir_refusal(tmp_path, capsys):
    (tmp_path / "clean").mkdir()
    (tmp_path / "clean" / "foo.ipynb").write_text(CLEAN_NB)
    (tmp_path / "MANIFEST.json").write_text(json.dumps({
        "clean": [{"file": "clean/foo.ipynb", "split": "heldout"}], "mutants": [],
    }))
    (tmp_path / "replay" / "detector").mkdir(parents=True)
    (tmp_path / "replay" / "verifier").mkdir(parents=True)
    rc = main([
        "check", "--llm", "--replay-dir", str(tmp_path / "replay"),
        str(tmp_path / "clean"),
    ])
    assert rc == 3
    assert "held-out corpus notebook is gate-only" in capsys.readouterr().err


def test_check_dir_abort_on_unreadable(tmp_path, capsys):
    _write(tmp_path, "a_good.ipynb", CLEAN_NB)
    _write(tmp_path, "b_bad.ipynb", "{not json")
    rc = main(["check", str(tmp_path)])
    out, err = capsys.readouterr()
    assert rc == 3
    assert out.count("# Waldean report") == 1
    assert err.startswith("waldean: ")


def test_check_dir_recurse_reports_all_worst_exit(tmp_path, capsys):
    _write(tmp_path, "a_leaky.ipynb", Path(LEAKY).read_text())
    _write(tmp_path, "b_clean.ipynb", CLEAN_NB)
    rc = main(["check", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 2
    assert out.count("# Waldean report") == 2
    assert out.index("a_leaky.ipynb") < out.index("b_clean.ipynb")


# --- WS3: multi-file roll-up ------------------------------------------------


def test_rollup_on_tty_not_piped(monkeypatch, tmp_path, capsys):
    _write(tmp_path, "a_leaky.ipynb", Path(LEAKY).read_text())
    _write(tmp_path, "b_clean.ipynb", CLEAN_NB)
    main(["check", str(tmp_path)])
    piped_out, piped_err = capsys.readouterr()
    assert "checked " not in piped_err

    monkeypatch.setenv("NO_COLOR", "1")  # isolate roll-up from color
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    main(["check", str(tmp_path)])
    tty_out, tty_err = capsys.readouterr()
    assert "checked 2 notebooks: 1 high, 0 medium, 1 clean\n" in tty_err
    assert tty_out == piped_out  # roll-up never touches stdout


def test_rollup_buckets_by_severity_under_medium_gate(monkeypatch, tmp_path, capsys):
    from waldean.core.flag import Flag

    medium = Flag(flaw_id="testing-multiple-uncorrected", severity="medium",
                  confidence=0.9, cell=1, line=1, evidence="e",
                  failure_scenario="f", fix="x")
    monkeypatch.setattr("waldean.api.run_static", lambda nb, flow: [medium])
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    _write(tmp_path, "a.ipynb", CLEAN_NB)
    _write(tmp_path, "b.ipynb", CLEAN_NB)
    rc = main(["check", "--severity-gate", "medium", str(tmp_path)])
    err = capsys.readouterr().err
    assert rc == 2  # medium at the medium gate exits 2 ...
    assert "checked 2 notebooks: 0 high, 2 medium, 0 clean" in err  # ... but buckets stay medium


def test_rollup_never_for_json_even_on_tty(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    _write(tmp_path, "a.ipynb", CLEAN_NB)
    _write(tmp_path, "b.ipynb", CLEAN_NB)
    main(["check", "--format", "json", str(tmp_path)])
    out, err = capsys.readouterr()
    assert "checked " not in err
    json.loads(out)  # stdout stays one valid JSON document


# --- WS4: --llm progress ----------------------------------------------------


def test_llm_progress_on_tty_stderr_only(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "y")
    monkeypatch.setattr("waldean.cli.llm_backends", lambda rd, subscription=False: (_OkDet(), _Ver()))
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    _write(tmp_path, "a.ipynb", CLEAN_NB)
    _write(tmp_path, "b.ipynb", CLEAN_NB)
    main(["check", "--llm", str(tmp_path)])
    out, err = capsys.readouterr()
    assert "checking 1/2" in err
    assert "checking 2/2" in err
    assert "checking" not in out
    assert err.count("\n") == 1  # \r-overwrite, single close newline


def test_llm_progress_absent_when_piped(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "y")
    monkeypatch.setattr("waldean.cli.llm_backends", lambda rd, subscription=False: (_OkDet(), _Ver()))
    p = _write(tmp_path, "a.ipynb", CLEAN_NB)
    main(["check", "--llm", p])
    assert "checking" not in capsys.readouterr().err


def test_llm_progress_closed_before_backend_error(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "y")
    monkeypatch.setattr("waldean.cli.llm_backends", lambda rd, subscription=False: (_Det(), _Ver()))
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    rc = main(["check", "--llm", LEAKY])
    err = capsys.readouterr().err
    assert rc == 3
    assert "\nwaldean: narrative layer failed" in err  # error starts on a fresh line


# --- WS5: user-facing string pins -------------------------------------------


def test_help_pins_exit_code_line(capsys):
    with pytest.raises(SystemExit) as e:
        main(["check", "--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "exit codes: 0 clean, 1 medium, 2 high, 3 input or usage error" in out
    assert "notebook files or directories" in out


def test_message_no_such_file(capsys):
    rc = main(["check", "missing.ipynb"])
    assert rc == 3
    assert capsys.readouterr().err == "waldean: missing.ipynb: no such file\n"


def test_message_directory_not_notebook():
    # unreachable from the CLI since directory expansion landed; pinned at
    # unit level so the wording stays stable for any future caller
    from waldean.cli import _input_error

    assert _input_error(IsADirectoryError()) == "is a directory, not a notebook"


def test_message_llm_missing_keys(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    rc = main(["check", "--llm", LEAKY])
    assert rc == 3
    assert capsys.readouterr().err == (
        "waldean: --llm needs ANTHROPIC_API_KEY and OPENAI_API_KEY set in the environment\n"
    )


def test_eval_llm_missing_keys_exits_3(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    rc = main(["eval", "--llm", "--split", "dev"])
    assert rc == 3
    assert capsys.readouterr().err == (
        "waldean: --llm needs ANTHROPIC_API_KEY and OPENAI_API_KEY set in the environment\n"
    )


def test_eval_llm_subscription_heldout_refused_before_backends(monkeypatch, capsys):
    # --llm-subscription can never produce gate evidence (kind="agent"); refuse
    # the heldout split up front rather than let the eval.py raise do it, and
    # do so before _llm_backends is even called (no API keys needed to trip).
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    called = []
    monkeypatch.setattr("waldean.cli.llm_backends", lambda rd, subscription=False: called.append(1))
    rc = main(["eval", "--llm", "--llm-subscription", "--split", "heldout"])
    assert rc == 3
    assert "subscription runs cannot produce gate evidence" in capsys.readouterr().err
    assert called == []


def test_llm_backends_subscription_ignores_replay_dir(monkeypatch, tmp_path):
    from waldean.api import llm_backends as _llm_backends
    from waldean.llm.backends import AgentBackend, CodexBackend

    det, ver = _llm_backends(str(tmp_path / "replay"), subscription=True)
    assert isinstance(det, AgentBackend)
    assert isinstance(ver, CodexBackend)
    assert not (tmp_path / "replay").exists()  # never wrapped in ReplayBackend


def test_heldout_refusal_has_prefix_and_exits_3(tmp_path, capsys):
    (tmp_path / "clean").mkdir()
    (tmp_path / "clean" / "foo.ipynb").write_text(
        '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}'
    )
    (tmp_path / "MANIFEST.json").write_text(json.dumps({
        "clean": [{"file": "clean/foo.ipynb", "split": "heldout"}], "mutants": [],
    }))
    (tmp_path / "replay" / "detector").mkdir(parents=True)
    (tmp_path / "replay" / "verifier").mkdir(parents=True)
    rc = main([
        "check", "--llm", "--replay-dir", str(tmp_path / "replay"),
        str(tmp_path / "clean" / "foo.ipynb"),
    ])
    assert rc == 3
    assert capsys.readouterr().err.startswith("waldean: ")


# --- WS5: --keep-going ------------------------------------------------------


def test_keep_going_mixed_batch_reports_good_exits_3(tmp_path, capsys):
    _write(tmp_path, "a_good.ipynb", CLEAN_NB)
    _write(tmp_path, "b_bad.ipynb", "{not json")
    _write(tmp_path, "c_good.ipynb", CLEAN_NB)
    rc = main(["check", "--keep-going", str(tmp_path)])
    out, err = capsys.readouterr()
    assert rc == 3
    assert out.count("# Waldean report") == 2
    assert err.count("waldean: ") == 1


def test_keep_going_all_fail_exits_3(tmp_path, capsys):
    _write(tmp_path, "a_bad.ipynb", "{not json")
    _write(tmp_path, "b_bad.ipynb", "{also not json")
    rc = main(["check", "--keep-going", str(tmp_path)])
    out, err = capsys.readouterr()
    assert rc == 3
    assert out.count("# Waldean report") == 0
    assert err.count("waldean: ") == 2


def test_keep_going_high_plus_failure_exits_3(tmp_path, capsys):
    _write(tmp_path, "a_leaky.ipynb", Path(LEAKY).read_text())
    _write(tmp_path, "b_bad.ipynb", "{not json")
    rc = main(["check", "--keep-going", str(tmp_path)])
    assert rc == 3  # a high finding alone would exit 2; a failure forces 3


def test_keep_going_json_array_with_failure(tmp_path, capsys):
    _write(tmp_path, "a_good.ipynb", CLEAN_NB)
    _write(tmp_path, "b_bad.ipynb", "{not json")
    rc = main(["check", "--keep-going", "--format", "json", str(tmp_path)])
    data = json.loads(capsys.readouterr().out)
    assert rc == 3
    assert isinstance(data, list)
    assert len(data) == 1


def test_keep_going_json_single_success_bare_object(tmp_path, capsys):
    p = _write(tmp_path, "clean.ipynb", CLEAN_NB)
    rc = main(["check", "--keep-going", "--format", "json", p])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert isinstance(data, dict)  # back-compat: single notebook stays a bare object


def test_keep_going_rollup_counts_failures_on_tty(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    _write(tmp_path, "a_leaky.ipynb", Path(LEAKY).read_text())
    _write(tmp_path, "b_clean.ipynb", CLEAN_NB)
    _write(tmp_path, "c_bad.ipynb", "{not json")
    main(["check", "--keep-going", str(tmp_path)])
    err = capsys.readouterr().err
    assert "checked 3 notebooks: 1 high, 0 medium, 1 clean, 1 failed" in err


def test_keep_going_llm_backend_error_still_hard_aborts(monkeypatch, capsys):
    # the --llm backend-error abort must never soften, even with --keep-going.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "y")
    monkeypatch.setattr("waldean.cli.llm_backends", lambda rd, subscription=False: (_Det(), _Ver()))
    rc = main(["check", "--llm", "--keep-going", LEAKY])
    err = capsys.readouterr().err
    assert rc == 3
    assert "narrative layer failed" in err


def test_keep_going_heldout_refusal_still_aborts(tmp_path, capsys):
    # the held-out gate-only refusal must never soften, even with --keep-going.
    (tmp_path / "clean").mkdir()
    (tmp_path / "clean" / "foo.ipynb").write_text(
        '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}'
    )
    (tmp_path / "MANIFEST.json").write_text(json.dumps({
        "clean": [{"file": "clean/foo.ipynb", "split": "heldout"}], "mutants": [],
    }))
    (tmp_path / "replay" / "detector").mkdir(parents=True)
    (tmp_path / "replay" / "verifier").mkdir(parents=True)
    rc = main([
        "check", "--llm", "--keep-going", "--replay-dir", str(tmp_path / "replay"),
        str(tmp_path / "clean" / "foo.ipynb"),
    ])
    assert rc == 3
    assert capsys.readouterr().err.startswith("waldean: ")


def test_llm_subscription_missing_clis_exits_3(monkeypatch, capsys):
    monkeypatch.setattr("waldean.api.shutil.which", lambda name: None)
    rc = main(["check", "--llm", "--llm-subscription", LEAKY])
    assert rc == 3
    assert capsys.readouterr().err == (
        "waldean: --llm-subscription needs the claude and codex CLIs on PATH\n"
    )


def test_rules_lists_all_taxonomy_ids(capsys):
    from waldean.core.taxonomy import load_taxonomy

    rc = main(["rules"])
    out = capsys.readouterr().out
    assert rc == 0
    for fid in load_taxonomy():
        assert fid in out


def test_rules_json_valid(capsys):
    rc = main(["rules", "--format", "json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert len(data) == 9
    for d in data:
        assert set(d) == {"id", "layer", "severity", "definition", "book_anchor"}


def test_expand_nonexistent_path_passes_through(tmp_path):
    missing = str(tmp_path / "nope.ipynb")
    assert _expand_notebooks([missing]) == [missing]


def test_expand_empty_dir_raises(tmp_path):
    with pytest.raises(_EmptyDir):
        _expand_notebooks([str(tmp_path)])


def test_eval_predictions_cli(fake_corpus, capsys):
    preds = fake_corpus / "preds.json"
    preds.write_text(json.dumps({
        "mutated/m.ipynb": [{"flaw_id": "leakage-fit-before-split"}],
    }))
    rc = main(["eval", "--corpus", str(fake_corpus), "--predictions", str(preds)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "external predictions" in out
    assert "recall" in out


def test_eval_predictions_rejects_llm(fake_corpus, capsys):
    rc = main(["eval", "--corpus", str(fake_corpus),
               "--predictions", str(fake_corpus / "nope.json"), "--llm"])
    assert rc == 3
    assert "drop --llm" in capsys.readouterr().err


def test_eval_predictions_malformed_json_exits_3(fake_corpus, capsys):
    preds = fake_corpus / "preds.json"
    preds.write_text("not json")
    rc = main(["eval", "--corpus", str(fake_corpus), "--predictions", str(preds)])
    err = capsys.readouterr().err
    assert rc == 3
    assert err.startswith("waldean: --predictions: ")


def test_eval_predictions_unknown_corpus_path_exits_3(fake_corpus, capsys):
    preds = fake_corpus / "preds.json"
    preds.write_text(json.dumps({"mutated/typo.ipynb": []}))
    rc = main(["eval", "--corpus", str(fake_corpus), "--predictions", str(preds)])
    err = capsys.readouterr().err
    assert rc == 3
    assert err.startswith("waldean: --predictions: ")
    assert "typo" in err


@pytest.mark.parametrize("preds_content", [
    "[]",
    json.dumps({"clean/c.ipynb": [{"confidence": 1.0}]}),
    json.dumps({"clean/c.ipynb": [{"flaw_id": "leakage-fit-before-split",
                                    "confidence": "high"}]}),
    json.dumps({"clean/c.ipynb": "oops"}),
    json.dumps({"clean/c.ipynb": ["oops"]}),
], ids=["top-level-list", "missing-flaw-id", "non-numeric-confidence",
        "findings-not-a-list", "finding-not-an-object"])
def test_eval_predictions_malformed_shapes_exit_3(fake_corpus, capsys, preds_content):
    preds = fake_corpus / "preds.json"
    preds.write_text(preds_content)
    rc = main(["eval", "--corpus", str(fake_corpus), "--predictions", str(preds)])
    err = capsys.readouterr().err
    assert rc == 3
    assert err.startswith("waldean: --predictions: ")


def test_eval_predictions_missing_corpus_blames_corpus(tmp_path, capsys):
    preds = tmp_path / "preds.json"
    preds.write_text("{}")
    rc = main(["eval", "--corpus", str(tmp_path / "nocorpus"), "--predictions", str(preds)])
    err = capsys.readouterr().err
    assert rc == 3
    assert err.startswith("waldean: corpus not found")


def test_eval_predictions_missing_corpus_notebook_blames_corpus(fake_corpus, capsys):
    preds = fake_corpus / "preds.json"
    preds.write_text("{}")
    (fake_corpus / "clean" / "c.ipynb").unlink()
    rc = main(["eval", "--corpus", str(fake_corpus), "--predictions", str(preds)])
    err = capsys.readouterr().err
    assert rc == 3
    assert err.startswith("waldean: corpus: ")


def test_eval_predictions_rejects_split(fake_corpus, capsys):
    preds = fake_corpus / "preds.json"
    preds.write_text("{}")
    rc = main(["eval", "--corpus", str(fake_corpus), "--predictions", str(preds),
               "--split", "dev"])
    assert rc == 3
    assert "--split does not apply" in capsys.readouterr().err
