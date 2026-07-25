
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

