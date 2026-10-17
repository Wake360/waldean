# Best-of-N selection: false-positive recheck, 2026-10-17

This note checks the best-of-n shape of `leakage-test-selection`. The shape was designed from book cases, not from these notebooks, so the v3 counts below are a false-positive check, not a recall claim.

## Commands

Before is commit a4959d9, the last commit before the best-of-n detector. After is the current branch.

```bash
git worktree add <scratch>/waldean-pre12 a4959d9
(cd <scratch>/waldean-pre12 && uv run waldean check --format json --keep-going \
  /Users/filipvachek/dev/waldean/corpus/real /Users/filipvachek/dev/waldean/evals/agent-baseline-v3/runs \
  > <scratch>/waldean-12-before.json)
git worktree remove <scratch>/waldean-pre12
uv run waldean check --format json --keep-going corpus/real evals/agent-baseline-v3/runs > <scratch>/waldean-12-after.json
```

The flag sets were diffed on (notebook, flaw_id, cell, line, confidence), over flags and candidates. Then:

```bash
uv run waldean corpus build --root corpus
uv run pytest tests/test_gates.py -q
uv run waldean eval --corpus corpus --out evals
```

## Result

NEW: 0. GONE: 0. The raw diff printed 24 NEW and 24 GONE lines. Each pair was the same flag, with an absolute path in the before run and a relative path in the after run. After normalizing the paths, the two sets are identical, 24 flags each. The best-of-n shape fires on no v3 run and no corpus/real notebook.

The corpus build produced 64 clean notebooks, 240 verified mutants (0 discarded) and 44 negative flags. The gates passed (16 tests). In evals/2026-10-17-eval.md, `leakage-test-selection` has 24 TP, 0 FN, 0 FP, precision 1.00 and recall 1.00. The Robustness section marks this row as thin: all 24 mutants come from one base family, so the recall measures one idiom.

The clean FP rate is 2.2% (2 of 91). The cause is `leakage-fit-before-split` flags at 0.9 on two real notebooks. One is corpus/real/21__dipanjanS_practical-machine-learning-with-python__decision_tree_regression.ipynb, cell 42. The other is corpus/real/28__dipanjanS_practical-machine-learning-with-python__linear_regression.ipynb, cell 29. In both, the helper `transform_ohe` calls `ohe.fit_transform` on `X_test`. Both flags were already present at a4959d9, before this plan. They came in after eb94aa2, the commit behind the 2026-10-13 eval, which reported 0.0%. Whether to relabel these notebooks or change the detector is open.

The eval report was produced with uncommitted changes to waldean/bench/eval.py, which add the Robustness section.
