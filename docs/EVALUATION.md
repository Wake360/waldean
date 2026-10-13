# Evaluation

## How Waldean proves it works: mutation testing for statistics

The detector is not measured by demos. A **mutation corpus** exists before
the detectors do: clean notebooks get named flaws programmatically injected
(via libcst, format-preserving), and every mutant must *mechanically prove*
the flaw is present before it enters the corpus — e.g. a leakage mutant is
executed and the scaler's `n_samples_seen_` must equal the full row count
(it saw the test set), not the train count.

Detection quality is then a confusion matrix per flaw class, not an opinion:

| class (static layer) | mutants | TP | FN | FP | precision | recall |
|---|---|---|---|---|---|---|
| leakage-fit-before-split | 48 | 48 | 0 | 0 | 1.00 | 1.00 |
| leakage-temporal-shuffle | 16 | 16 | 0 | 0 | 1.00 | 1.00 |
| leakage-test-selection | 16 | 16 | 0 | 0 | 1.00 | 1.00 |
| testing-multiple-uncorrected | 96 | 96 | 0 | 0 | 1.00 | 1.00 |
| baserate-accuracy-imbalanced | 8 | 8 | 0 | 0 | 1.00 | 1.00 |
| selection-survivorship-cohort (candidate) | 16 | 16 | 0 | — | — | 1.00 |

False-positive rate on the 91-notebook clean corpus (64 synthetic + 27
hand-reviewed real notebooks from Apache-2.0/MIT repositories): **0.0%**.
The 27 real notebooks also shaped the static layer during dogfood (the
rebuild described below), so this is not an out-of-sample test for them —
the real-notebook share of the 0.0% leans optimistic.
One of the 27, `00__ageron_handson-ml3__03_classification.ipynb`, is
clean only at the 0.8 floor. It fits stateful preprocessing on the full
training set before `cross_val_score`, which a later review judged a real
leak (`evals/2026-07-08-llm-dogfood-subscription.md`). The static layer
reports those sites as 0.75 candidates, so they do not count against the
0.0%.
232/232 mutants passed mechanical verification at build; 0 discarded.
Half of the fit-before-split mutants are a hand-written z-score over the
full frame (verified by the all-rows mean and unit standard deviation of
the pre-split matrix), the other half a scaler fit on the full frame
(verified by `n_samples_seen_`).
32 of the 232 are narrative-only mutants (regression-to-mean-claim,
significance-meaningless); they are scored by the `--llm` eval, not by
this table, and no numbers are claimed for them until its gates run.
(Eval 2026-10-13, `evals/2026-10-13-eval.json`.)

Reproduce: `waldean corpus build && waldean eval`. Dated reports live in `evals/`.
Set `WALDEAN_BUILD_DATE=YYYY-MM-DD` to pin the manifest/report date for a byte-identical rebuild.

**Dogfooded on real notebooks** (`evals/2026-07-04-dogfood.md`): the first
run on 34 real notebooks produced a 50% file flag rate — 119 of 124 flags
were false positives, hand-reviewed one by one. The detector was rebuilt
from that data (flow-sensitive dataflow, transformer/estimator distinction,
CV-aware sinks). After the fix: 3 confident flags on the same 34 notebooks,
all three confirmed real leaks, 0 known false positives. The report keeps
the full failure taxonomy; the 27 clean notebooks entered the corpus with
licenses recorded per file.

**Wider dogfood — first recall and precision numbers**
(`evals/2026-07-07-dogfood-wide.md`): 60 fresh GitHub notebooks, none
of them among the 34 notebooks of the first dogfood. waldean flagged 13; adversarial review
confirmed 25 of 28 flags real (**0.89 flag precision**, 12 of 13 flagged
notebooks genuinely leaky) and, over a seeded 30-notebook miss-hunt
sample of the un-flagged set, found 8 leaks waldean missed — **0.60
notebook-level recall** across the 43-notebook audited subset. Two of the
8 were reported as below-floor candidates (a scaler fit on full data
feeding `cross_val_score`); the other six left no flag or candidate at the
missed site. 33
confirmed leak instances across 20 notebooks, all in the two leakage
classes (28 `leakage-fit-before-split`, 5 `leakage-temporal-shuffle`).

**Honest caveats:** the recall evidence is leakage-only — this sample
produced zero confirmed real instances of the testing or base-rate
classes, so no real-world recall is claimed for them. The one false
positive (an RFECV scout-subsample pattern) shows the corpus's 0.0% FP
does not carry to messy real code; 0.60 recall is a one-seed subset
estimate, upper-leaning. Ground truth is multi-agent adversarial review,
not expert human labeling.

## What Waldean sees (v1) and what it doesn't

The static layer (deterministic, no API key, runs in CI) decides four
classes on its own:

- `leakage-fit-before-split` — flow-sensitive def-use dataflow: a
  *transformer* (not a model) is fitted on data whose transformed output
  feeds `train_test_split`, or transforms a split part after a full-data
  fit. Cross-validation counts as an evaluation sink: supervised selection
  fitted on the CV data (`SelectKBest.fit(X, y)` → `cross_val_score`) is a
  confident flag; unsupervised pre-CV fits (scaler/PCA) stay below the
  floor as candidates. Pandas self-statistic imputation before the split
  (`df[c].replace(0, df[c].median())`) is covered. Pipelines passed to CV,
  fits on the train split, label encoding and estimator fits are not
  flagged — each of those idioms was a measured false-positive class in
  the dogfood report.

  Function inlining limits: a call to a notebook-level function is
  inlined one level deep; a helper called from inside a helper is not
  inlined.
  Only positional parameters are renamed to the call's arguments;
  keyword-only and positional-only parameters and keyword arguments are
  not. Assignments inside the helper appear as notebook-level names at the
  call site, so a helper local can shadow a notebook name of the same
  spelling (a known imprecision). Return values are not bound, so
  `train, test = split(df)` does not carry the helper's split. `.pipe`
  is inlined when its first argument is a named function or a lambda.

- `leakage-temporal-shuffle` — time-ordered data with lag/rolling-window
  features (`shift`, `rolling`, `diff`, `pct_change`, …) split by a
  shuffled protocol — default `train_test_split`, shuffled `KFold` —
  instead of `TimeSeriesSplit`, `shuffle=False`, or a temporal cutoff.
  Signals are evaluated per evaluation sink on that sink's dependency
  chain: a date column alone never fires, bare `scipy.ndimage.shift` /
  `sklearn.utils.resample` / `np.diff` never fire, and a frame sorted on
  a non-date key with neighbor-comparison features never fires.
- `testing-multiple-uncorrected` — counts statistical test call sites
  (loops weighted), checks for corrections, reports the implied FWER.
- `baserate-accuracy-imbalanced` — accuracy as the only metric while class
  imbalance is visible in stored `value_counts` outputs.

It additionally emits a low-confidence **candidate** for
`selection-survivorship-cohort` (a filter on a survival-correlated column
followed by aggregation). Deciding that class requires the narrative layer
— the flaw is the *pair* (filter, population claim); the filter alone is
legitimate analysis.

**What Waldean does not see:** flaws with no imprint in code, outputs or
prose. Survivorship bias that lives in data that never entered the notebook
is invisible to any tool that reads notebooks. Waldean claims only the
detectable classes, and the taxonomy (`waldean/core/taxonomy/flaws.yaml`) is the
complete, versioned list of what it checks.

`.py` scripts have no stored cell outputs, so `baserate-accuracy-imbalanced`
(which reads a `value_counts` output) can only ever emit a below-floor
candidate on a script, never a confident flag. `--llm` needs markdown cells
to check claims against computation, so it is meaningful on percent-format
scripts and not on plain scripts, which have none.

