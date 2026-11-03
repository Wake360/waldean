# Waldean report — examples/leaky.ipynb

verdict: 1 high, 0 medium | static layer (no LLM)

## HIGH: leakage-fit-before-split
- **Where:** cell 5, line 2
- **Evidence:** `scaler.fit_transform(...)` consumes X, feeding `train_test_split` (cell 5) — the fit happened before the split
- **Flaw:** A transformation (scaler, imputer, encoder, feature selector, PCA, vectorizer) is fitted on data that contains the test set.
- **Failure scenario:** Test metrics are inflated; the production model will underperform the reported numbers.
- **Fix:** Fit the transformer on the training split only; apply transform to the test split.
- **Confidence:** 0.92
- **Repair:** `waldean propose examples/leaky.ipynb` writes a repair contract that an agent or a person can apply and Waldean can verify

## Notes
- no baseline found for `accuracy_score` (cell 6): compare it with a DummyClassifier or the majority-class rate to show what the model adds

## CLEAN (checked): baserate-accuracy-imbalanced, leakage-lag-full-series, leakage-resample-before-split, leakage-temporal-shuffle, leakage-test-selection, testing-multiple-uncorrected

