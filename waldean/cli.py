"""waldean CLI: check / propose / verify / eval / corpus."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import sys
from pathlib import Path

from nbformat.reader import NotJSONError

from .api import (BackendError, EmptyDir, check, expand_notebooks, heldout_refusal, llm_backends,
                  missing_llm_keys, missing_subscription_clis)
from .core.flag import DEFAULT_CONFIDENCE_FLOOR
from .report import _colorize, exit_code, parse_warning, report_obj, to_markdown, to_sarif

def _input_error(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "no such file"
    if isinstance(exc, IsADirectoryError):
        return "is a directory, not a notebook"
    if isinstance(exc, UnicodeDecodeError):
        return "not valid UTF-8 text"
    if isinstance(exc, NotJSONError):
        return "not a valid notebook (invalid JSON)"
    return str(exc)


def cmd_check(args) -> int:
    if not 0.0 <= args.floor <= 1.0:
        print(f"waldean: --floor must be between 0 and 1 (got {args.floor})", file=sys.stderr)
        return 3
    if args.probe and any(Path(n).suffix == ".py" for n in args.notebooks):
        print("waldean: --probe runs .ipynb notebooks only", file=sys.stderr)
        return 3
    det = ver = None
    if args.llm:
        print("waldean: --llm is experimental: no validated precision or recall; "
              "its quality gates never ran (see README, Architecture)", file=sys.stderr)
        if args.llm_subscription and missing_subscription_clis():
            print("waldean: --llm-subscription needs the claude and codex CLIs on PATH",
                  file=sys.stderr)
            return 3
        det, ver = llm_backends(args.replay_dir, subscription=args.llm_subscription)
        missing = missing_llm_keys(det, ver)
        if missing:
            print(f"waldean: --llm needs {' and '.join(missing)} set in the environment",
                  file=sys.stderr)
            return 3
    try:
        notebooks = expand_notebooks(args.notebooks)
    except EmptyDir as exc:
        print(f"waldean: {exc}: no .ipynb files found", file=sys.stderr)
        return 3
    # interactive-only chrome; the piped md/json/sarif bytes stay untouched
    color = args.format == "md" and sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    progress = args.llm and sys.stderr.isatty()

    def close_progress():
        # end the \r-overwritten line so errors/summaries start on a fresh one
        if progress:
            print(file=sys.stderr)

    reports = []
    sarif_entries = []
    worst = 0
    n_high = n_med = n_clean = n_failed = 0
    for i, path in enumerate(notebooks, 1):
        if progress:
            print(f"\rchecking {i}/{len(notebooks)} {path}", end="", file=sys.stderr,
                  flush=True)
        if args.llm:
            refusal = heldout_refusal(path, det, ver)
            if refusal:
                close_progress()
                print(f"waldean: {refusal}", file=sys.stderr)
                return 3
        try:
            nb, flow, flags = check(path, det, ver, args.probe)
        except BackendError as exc:
            close_progress()
            print(f"waldean: narrative layer failed: {exc}", file=sys.stderr)
            return 3
        except Exception as exc:
            close_progress()
            print(f"waldean: {path}: {_input_error(exc)}", file=sys.stderr)
            if args.keep_going:
                n_failed += 1
                continue
            return 3
        warning = parse_warning(len(set(flow.parse_errors) | set(flow.skipped_cells) | set(flow.uninlined_cells)),
                                len(nb.code_cells))
        if args.format == "json":
            reports.append(report_obj(path, flags, args.floor, args.severity_gate, warning))
        elif args.format == "sarif":
            sarif_entries.append((path, flags))
        else:
            text = to_markdown(path, flags, args.floor, warning, args.llm)
            print(_colorize(text) if color else text)
        confident = [f for f in flags if f.confidence >= args.floor]
        if any(f.severity == "high" for f in confident):
            n_high += 1
        elif any(f.severity == "medium" for f in confident):
            n_med += 1
        else:
            n_clean += 1
        worst = max(worst, exit_code(flags, args.floor, args.severity_gate))
    close_progress()
    if args.format == "json":
        # one bare object for a single notebook (back-compat), an array for many
        bare = len(notebooks) == 1 and len(reports) == 1
        print(json.dumps(reports[0] if bare else reports, indent=2))
    elif args.format == "sarif":
        print(to_sarif(sarif_entries, args.floor))
    elif len(notebooks) > 1 and sys.stdout.isatty():
        failed = f", {n_failed} failed" if n_failed else ""
        print(f"checked {len(notebooks)} notebooks: {n_high} high, {n_med} medium, "
              f"{n_clean} clean{failed}", file=sys.stderr)
    return max(worst, 3 if n_failed else 0)


def cmd_eval(args) -> int:
    if args.predictions:
        if args.llm:
            print("waldean: --predictions scores an external tool; drop --llm",
                  file=sys.stderr)
            return 3
        if args.split is not None:
            print("waldean: --split does not apply to --predictions; both splits are scored",
                  file=sys.stderr)
            return 3
        from .bench.eval import evaluate_predictions, load_predictions, render_report

        try:
            predictions = load_predictions(args.predictions)
        except (OSError, ValueError) as exc:
            print(f"waldean: --predictions: {_input_error(exc)}", file=sys.stderr)
            return 3
        try:
            results = evaluate_predictions(args.corpus, predictions)
        except SystemExit as exc:
            print(f"waldean: {exc}", file=sys.stderr)
            return 3
        except Exception as exc:
            print(f"waldean: corpus: {_input_error(exc)}", file=sys.stderr)
            return 3
        results["predictions_file"] = args.predictions
        print(render_report(results))
        return 0

    if args.llm:
        from .bench.eval import run_llm_eval

        split = args.split or "dev"
        if args.llm_subscription and split == "heldout":
            print("waldean: subscription runs cannot produce gate evidence — set "
                  "ANTHROPIC_API_KEY + OPENAI_API_KEY for the held-out gate",
                  file=sys.stderr)
            return 3
        if args.llm_subscription and missing_subscription_clis():
            print("waldean: --llm-subscription needs the claude and codex CLIs on PATH",
                  file=sys.stderr)
            return 3

        det, ver = llm_backends(args.replay_dir, subscription=args.llm_subscription)
        missing = missing_llm_keys(det, ver)
        if missing:
            print(f"waldean: --llm needs {' and '.join(missing)} set in the environment",
                  file=sys.stderr)
            return 3
        results = run_llm_eval(args.corpus, det, ver, split=split, out_dir=args.out)
        print(f"llm eval written to {args.out}/{results['date']}-llm-eval-{results['split']}.md")
        for c, r in results["narrative_classes"].items():
            f1 = f"{r['f1']:.2f}" if r["f1"] is not None else "—"
            print(f"  {c}: F1 {f1}")
        fp = results["clean_fp_rate"]
        print(f"  clean FP rate: {fp:.1%}" if fp is not None else "  clean FP rate: —")
        for recipe, r in sorted(results["g3_per_recipe"].items()):
            print(f"  G3 {recipe}: kill {r['killed']}/{r['total']}")
        print(f"  gate evidence: {results['gate_evidence']}")
        return 0

    from .bench.eval import run_eval

    results = run_eval(args.corpus, args.out)
    print(f"eval written to {args.out}/{results['date']}-eval.md")
    for c, r in results["static_classes"].items():
        p = f"{r['precision']:.2f}" if r["precision"] is not None else "—"
        rc = f"{r['recall']:.2f}" if r["recall"] is not None else "—"
        print(f"  {c}: precision {p} recall {rc}")
    print(f"  clean FP rate: {results['clean_fp_rate']:.1%}")
    return 0


def cmd_corpus_build(args) -> int:
    from .bench.corpus import build_corpus

    build_corpus(args.root, seeds=tuple(args.seeds))
    return 0


def cmd_rules(args) -> int:
    from .core.taxonomy import load_taxonomy

    defs = sorted(load_taxonomy().values(), key=lambda d: d.id)
    if args.format == "json":
        print(json.dumps([
            {"id": d.id, "layer": d.layer, "severity": d.severity,
             "definition": " ".join(d.definition.split()), "book_anchor": d.book_anchor}
            for d in defs
        ], indent=2))
        return 0
    for d in defs:
        print(d.id)
        print(f"{d.layer} {d.severity}")
        print(" ".join(d.definition.split()))
        print()
    return 0


VERIFY_EXIT = {"verified": 0, "static-pass": 0, "inconclusive": 1, "rejected": 2}
EXECUTE_WARNING = ("waldean: --execute runs both notebooks on this machine with your permissions. "
                   "Secret-looking environment variables are hidden from the kernel; nothing else "
                   "is isolated.")


def cmd_propose(args) -> int:
    from .repair.loop import propose

    try:
        written, unsupported = propose(args.file, out_root=Path(args.out), floor=args.floor, diff=args.diff)
    except Exception as exc:
        print(f"waldean: {args.file}: {_input_error(exc)}", file=sys.stderr)
        return 3
    for line in unsupported:
        print(f"unsupported: {line}")
    for repair_dir in written:
        print(f"proposed: {(repair_dir / 'brief.md').as_posix()}")
    if not written:
        print("nothing to propose: no confident finding has a repair contract")
    return 0 if written else 1


def cmd_verify(args) -> int:
    import re

    from .repair.loop import render_evidence, verify

    if args.execute != bool(args.metric):
        print("waldean: --execute and --metric go together", file=sys.stderr)
        return 3
    metric = None
    if args.metric:
        try:
            metric = re.compile(args.metric)
        except re.error as exc:
            print(f"waldean: --metric: {exc}", file=sys.stderr)
            return 3
        if metric.groups != 1:
            print("waldean: --metric needs exactly one capture group around the number",
                  file=sys.stderr)
            return 3
        print(EXECUTE_WARNING, file=sys.stderr)
    try:
        evidence = verify(args.repair_dir, args.fixed, metric, args.timeout)
    except ImportError:
        print("waldean: --execute needs the execute extra: pip install 'waldean[execute]'",
              file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"waldean: {args.repair_dir}: {_input_error(exc)}", file=sys.stderr)
        return 3
    print(render_evidence(evidence, Path(args.repair_dir)))
    return VERIFY_EXIT[evidence["status"]]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="waldean", description="Statistical-integrity linter for notebooks.")
    try:
        _version = importlib.metadata.version("waldean")
    except importlib.metadata.PackageNotFoundError:
        _version = "unknown"
    parser.add_argument("-V", "--version", action="version", version=f"waldean {_version}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser(
        "check",
        help="lint notebook(s); exit 0 clean / 1 medium / 2 high-severity / 3 input or usage error",
        epilog="exit codes: 0 clean, 1 medium, 2 high, 3 input or usage error",
    )
    p_check.add_argument("notebooks", nargs="+",
                         help="notebook files or directories (searched recursively "
                              "for *.ipynb, skipping .ipynb_checkpoints); a .py script "
                              "given as an explicit arg is accepted too")
    p_check.add_argument("--format", choices=["md", "json", "sarif"], default="md",
                         help="json emits one object for a single notebook, a JSON array for "
                              "several; sarif emits one SARIF 2.1.0 log for the whole invocation")
    p_check.add_argument("--floor", type=float, default=DEFAULT_CONFIDENCE_FLOOR,
                         help="confidence floor in [0, 1] (default: %(default)s); findings below "
                              "it move to Candidates instead of Flags")
    p_check.add_argument("--severity-gate", choices=["medium", "high"], default="high",
                         help="exit 2 at or above this severity (default: %(default)s); "
                              "confident findings below the gate exit 1")
    p_check.add_argument("--llm", action="store_true",
                         help="add the narrative layer (needs API keys)")
    p_check.add_argument("--llm-subscription", action="store_true",
                         help="run the narrative layer through the claude/codex CLIs "
                              "(subscription billing, no API keys); never gate-eligible")
    p_check.add_argument("--replay-dir", help="record/replay LLM responses here")
    p_check.add_argument("--probe", action="store_true",
                         help="run the notebook up to each fit-before-split sink in a separate "
                              "waldean-verify kernel and rewrite the flag's confidence from "
                              "n_samples_seen_; executes your code with your permissions; .ipynb only")
    p_check.add_argument("--keep-going", action="store_true",
                         help="continue past unreadable files (reported on stderr); "
                              "exit 3 if any file could not be checked")
    p_check.set_defaults(func=cmd_check)

    p_eval = sub.add_parser("eval", help="run detectors over the corpus, write dated report")
    p_eval.add_argument("--corpus", default="corpus",
                        help="corpus root directory (default: %(default)s)")
    p_eval.add_argument("--out", default="evals",
                        help="directory for dated eval reports (default: %(default)s)")
    p_eval.add_argument("--llm", action="store_true",
                        help="narrative-layer eval (needs API keys)")
    p_eval.add_argument("--llm-subscription", action="store_true",
                        help="run the narrative layer through the claude/codex CLIs "
                             "(subscription billing, no API keys); never gate-eligible")
    p_eval.add_argument("--split", choices=["dev", "heldout"])
    p_eval.add_argument("--replay-dir", help="record/replay LLM responses here")
    p_eval.add_argument("--predictions",
                        help="score an external tool: JSON of {corpus-relative "
                             "path: [{flaw_id, confidence}]} instead of running "
                             "waldean's own detectors")
    p_eval.set_defaults(func=cmd_eval)

    p_corpus = sub.add_parser("corpus", help="corpus operations")
    corpus_sub = p_corpus.add_subparsers(dest="corpus_command", required=True)
    p_build = corpus_sub.add_parser("build", help="build clean notebooks + verified mutants")
    p_build.add_argument("--root", default="corpus",
                         help="corpus root directory (default: %(default)s)")
    p_build.add_argument("--seeds", nargs="+", type=int, default=[11, 12, 13, 14],
                         help="dev-split base seeds, one clean notebook per family "
                              "per seed (default: %(default)s)")
    p_build.set_defaults(func=cmd_corpus_build)

    p_rules = sub.add_parser("rules", help="list the flaw classes waldean checks")
    p_rules.add_argument("--format", choices=["text", "json"], default="text",
                         help="json emits a JSON array of flaw objects (default: %(default)s)")
    p_rules.set_defaults(func=cmd_rules)

    p_propose = sub.add_parser(
        "propose",
        help="write a repair contract for a fixable finding; exit 0 written / 1 nothing / 3 error",
    )
    p_propose.add_argument("file", help="notebook or .py script")
    p_propose.add_argument("--out", default=".waldean/repairs",
                           help="directory for repair contracts (default: %(default)s)")
    p_propose.add_argument("--floor", type=float, default=DEFAULT_CONFIDENCE_FLOOR,
                           help="confidence floor (default: %(default)s)")
    p_propose.add_argument("--diff", action="store_true",
                           help="also write patch.diff when the fix is mechanical")
    p_propose.set_defaults(func=cmd_propose)

    p_verify = sub.add_parser(
        "verify",
        help="check a repair against its contract; exit 0 verified or static-pass / "
             "1 inconclusive / 2 rejected / 3 error",
    )
    p_verify.add_argument("repair_dir", help="directory written by waldean propose")
    p_verify.add_argument("--fixed", help="repaired file (default: the file the contract names)")
    p_verify.add_argument("--execute", action="store_true",
                          help="run the original and the repaired notebook and compare the metric")
    p_verify.add_argument("--metric",
                          help="regex with one capture group for the number, matched against "
                               "printed output lines")
    p_verify.add_argument("--timeout", type=int, default=600,
                          help="seconds per cell when executing (default: %(default)s)")
    p_verify.set_defaults(func=cmd_verify)

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code == 2:
            return 3
        raise
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
