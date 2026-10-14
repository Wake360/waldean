# Methodology checklist

1. Before modelling, set aside a test set. If the model is meant for rows later than the data, the test set is the latest rows. If an entity appears in several rows, the test set holds whole entities.
2. Cross-validate inside the training rows only, with the same structure: earlier rows train and later rows test, or whole entities per fold.
3. Fit every preprocessing step inside the cross-validation folds.
4. Name all candidate models, including a trivial baseline, before scoring any of them.
5. Choose the model, features, hyperparameters and decision threshold on cross-validation only. Write the choice down before scoring the test set.
6. Refit the chosen model on all training rows and score it once on the test set. That score is the headline.
7. Use only features known at prediction time. Read columns.csv for when each column is recorded. Drop identifiers.
