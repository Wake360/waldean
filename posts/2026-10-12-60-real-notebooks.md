# 60 real notebooks: what static analysis can and cannot do

I ran Wald, a static leakage linter, on 60 notebooks it had never seen.
Wald reads code and never executes it. This post covers what it caught,
what it missed, and why the misses look the way they do. Every number
here comes from one eval file, linked at the end.

## Setup

The 60 notebooks came from GitHub, spread across five buckets:
supervised feature-selection code, Kaggle-style competition work, time
series, accuracy on imbalanced classes, and broad ML tutorials. They were
deduplicated by code-cell hash against the notebooks used in earlier
runs and against Wald's own real-notebook corpus. There were 0
duplicates. Running `wald check` over all 60 gave 0 crashes and 0 parse
failures.

The eval is aggregate. No notebook or author is named, and 37 of the 60
had no permissive license, so none of them is reproduced here. The
[anonymized ledger](https://github.com/Wake360/wald/blob/main/evals/real-flaws.tsv)
has one row per confirmed leak: an anonymized notebook id, the flaw
class, the license, whether Wald flagged it or missed it, and why the
reviewer judged it real.

Review had three parts. One reviewer judged every flag in every flagged
notebook as true or false. Miss-hunters searched a stratified random
sample of 30 of the 47 unflagged notebooks (seed 42) for leaks Wald did
not report. Then an adversarial verifier went over every claimed true
positive and every claimed miss. It defaulted to "refuted" unless the
leak was airtight.

One caveat before the numbers. All of these reviewers were LLM agents.
Ground truth here is multi-agent adversarial review, not expert human
labeling. The clear cases (fit on full data, then split, then report a
metric) were unambiguous. One miss is contested, and I mark it below.

## Results

| measure | value |
|---|---|
| notebooks scanned | 60 |
| notebooks flagged | 13 |
| flags | 28 |
| flags confirmed real | 25 |
| precision, per flag (leakage classes) | 0.89 |
| flagged notebooks with a real leak | 12 of 13 (0.92) |
| audited subset | 43 notebooks (13 flagged + 30 sampled) |
| leaky notebooks in the audited subset | 20 |
| leaky notebooks caught | 12 |
| recall (audited subset, leakage classes) | 0.60 |

Both headline numbers are narrow. The 0.89 precision and the 0.60 recall
hold for the audited subset and for the leakage classes only. Recall is
measured over the 43-notebook audited subset at one seed. The 17
unflagged notebooks that were not sampled may hide more misses, so
recall over all 60 is likely lower, not higher.

The confirmed leaks were 33 instances across 20 notebooks, and all of
them were leakage: 28 fit-before-split instances in 17 notebooks, and 5
temporal-shuffle instances in 4 notebooks. One notebook alone contributed
8 of the 28 fit-before-split instances, eight per-column scaler fits on
full data in a single cell.

## The three flags that did not survive

**An RFECV scout subsample.** The notebook called `fit_transform` on
`X_train`, which was already split off. A later `train_test_split` only
carved a feature-selection scout set out of that training data and then
discarded it. Wald saw a fit before a split call and flagged it. It
cannot tell which split is the evaluation split, so it treated a
throwaway split as the real one. This is a new false-positive idiom.

**A target-side `y.fillna`.** Wald read filling missing values in the
label vector as a feature transform. Imputing `y` is its own question,
but it is not the feature leak Wald claimed.

**A duplicate scaler flag.** One borderline flag repeated a scaler leak
that was already reported. The leak was real; the second flag added
nothing.

Corpus evals give Wald a 0.0% false-positive rate on curated clean
notebooks. That number does not transfer. On messy real code Wald is not
perfect, and these three flags show where it slips.

## The eight misses

Miss-hunting found 8 real leaks that Wald did not flag, each in a
different notebook. None of them has a name-level syntactic anchor the
static layer keys on. The snippets below are written fresh to show each
idiom. They are not copied from any notebook.

**Per-group imputation before the split.** A group median is computed
over every row, test rows included.

```python
df["Age"] = df.groupby("Title")["Age"].transform(lambda s: s.fillna(s.median()))
X_train, X_test, y_train, y_test = train_test_split(X, y)
```

**Column-mean `fillna` before the split.** The mean is a statistic of
the whole dataset, so the test rows shape the training features.

```python
df["LotFrontage"] = df["LotFrontage"].fillna(df["LotFrontage"].mean())
X_train, X_test, y_train, y_test = train_test_split(X, y)
```

**A scaler fit on full data that feeds `cross_val_score`.** There is no
`train_test_split` call to anchor on. The folds exist only inside
`cross_val_score`, and every fold was scaled with statistics from all of
them.

```python
X_scaled = StandardScaler().fit_transform(X)
scores = cross_val_score(model, X_scaled, y)
```

**TF-IDF and SVD fit on the whole corpus.** The vocabulary, the IDF
weights and the SVD components all see the test documents.

```python
tfidf = TfidfVectorizer().fit_transform(all_texts)
reduced = TruncatedSVD().fit_transform(tfidf)
```

**One-hot keys from `get_dummies` on combined data (contested).** The
encoded columns come from categories that appear in the test set. This
one survived refutation, but the eval marks it as contested. Treat it
that way.

```python
keys = pd.get_dummies(pd.concat([train, test])["city"]).columns
```

**Temporal leaks inside cross-validation and helpers.** Two misses were
temporal-shuffle leaks. One ran `StratifiedKFold` and `cross_val_score`
on lag and rolling-window features of time-ordered data. The other sat
inside a demand-forecast training helper.

```python
df["lag_one"] = df["demand"].shift()
cross_val_score(model, df[features], df["target"], cv=StratifiedKFold())
```

## What this says about static analysis

Static analysis catches leaks that have a syntactic anchor. A named
transformer such as `StandardScaler`, a `fit_transform` call, and a
`train_test_split` call later in the dataflow give a linter something to
connect.

It misses leaks expressed as pandas arithmetic. `groupby().transform()`,
`fillna(df[col].mean())` and `get_dummies` compute a statistic over all
rows without any object that looks like a fitted transformer. It also
misses splits that happen inside `cross_val_score` or inside a helper
function. Closing these gaps needs deeper dataflow or reading the
notebook's claims, not more name-based heuristics.

The gap is not total. The ledger shows some pandas statistics that Wald
did flag, including a column-mean `fillna`. The eval does not say why
one was caught and a similar one missed.

The sample also produced zero confirmed real instances of the multiple
testing and base-rate classes (uncorrected tests, accuracy on imbalanced
classes). Wald has detectors for both, but this run cannot say how they
do on real code. No real-world recall is claimed for them.

The practical reading for anyone using Wald: a flag is usually worth
reading, and a clean report is not evidence of a clean notebook. In the
audited subset, 8 of the 20 leaky notebooks came back with no flag at
all. Treat Wald as a check that finds some leaks, not a certificate.

Sources skew toward small personal and competition repos. These are not
production pipelines.

## What I would want from you

A notebook where Wald is wrong. If it missed a leak you can point to,
open a [missed-issue report](https://github.com/Wake360/wald/issues/new?template=missed_issue.md).
If it flagged something that is not a leak, open a
[false-positive report](https://github.com/Wake360/wald/issues/new?template=false_positive.md).
A minimal snippet that reproduces the idiom is enough.

## Try it

```bash
pip install wald-lint
wald check notebook.ipynb
```

The code is at [github.com/Wake360/wald](https://github.com/Wake360/wald).
The full eval this post is built from is
[evals/2026-07-07-dogfood-wide.md](https://github.com/Wake360/wald/blob/main/evals/2026-07-07-dogfood-wide.md).
