# Wald LLM eval — 2026-07-25 (corpus built 2026-07-05, split dev)

Detector anthropic-agent/session (agent), verifier codex/session (agent). Confidence floor 0.8. Gate evidence: False.

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

## Honest caveats
- Narrative mutants are template prose from one author; the phrasing holdout detects memorization but cannot rule it out.
- Token/cost totals: detector None, verifier None (None = backend exposes no usage counters).