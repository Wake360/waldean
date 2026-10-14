# CV-branch promotion gate — 2026-10-13

Proposal: raise two branches of `leakage-fit-before-split` from 0.75 (candidate) to 0.85 (confident flag). The branches are an unsupervised transformer fit whose output feeds a CV sink (`cross_val_score`, `cross_validate`, ...), and a frame statistic written back into the frame whose rows feed a CV sink.

Decision: **gate failed, change not shipped.** The code and test changes were reverted. Both branches stay at 0.75.

## Gate

The promotion needed all three conditions. Baseline is HEAD 2437da4. After is the same tree with the two constants changed. Static layer only, confident flags (>= 0.8).

| condition | before | after | result |
|---|---|---|---|
| `corpus/real` gains zero confident flags | 2 | 5 (+3, one notebook) | fail |
| every new confident flag in the unlicensed dogfood-wide set is a fit on full data before a CV sink | 27 | 31 (+4) | fail (3 of 4) |
| Yang precision >= 0.62 | 0.57 | 0.53 | fail |

## corpus/real

The three new flags are all in `00__ageron_handson-ml3__03_classification`. A `StandardScaler` or preprocessing pipeline is fitted on `X_train` (or `train_data`), and that output feeds `cross_val_score` on the same training split. The held-out test set stays clean. Inside CV, each fold's validation rows were part of the fit. The 2026-07-04 hand review counted this notebook clean at the 0.8 floor. The 2026-07-08 LLM review (`evals/2026-07-08-llm-dogfood-subscription.md`) disagrees: it judged the pre-CV pipeline fits in cells 186 and 258 to be real leaks, as `corpus/real/MANIFEST.json` notes. Whether these three flags are false positives depends on which review is right, so they are not counted as verified false positives here. The gate fails on its own rule anyway, because corpus/real must gain zero confident flags and it gains three.

## Unlicensed dogfood-wide set (hand review, aggregate)

Each of the 4 new confident flags was read in its notebook cell.

| id | verdict | reason |
|---|---|---|
| nb08 | true | `MinMaxScaler` fitted on all feature rows, output feeds `cross_validate` |
| nb12 | true | `StandardScaler` fitted on the full training frame (no held-out split), output feeds `cross_val_score` |
| nb53 | true | `StandardScaler` fitted on the full dataset columns, output feeds `cross_val_score` |
| nb35 | fails the bar | scaler fitted on the training slice of a row split; CV runs on that slice. The leak is only inside CV, not a fit on full data. No ground-truth label; this is a hand-review judgment |

nb02 and nb18, the misses this task targeted: nb18 is already a confident flag at HEAD. nb02 raises no `leakage-fit-before-split` flag or candidate before or after, so the promotion would not cover it.

## Yang et al. ASE'22 (`pre` label)

Same data, labels and script as `evals/2026-10-13-yang-pre.md`.

| run | TP | FP | FN | TN | precision | recall |
|---|---|---|---|---|---|---|
| published 2026-10-13 (`yang-pre.md`) | 8 | 5 | 11 | 76 | 0.62 | 0.42 |
| before, HEAD 2437da4 | 8 | 6 | 11 | 75 | 0.57 | 0.42 |
| after promotion | 8 | 7 | 11 | 74 | 0.53 | 0.42 |

Before vs. published: one new false positive (nb_606, label `N`) comes from the recall changes already on HEAD, not from this promotion. HEAD alone is below the 0.62 bar.

After vs. before: one new false positive (nb_3336, label `N`). It is the same idiom again: a scaler fitted on `X_train`, then `cross_val_score` on `X_train`. No new true positive.

## Reading

The CV branch cannot tell a fit on all data (nb08, nb12, nb53) from a fit on the training split followed by CV on that split (corpus/real nb00, dogfood nb35, Yang nb_3336). Of these, only Yang nb_3336 has a ground-truth label, and Yang labels it `N`. For nb00 the two reviews disagree, and nb35 rests on this task's hand review alone. A future promotion could pass only if it first excludes fits whose input is a split product. That change is not made here.

## Reproduce

`uv run waldean check corpus/real --format json --keep-going` and `uv run waldean check scratch/dogfood-wide --format json --keep-going`. Count flags with `flaw_id == "leakage-fit-before-split"` and `confidence >= 0.8` per file. Yang: `uv run python scripts/yang_eval.py <labels.csv> <notebooks dir> <out.md>`. Data provenance is as in `evals/2026-10-13-yang-pre.md`. The after numbers need `0.9 if supervised else 0.75` changed to `0.85`, and the statistic-before-CV `emit(stat, 0.75, ...)` changed to `0.85`, in `waldean/checks/detect.py`. The unlicensed dogfood-wide set is not committed. Its notebooks are referred to by id only.
