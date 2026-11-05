# Waldean on Yang et al. ASE'22 (`pre` label) — 2026-11-05

100 notebooks, 66 with a `pre` label; the 34 without one count as negatives; static layer, confident flags only (>= 0.8), class `leakage-fit-before-split`.

| TP | FP | FN | TN | precision | recall |
|---|---|---|---|---|---|
| 13 | 5 | 6 | 76 | 0.72 | 0.68 |

Errors (waldean exit 3, counted as not flagged): 2
- GitHub-data/notebooks/2021-09-09/nb_334.py
- GitHub-data/notebooks/2021-09-30/nb_195.py

## Flagged
- GitHub-data/notebooks/2021-09-01/nb_2528.py — label `Y`
- GitHub-data/notebooks/2021-09-05/nb_1162.py — label `N (due to overlaps)`
- GitHub-data/notebooks/2021-09-05/nb_1633.py — label `Y [type inference]`
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

## Review

Rerun of `evals/2026-10-13-yang-pre-rerun.md` on branch `dataflow-deep-inline`. Same data, labels and script. Baseline: the same script on `main` at 88fda0a on 2026-11-05 gave 12 / 5 / 7 / 76, identical to the 2026-10-13 rerun, so HEAD drift since then changed nothing here.

Changes measured: helpers inlined up to three levels deep with a recursion stop, return values bound position by position, row slices and `append`-style mutations recorded inside helpers, inlined assigns keep their call, and the tail of a row slice split counts as test data.

Change against baseline: one more true positive, no new false positive. Precision 0.71 -> 0.72, recall 0.63 -> 0.68 (13 of 19). The recall target of 0.70 (14 of 19) set in the 2026-10-13 rerun is still not met, so the README keeps the published 0.62 / 0.42.

| nb | now | why |
|---|---|---|
| nb_1633 | flagged | `create_model` calls `split_train_test`, which returns a row slice split, and `scale_test_data`, which calls `fit_transform` on the test part. The test part reaches `model.predict` through `window_data`'s `append` loop (0.9). |
| nb_678 | missed | Train and test go through pickle files and the full set is reloaded from file. File round trips are not followed. |
| nb_3144 | missed | No split call, and `LabelEncoder` is exempt on purpose. |

The five false positives are unchanged: nb_1162, nb_2770, nb_65, nb_1959, nb_3594.

## Caveats

nb_1633 was the target of this change, so this rerun is not a held-out estimate.
nb_1633 yields two flags at the same cell and line, one per `fit_transform` call inside `scale_test_data`, because the inlined body sits at the outer call site.
Yang labels are the paper authors' manual labels, not re-adjudicated here. Only `pre` is comparable.
Data: labels from https://github.com/malusamayo/GitHubAPI-Crawler/raw/master/evaluation_materials/manual-labels.csv (sha256 075cde4f451354dff537ba1ae673d5dd6d631782892e34a525bdb20dd0ec200f), notebooks from https://github.com/malusamayo/GitHubAPI-Crawler/raw/master/evaluation_materials/sample-notebooks.zip (sha256 b645e3efb3fb5dcaf5dadb0b33d441d6816aede4af8a17ce482a5116f9896ca1). Upstream license: none declared on GitHub. Neither file is committed.
Reproduce: `uv run python scripts/yang_eval.py <labels.csv> <unzipped notebooks dir> <out.md>`; the Review and Caveats sections are written by hand.
