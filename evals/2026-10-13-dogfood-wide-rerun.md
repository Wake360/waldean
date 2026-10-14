# Dogfood-wide rerun — 2026-10-13

Rerun of `evals/2026-07-07-dogfood-wide.md` on the same 60 notebooks, on branch `detect-quality` at a5a36ab. Static layer, confident flags (>= 0.8), no `--probe`. Ground truth is the 2026-07-07 review and its ledger `evals/real-flaws.tsv`; new flags were reviewed by hand in their cells for this file. Most notebooks have no license, so this report is aggregate only.

Ids: `nb01`-`nb20` are the ledger ids of the 20 leaky notebooks. `w02` and `w45` are two notebooks outside the ledger, by their position in the batch.

Command: `uv run waldean check scratch/dogfood-wide --format json --keep-going`. All 60 notebooks were read; none failed.

## Result

| | 2026-07-07 | 2026-10-13 |
|---|---|---|
| flagged notebooks | 13 | 15 |
| confident flags | 28 | 32 |
| flags confirmed real | 25 (0.89) | 28 (0.88) |
| `leakage-fit-before-split` flags confirmed real | 22 of 25 | 24 of 27 |
| ledger leaky notebooks caught | 12 of 20 (0.60) | 12 of 20 (0.60) |

Notebook-level recall over the same 20 leaky notebooks is unchanged at 12 of 20. None of the 8 previous misses is flagged. Every flag from 2026-07-07 is still raised at the same cell and line, including the 3 that did not survive review (the RFECV scout split, a `y.fillna`, and a one-hot encoder on the target), so they still count against precision.

The rerun found one leaky notebook outside the ledger (w45, below). It was not in the 2026-07-07 miss-hunt sample. Over the 21 leaky notebooks now known, 13 are caught. This supports the 2026-07-07 caveat that the unsampled notebooks hide leaks; it is not a new recall estimate.

## New flags, hand review

| id | class | verdict | reason |
|---|---|---|---|
| w45 | `leakage-fit-before-split` (0.92) | real | `TfidfVectorizer.fit_transform` on the full text column, then resampling, then a `train_test_split` inside a helper called from the model cell. The vocabulary and idf weights include the test rows. Found through helper inlining. |
| nb16 | `leakage-fit-before-split` (0.85) | real | A per-group mean of a numeric feature, computed with `groupby(...).transform('mean')` over the full frame, becomes two feature columns that pass through to the split. Mild leak, the same family as the nb07 miss. |
| nb01 | `leakage-test-selection` (0.9) | real | The best of four models is picked by ROC-AUC on the test split, and that score is printed as the result. The later predictions go to an unlabeled submission, so no other score is reported. |
| w02 | `leakage-test-selection` (0.9) | borderline, not counted | The number of features is picked by validation ROC-AUC and the AUC at the optimum is printed as validation. The test split is held out and written to disk for a later notebook. The pattern fits the definition, but the printed number is labeled as a validation score, not the final estimate. |

`leakage-test-selection` did not exist on 2026-07-07, so its two flags are new in this run, not regressions.

## Previous misses

| id | idiom | flagged now | why not |
|---|---|---|---|
| nb02 | scaler on full data feeding `cross_val_score` | no | Still a 0.75 candidate. The CV promotion gate failed (`evals/2026-10-13-cv-promotion.md`). |
| nb07 | per-group median `fillna` | no | The only evaluation is `cross_val_score` on the training file. A group-statistic fill before a CV sink raises nothing; a minimal script reproduces this. The same fill before `train_test_split` is flagged. |
| nb10 | column-mean `fillna` | no | The mean is computed on the source frame and fills a copy derived from it. The statistic branch needs the same frame on both sides; a minimal script reproduces this. |
| nb12 | temporal shuffle in CV | no | No detector change for this class. Still a 0.75 `leakage-fit-before-split` candidate only. |
| nb15 | temporal shuffle in a training helper | no | No change for this class. |
| nb17 | TF-IDF/SVD on full corpus | no | Python 2 cells, including the split and model cells, still do not parse. |
| nb18 | scaler on full data feeding `cross_val_score` | no | Same as nb02, 0.75 candidate. |
| nb19 | `get_dummies` key leakage | no | Not modelled. |

## Caveats

- Ground truth for the 25 old confirmed flags is the 2026-07-07 LLM adversarial review. The 4 new flags have one hand review each.
- Recall is still over the 43-notebook audited subset at one seed.
- The changes measured here were designed against Yang notebooks, not this set, but this set was used to check them for new false positives along the way.
