# Waldean report — examples/temporal-cv-before-after.ipynb

verdict: 1 high, 0 medium | static layer (no LLM)

## HIGH: leakage-temporal-shuffle
- **Where:** cell 5, line 2
- **Evidence:** time-ordered frame (datetime origin in cell 2) carries lag/window features (`.shift` at cell 3 line 3, `.shift` at cell 3 line 2, `.shift` at cell 3 line 1); `cross_validate` (cell 5) uses a shuffled split, leaking future rows into training
- **Flaw:** Time-ordered data whose lag, rolling-window, or resampled features feed a model evaluation is split with a shuffled protocol — train_test_split with default shuffle, a shuffled KFold, or non-temporal cross-validation — instead of TimeSeriesSplit, shuffle=False, or an explicit temporal cutoff.
- **Failure scenario:** Training rows sit after test rows in time, so the model is scored on "predicting" a past it was trained beyond; the reported error collapses when the model must forecast an actual future.
- **Fix:** Split by time: an explicit cutoff date, train_test_split(shuffle=False) on time-sorted rows, or TimeSeriesSplit for cross-validation.
- **Confidence:** 0.90
- **Repair:** `waldean propose examples/temporal-cv-before-after.ipynb` writes a repair contract that an agent or a person can apply and Waldean can verify

## CLEAN (checked): baserate-accuracy-imbalanced, leakage-fit-before-split, testing-multiple-uncorrected

