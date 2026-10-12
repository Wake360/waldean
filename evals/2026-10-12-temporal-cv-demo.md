# Temporal-CV demo run — 2026-10-12

Notebook: `examples/temporal-cv-before-after.ipynb`, built by `scripts/build_temporal_demo.py`.

```
shuffled KFold: R2=0.992 MAE=2.98
TimeSeriesSplit: R2=0.465 MAE=9.82
```

Python 3.12.15 on Darwin.

- numpy 2.5.0
- pandas 3.0.3
- scikit-learn 1.9.0

Seeds: data `default_rng(7)`, `KFold(random_state=0)`, `RandomForestRegressor(random_state=0)`.
The data is synthetic. The gap shows the protocol effect on this series, not a typical real-world size.
