# Changelog

## 0.5.0

- `waldean propose FILE` writes a repair contract (`protocol.json`, `brief.md`, a copy of the original) for confident `leakage-temporal-shuffle` findings. Other classes are listed as unsupported.
- `waldean verify REPAIR_DIR` checks a repair against its contract and writes `evidence.json`. Exit 0 verified or static-pass, 1 inconclusive, 2 rejected, 3 error. `--execute --metric REGEX` runs the original and the repaired notebook (new `execute` extra).
- Markdown reports add a `Repair:` line under findings that have a repair contract.

## 0.4.0

- Renamed the project from Wald to Waldean. The PyPI package is now
  `waldean` (was `wald-lint`), the command is `waldean` (was `wald`), the
  import package is `waldean`, the repository is `Wake360/waldean`, the
  GitHub Action is `Wake360/waldean@v0.4.0` and the pre-commit hook ids are
  `waldean` and `waldean-scripts`. Environment variables use the
  `WALDEAN_` prefix, and corpus notebook metadata uses the `waldean` key.
  Detection behavior and report content are unchanged.

## 0.3.1

- `wald eval --predictions FILE` scores an external tool's findings
  against the mutation corpus with the same counting logic as Wald's own
  detectors (`docs/benchmark.md`). Malformed input exits 3 with a message
  that names the bad entry. `--split` and `--llm` are rejected together
  with `--predictions`.
- `scripts/self-score.sh` proves that Wald's own flags, converted to the
  predictions format, reproduce `wald eval` exactly.
- LLM narrative layer: `AgentBackend` now passes `--settings
  '{"disableAllHooks":true}'` to the `claude`/`codex` CLIs, so a
  user-level Claude hook can no longer kill a subscription eval
  session mid-run — the 2026-07-09 dev-split eval lost 17/45 sessions
  to a `SessionEnd` hook doing exactly this.
- Packaging: `wald/__init__.py` version had drifted to 0.2.1 against
  the 0.3.0 release; fixed and locked by a new packaging test so the
  two can't diverge again.
- CI: ruff pinned to 0.15.21 and pyright to 1.1.411 — ruff 0.16.0
  reported 37 new findings on an unrelated version bump.
- README rewritten for the subscription-only narrative path.

## 0.3.0

- CLI: `.py` input support — `wald check analysis.py` runs on plain
  scripts (one analysis unit) and percent-format files (`# %%` code
  cells, `# %% [markdown]` markdown cells); reported lines are
  file-absolute. Directory arguments still collect only `*.ipynb` —
  pass `.py` files explicitly. `examples/leaky.py` ships alongside
  `examples/leaky.ipynb`.
- CLI: `--keep-going` on `wald check` — continue past unreadable files
  instead of aborting on the first one; each failure is reported to
  stderr, and the run exits 3 if any file failed, even alongside a
  high-severity finding elsewhere that would otherwise exit 2. The
  multi-file TTY summary line gains a `, N failed` suffix.
- CLI: `wald rules` — lists the taxonomy's flaw classes (id, layer,
  severity, definition); `--format json` for machines.
- LLM narrative layer: the G2/G3 quality gates never ran — they need
  `ANTHROPIC_API_KEY` + `OPENAI_API_KEY`, and the keys never arrived. Per
  the pre-planned termination rule, v1 ships as the static linter; no
  narrative-layer recall/F1 numbers are claimed. The layer remains
  available as an experimental, unvalidated path via `--llm-subscription`
  (claude/codex CLIs, no API keys) and `--llm` for key holders; an
  indicative non-gate dev-split run is at
  `evals/2026-07-09-llm-eval-dev-subscription-indicative.md`.
- `.pre-commit-hooks.yaml`: `wald` hook for notebooks, `wald-scripts` for
  `.py` files.
- New GitHub issue template for false-positive reports
  (`.github/ISSUE_TEMPLATE/false_positive.md`).
- Launch post addendum (`posts/2026-07-04-i-mutation-tested-statistical-malpractice.md`)
  covering the 60-notebook wide dogfood.

## 0.2.1

- CLI UX: TTY-aware severity color and a dimmed CLEAN line (`NO_COLOR`
  honored), recursive directory input (`wald check <dir>` walks `*.ipynb`,
  skips `.ipynb_checkpoints`, empty dir exits 3), a multi-file roll-up
  summary line, and `wald check --llm` per-file progress. Piped
  md/json/sarif bytes and the 0/1/2/3 exit contract are unchanged,
  asserted byte-for-byte against `tests/golden/leaky.md`.
- `wald eval --llm` per-notebook progress and a key-guard test.
- pyright is now a hard CI gate at 0 errors (dropped `continue-on-error`).
- Temporal-shuffle evasion triage: 4 evasion shapes enumerated, each
  accepted with a written rationale (`docs/temporal-shuffle-evasions.md`).
- selection-survivorship-cohort parked for narrative-layer fusion: a
  scoped-claim notebook emits the identical below-floor candidate, so a
  static-only promotion cannot hold precision. The 16 mutants and
  candidate recall 1.00 are kept.
- Composite GitHub Action (`action.yml`): runs `wald check --format
  sarif`, exposes a `fail-on`-mapped gate exit code, and pairs with
  `upload-sarif` for PR annotations. Inputs pass through `env`, never
  template expansion, to avoid command injection from consumer-supplied
  paths.

No detector behavior change: all four static classes remain precision
1.00 / recall 1.00 on 192 mutants, 0.0% FP on the 83-notebook clean
corpus.

## 0.2.0

- Fourth static class: `leakage-temporal-shuffle` — shuffled train/test
  splits on time-ordered data with lag/rolling-window features, evaluated
  per evaluation sink on that sink's dependency chain. Adversarially
  hardened: 4 confirmed false-positive shapes (sorted-frame neighbor
  features) fixed at the root; 4 evasions documented as residual risk.
- Corpus grew to 83 clean notebooks (56 synthetic + 27 real), 192 verified
  mutants. New class: 16/16 at precision 1.00 / recall 1.00. All four
  static classes still precision 1.00 / recall 1.00, clean FP rate 0.0%.
  (`evals/2026-07-05-eval.md`, `evals/2026-07-05-eval.json`.)

## 0.1.0

- Static layer: three flaw classes — `leakage-fit-before-split`,
  `testing-multiple-uncorrected`, `baserate-accuracy-imbalanced` — plus a
  below-floor candidate for `selection-survivorship-cohort`. Mutation-tested
  at precision 1.00 / recall 1.00 on all three; 0.0% FP on 75 clean
  notebooks (48 synthetic + 27 real). (`evals/2026-07-04-eval.md`.)
- Narrative layer (M2): LLM claims-vs-computation detector, cross-provider
  verifier, fusion — built and tested key-free against replay fixtures.
  G2/G3 quality gates not yet run (blocked on Anthropic + OpenAI keys).
- Dogfooded on 34 real notebooks: detector rebuilt after an initial 50%
  file flag rate (119 of 124 flags false positives); after the fix, 3
  confident flags, all confirmed real leaks, 0 known false positives.
  (`evals/2026-07-04-dogfood.md`.)
- SARIF 2.1.0 output (`wald check --format sarif`) and agent-gate docs
  (`docs/agent-gate.md`): Claude Code PostToolUse hook, pre-commit,
  GitHub Actions recipe with SARIF upload.
