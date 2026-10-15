---
name: waldean
description: Use when writing or editing a notebook or .py script that trains or evaluates a model, splits data, runs statistical tests, or reports a metric. Methodology checklist plus `waldean check` before any reported number.
---

# Waldean

## When this applies

You are writing or editing analysis code whose output is a number someone will trust: a model score, a p-value, a lift, a forecast error. Follow the checklist while you write it, and run `waldean check` before you report the number.

## Checklist

1. Before modelling, set aside a test set. If the model is meant for rows later than the data, the test set is the latest rows. If an entity appears in several rows, the test set holds whole entities.
2. Cross-validate inside the training rows only, with the same structure: earlier rows train and later rows test, or whole entities per fold.
3. Fit every preprocessing step inside the cross-validation folds.
4. Name all candidate models, including a trivial baseline, before scoring any of them.
5. Choose the model, features, hyperparameters and decision threshold on cross-validation only. Write the choice down before scoring the test set.
6. Refit the chosen model on all training rows and score it once on the test set. That score is the headline.
7. Use only features known at prediction time. If you do not know when a column is recorded, ask or say so next to the result. Drop identifiers.

For statistical tests: if you run more than one test on the same question, apply a correction (Holm, Bonferroni or Benjamini-Hochberg) and say which. For imbalanced classes, do not report accuracy alone.

## Install

```bash
pip install waldean
```

If it cannot be installed, tell the user and continue with the checklist alone.

## Run

Run it once the split and preprocessing are in place, and again before you report any metric:

```bash
waldean check <file> --format json
```

| exit | meaning |
|---|---|
| 0 | no confident finding |
| 1 | medium finding |
| 2 | high finding |
| 3 | input or usage error; the file was not checked |

## Act on findings

HIGH: fix the cell and line the report names, run the check again, and do not report the metric until the finding is gone.

MEDIUM: fix it if the fix is local. Otherwise report the finding next to the metric.

Candidates (in `candidates`, below the confidence floor): read them and mention one only if it holds.

Never change the code just so the detector stops seeing the pattern. The report names the mechanism; fix the mechanism.

## Limits

A clean report is not a clean notebook. Waldean misses, among others: a split returned from a helper or more than one helper level deep, train and test loaded from separate files, a manual `KFold.split` loop, and Python 2 cells. A scaler fitted on all rows that feeds `cross_val_score` is only a candidate. The checklist covers these cases; the linter does not.

## Repair

For `leakage-temporal-shuffle` and `leakage-fit-before-split`, `waldean propose <file>` writes a repair brief and `waldean verify <dir>` checks the repair. Both are experimental.
