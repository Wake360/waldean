import json

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

df = pd.read_csv("data.csv")
holdout = pd.read_csv("holdout.csv")["row"].tolist()
train = [r for r in range(len(df)) if r not in set(holdout)]
months = sorted(df.loc[train, "snapshot"].unique())
folds = [([r for r in train if df.at[r, "snapshot"] < m], [r for r in train if df.at[r, "snapshot"] == m])
         for m in months[-3:]]
X, y = df[["x"]], df["churn"]
candidates = {"dummy": DummyClassifier(strategy="prior"), "logreg": LogisticRegression()}
cv_scores = {name: [float(roc_auc_score(y.iloc[te], m.fit(X.iloc[tr], y.iloc[tr]).predict_proba(X.iloc[te])[:, 1]))
                    for tr, te in folds] for name, m in candidates.items()}
chosen = max(cv_scores, key=lambda k: np.mean(cv_scores[k]))
model = candidates[chosen].fit(X.iloc[train], y.iloc[train])
headline = float(roc_auc_score(y.iloc[holdout], model.predict_proba(X.iloc[holdout])[:, 1]))
json.dump({"features": ["x"], "candidates": list(candidates), "cv_folds": folds, "cv_scores": cv_scores,
           "chosen": chosen, "holdout_rows": holdout, "holdout_scores": {chosen: headline}},
          open("evidence.json", "w"))
HEADLINE = ("roc_auc", headline)
