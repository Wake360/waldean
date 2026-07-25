## Title

I built a linter that catches train/test leakage before it ships — pip install wald-lint

## Body (~150 words)

`pip install wald-lint`, run `wald check notebook.ipynb`, it exits 2
if it finds high-severity issues — wire it into CI and leaky notebooks
fail the build instead of shipping.

It catches: fitting a scaler/imputer/encoder before the train/test
split, running more than a handful of hypothesis tests without
correction, filtering a cohort to survivors and reporting the
conclusion as a population claim, and reporting accuracy on an
imbalanced class without a baseline.

I didn't trust my own eval, so I tested it against real notebooks
pulled from GitHub, not just my own examples. First run: 96% false
positives (full writeup linked). Rebuilt the detectors, ran it again
on the same notebooks: 0 false positives. Then ran it on 60 more,
fresh: 0.89 precision on flags, 12 of 13 flagged notebooks had a real
leak, first honest recall number is 0.60 on the audited subset.

No LLM, no API key needed for the static checks. Static analysis on
your existing notebooks.

Repo + full numbers: github.com/Wake360/wald
