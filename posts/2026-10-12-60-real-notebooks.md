# 60 real notebooks: what static analysis can and cannot do

I ran Waldean, a static leakage linter, on 60 notebooks it had never seen.
Waldean reads code and never executes it. This post covers what it caught,
what it missed, and why the misses look the way they do. Every number
here comes from two files in the repo, both linked at the end: the eval
report and its anonymized ledger of confirmed leaks.

## Setup

The 60 notebooks came from GitHub, spread across five buckets:
supervised feature-selection code, Kaggle-style competition work, time
series, accuracy on imbalanced classes, and broad ML tutorials. They were
deduplicated by code-cell hash against the notebooks used in earlier
runs and against Waldean's own real-notebook corpus. There were 0
duplicates. Running `waldean check` over all 60 gave 0 crashes. Nine
notebooks had cells Waldean could not parse, three of them Python 2 code,
so their results were partial.

The eval is aggregate. No notebook or author is named, and 37 of the 60
had no permissive license, so none of them is reproduced here. The
[anonymized ledger](https://github.com/Wake360/waldean/blob/main/evals/real-flaws.tsv)
has one row per confirmed leak: an anonymized notebook id, the flaw
class, the license, whether Waldean flagged it or missed it, and why the
reviewer judged it real.

Review had three parts. One reviewer judged every flag in every flagged
notebook as true or false. Miss-hunters searched a stratified random
sample of 30 of the 47 unflagged notebooks (seed 42) for leaks Waldean did
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
discarded it. It was not the evaluation split. The eval logs this as a
new false-positive idiom. My reading, not a finding of the eval: a fit
followed by a split call looks like a leak unless the tool knows which
split feeds the metric.

**A target-side `y.fillna`.** The eval describes this flag as a
target-side `y.fillna` mistaken for a feature transform.

**A target encoder flag.** The third flag was a one-hot encoder fitted
on the target column of the full training frame. The same notebook had a
second flag that was a real leak. The eval first described this one as a
duplicate scaler flag and corrected that on 2026-10-13.

Corpus evals give Waldean a 0.0% false-positive rate on curated clean
notebooks. That number does not transfer. On messy real code Waldean is not
perfect, and these three flags show where it slips.

## The eight misses

Miss-hunting found 8 real leaks that Waldean did not flag, each in a
different notebook. Five have no name-level syntactic anchor the static
layer keys on. Two are a scaler fit on full data that feeds
`cross_val_score`. Waldean saw both and reported them as candidates at
confidence 0.75, below its 0.8 reporting floor. That floor is a
deliberate choice from the first dogfood, where reviewers disagreed on
whether pre-CV scaling is a leak worth flagging. The last one, a TF-IDF
and SVD fit, sits in a Python 2 notebook where most cells could not be
parsed. The snippets below are written fresh to show each idiom. They
are not copied from any notebook.

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

**A scaler fit on full data that feeds `cross_val_score` (two
notebooks).** Every fold is scaled with statistics computed over all of
them. Waldean reports this as a candidate below the floor.

```python
X_scaled = StandardScaler().fit_transform(X)
scores = cross_val_score(model, X_scaled, y)
```

**TF-IDF and SVD fit on the whole corpus.** The vocabulary, the IDF
weights and the SVD components all see the test documents. Waldean missed
this one because the notebook is Python 2. With the `print` statements
rewritten, it reports both fits as candidates below the floor.

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

Most of what Waldean caught had a syntactic anchor: a named transformer
such as `StandardScaler`, a `fit_transform` call, and a
`train_test_split` call later in the dataflow.

The misses are a mix of idioms. Some are pandas code,
`groupby().transform()`, `fillna(df[col].mean())` and `get_dummies`,
that computes a statistic over all rows without a fitted transformer
object. Two are temporal leaks inside cross-validation or a training
helper. The eval's view is that closing these gaps needs narrative fusion
or new dataflow, not more static heuristics. The two scaler cases are
different: Waldean sees them and holds them below the floor, so they are
a threshold choice, not a blind spot. The TF-IDF and SVD case is a parse
gap: the notebook is Python 2.

The gap is not total. The ledger shows some pandas statistics that Waldean
did flag, including a column-mean `fillna`. The eval does not say why
one was caught and a similar one missed.

The sample also produced zero confirmed real instances of the multiple
testing and base-rate classes (uncorrected tests, accuracy on imbalanced
classes). Waldean has detectors for both, but this run cannot say how they
do on real code. No real-world recall is claimed for them.

The practical reading for anyone using Waldean: a flag is usually worth
reading, and a clean report is not evidence of a clean notebook. In the
audited subset, 8 of the 20 leaky notebooks came back with no flag at
all. Treat Waldean as a check that finds some leaks, not a certificate.

Sources skew toward small personal and competition repos. These are not
production pipelines.

## What I would want from you

A notebook where Waldean is wrong. If it missed a leak you can point to,
open a [missed-issue report](https://github.com/Wake360/waldean/issues/new?template=missed_issue.md).
If it flagged something that is not a leak, open a
[false-positive report](https://github.com/Wake360/waldean/issues/new?template=false_positive.md).
A minimal snippet that reproduces the idiom is enough.

## Try it

```bash
pip install waldean
waldean check notebook.ipynb
```

The code is at [github.com/Wake360/waldean](https://github.com/Wake360/waldean).
The full eval this post is built from is
[evals/2026-07-07-dogfood-wide.md](https://github.com/Wake360/waldean/blob/main/evals/2026-07-07-dogfood-wide.md).
