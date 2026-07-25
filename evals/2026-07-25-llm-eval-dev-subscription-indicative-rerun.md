# Wald LLM eval re-run — 2026-07-25 (quiet-window, dev split, subscription)

Command: `uv run wald eval --corpus corpus --out evals --llm --llm-subscription --split dev`
Wall clock: ~27 min (15:29-15:56 CEST). Report: `evals/2026-07-25-llm-eval-dev.json` / `.md`.

Detector anthropic-agent/session (agent), verifier codex/session (agent). Confidence floor 0.8.
`gate_evidence: false`. `backend_errors: []` (0 errors, all dev files completed) — this is the
run Task 3's hook isolation (`--settings '{"disableAllHooks":true}'` in AgentBackend, commit
f04b9b0) was meant to produce.

## Narrative classes (layer B, full pipeline)

| class | TP | FN | FP | precision | recall | F1 |
|---|---|---|---|---|---|---|
| regression-to-mean-claim | 8 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| selection-survivorship-cohort | 8 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| significance-meaningless | 8 | 0 | 0 | 1.00 | 1.00 | 1.00 |

Clean FP rate (28 notebooks, 0 real): 0.0% (0 files)
Dropped ungrounded: 0/33 raw findings (0.0%)

## G3 — seeded false flags (verifier kill rate per recipe)

- control-group-present: killed 4/4 (100%)
- effect-size-present: killed 4/4 (100%)
- scoped-claim: killed 4/4 (100%)
- wrong-code-span: killed 8/8 (100%)

True-flag survival on the same run: 24/25 (96%)

## Comparison to 2026-07-09 run

The 2026-07-09 run (`evals/2026-07-09-llm-eval-dev-subscription-indicative.md`) had 17/45 dev
files fail with backend errors (mostly a user-level `SessionEnd` hook killing agent sessions),
void-ing gate evidence for those files. This re-run, after hook isolation, has 0 backend errors
across the dev split — same perfect narrative F1 and G3 kill rates on the files that did
complete in the prior run, plus full coverage this time.

## Honest caveats

- Dev split only; heldout is refused structurally (`wald/eval.py:207-212`) and was not run.
- Indicative only: `gate_evidence: false`. Session models are unpinned (whatever `claude`/`codex`
  resolve to at run time), so this run is not reproducible and not a release gate.
- Narrative mutants are template prose from one author; the phrasing holdout detects memorization
  but cannot rule it out.
- Token/cost totals: detector None, verifier None (backend exposes no usage counters).
