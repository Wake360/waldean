# Waldean on Yang et al. ASE'22 (`pre` label) — 2026-10-13

100 notebooks, 66 with a `pre` label; the 34 without one count as negatives; static layer, confident flags only (>= 0.8), class `leakage-fit-before-split`.

| TP | FP | FN | TN | precision | recall |
|---|---|---|---|---|---|
| 12 | 5 | 7 | 76 | 0.71 | 0.63 |

Errors (waldean exit 3, counted as not flagged): 2
- GitHub-data/notebooks/2021-09-09/nb_334.py
- GitHub-data/notebooks/2021-09-30/nb_195.py

## Flagged
- GitHub-data/notebooks/2021-09-01/nb_2528.py — label `Y`
- GitHub-data/notebooks/2021-09-05/nb_1162.py — label `N (due to overlaps)`
- GitHub-data/notebooks/2021-09-05/nb_2770.py — label `N (due to overlaps)`
- GitHub-data/notebooks/2021-09-05/nb_2816.py — label `Y`
- GitHub-data/notebooks/2021-09-06/nb_1417.py — label `Y`
- GitHub-data/notebooks/2021-09-07/nb_949.py — label `Y (MinMaxScaler)`
- GitHub-data/notebooks/2021-09-09/nb_1559.py — label `Y`
- GitHub-data/notebooks/2021-09-10/nb_2760.py — label `Y`
- GitHub-data/notebooks/2021-09-12/nb_1942.py — label `Y (StandardScaler)`
- GitHub-data/notebooks/2021-09-14/nb_65.py — label `N`
- GitHub-data/notebooks/2021-09-16/nb_318.py — label `Y`
- GitHub-data/notebooks/2021-09-18/nb_1959.py — label `N`
- GitHub-data/notebooks/2021-09-18/nb_278.py — label `Y`
- GitHub-data/notebooks/2021-09-20/nb_296.py — label `Y`
- GitHub-data/notebooks/2021-09-23/nb_2646.py — label `Y (mean)`
- GitHub-data/notebooks/2021-09-26/nb_1094.py — label `Y (mean)`
- GitHub-data/notebooks/2021-09-30/nb_3594.py — label `N [human errors]`

## Missed (`pre` = Y, not flagged)
- GitHub-data/notebooks/2021-09-04/nb_1743.py — label `Y (mean)`
- GitHub-data/notebooks/2021-09-02/nb_3065.py — label `Y (tokenizer, val data)`
- GitHub-data/notebooks/2021-09-30/nb_195.py — label `Y`
- GitHub-data/notebooks/2021-09-08/nb_678.py — label `Y`
- GitHub-data/notebooks/2021-09-30/nb_89.py — label `Y`
- GitHub-data/notebooks/2021-09-13/nb_3144.py — label `Y`
- GitHub-data/notebooks/2021-09-05/nb_1633.py — label `Y [type inference]`
## Review

Rerun of `evals/2026-10-13-yang-pre.md` on branch `detect-quality` at a5a36ab. Same data, labels and script. Changes since that record: refit on a test split output, `Tokenizer.fit_on_texts`, concat of split parts, row-slice splits (2-D slices, a 0 lower bound, a bounded tail, an open lookback tail), one level of function inlining including `.pipe`, a frame statistic in a pinned assign, chained `fillna` or a `.pipe` lambda, and a test split filled with its own statistic. `--probe` was not used; it executes code and this data is read only.

Change against `2026-10-13-yang-pre.md`: four more true positives, no new false positive. Precision 0.62 -> 0.71, recall 0.42 -> 0.63 (12 of 19). The target was recall >= 0.70 (14 of 19), so it is not met. The README keeps the published 0.62 / 0.42 until a run meets it.

The five false positives are unchanged: nb_1162, nb_2770, nb_65, nb_1959 (encoder fit before the split, Yang `N`) and nb_3594 (`N [human errors]`).

The 11 misses of `2026-10-13-yang-pre.md`, read statically:

| nb | now | why |
|---|---|---|
| nb_318 | flagged | A feature helper fills `data_test.Age` with the median of `data_test` after the split. Test split filled with its own statistic (0.85). |
| nb_296 | flagged | Inside `build_decision_tree` and `sanitize_mobility`: `fillna` with the frame's own mean and a hand-written min-max, then `train_test_split`. Seen through one-level inlining (0.85). |
| nb_2528 | flagged | Scaler `fit_transform` on the full array, then `[0:n, :]` / `[n-80:, :]`. 2-D row slices, a 0 lower bound and an open lookback tail now form a split (0.92). |
| nb_1417 | flagged | Scaler and PCA `fit_transform` on the full data, then a head slice and a bounded tail slice (0.92). |
| nb_1743 | missed | Train and test come from separate `read_csv` files. The test frame is filled with its own mean. There is no split call, so test identity is known only by name. |
| nb_3065 | missed | `Tokenizer.fit_on_texts` on all rows, then `for tr, te in kf.split(X)`. Tokenizer is now a fitted transformer, but `KFold.split` is not a split sink. Treating it as one would raise unsupervised pre-CV fits above the 0.75 candidate level, which the CV promotion gate rejected (`evals/2026-10-13-cv-promotion.md`). |
| nb_678 | missed | The split is a row slice (`dataset[:9000, :]`), but train and test go through pickle files, the tokenizer comes from a factory helper's return value, and the full set is reloaded from file. No file round-trip identity and no return-value binding. |
| nb_89 | missed | Separate `read_csv` files, no split call. The refit on test is `PolynomialFeatures.fit_transform` inside a helper inside loops. That transformer is stateless, so the refit leaks nothing measurable. |
| nb_1633 | missed | The row slice split is inside `split_train_test` and comes back through `return train, test`. The refit on test is in `scale_test_data`, called from `create_model`: two levels deep. Inlining is one level and return values are not bound. |
| nb_3144 | missed | `LabelEncoder.fit(list(train) + list(test))` in `feature_preprocessing`, called from `feature_engineering1` (two levels). There is no split call, and `LabelEncoder` is exempt on purpose. |
| nb_195 | missed | Over the 20 MB input cap (exit 3). |

Summary: 4 of 11 misses are now caught. Of the 7 left, 3 need return-value binding or more than one level of inlining (nb_678, nb_1633, nb_3144), 2 need name-based test identity for separately loaded files (nb_1743, nb_89), 1 needs a policy on unsupervised fits before a manual `KFold` loop (nb_3065), and 1 is the size cap (nb_195).

## Caveats

Yang labels are the paper authors' manual labels, not re-adjudicated here.
Only `pre` is comparable; Waldean has no class for `overlap` or `multi`.
The 34 notebooks without a `pre` label have Yang's `model` label `N`. None was flagged.
The four recovered notebooks were the targets of the changes measured here, so this rerun is not a held-out estimate.
Data: labels from https://github.com/malusamayo/GitHubAPI-Crawler/raw/master/evaluation_materials/manual-labels.csv (sha256 075cde4f451354dff537ba1ae673d5dd6d631782892e34a525bdb20dd0ec200f), notebooks from https://github.com/malusamayo/GitHubAPI-Crawler/raw/master/evaluation_materials/sample-notebooks.zip (sha256 b645e3efb3fb5dcaf5dadb0b33d441d6816aede4af8a17ce482a5116f9896ca1). Upstream license: none declared on GitHub. Neither file is committed.
Reproduce: `uv run python scripts/yang_eval.py <labels.csv> <unzipped notebooks dir> <out.md>`; the Review and Caveats sections are written by hand.
