## Title

[P] I mutation-tested a statistical-malpractice linter against real notebooks — 96% false-positive rate, then a rebuild, then a wider dogfood run

## Body (~200 words)

wald is a static linter for data-analysis notebooks: train/test
leakage, uncorrected multiple testing, survivorship bias, accuracy
claims on imbalanced classes with no baseline. No LLM, no API key,
runs in CI, exit code 2 on high-severity findings.

Detection quality was measured with mutation testing borrowed from
compiler-land: start from a clean notebook, inject a named flaw
programmatically, mechanically verify the flaw actually happened
(the scaler's `n_samples_seen_` must equal the full row count, a
multiple-testing mutant must really run more than five uncorrected
tests), then check detection. 64/64 mutants passed verification. On
that synthetic corpus: precision 1.00, recall 1.00, per flaw class,
confusion matrix in the linked post.

Then contact with real code. Run 1: 34 GitHub notebooks, 17 flagged,
124 flags, only 3 confirmed real (96% false positives). The idiom
breakdown — fit-on-train-only misclassified, estimators confused with
transformers, name reuse across sections, CV's internal splits
punished — drove a rebuild. Post-rebuild on the same 34: 3 flags, 0
false positives, all reviewer-confirmed.

Run 2 (wide dogfood, dated addendum in the post): 60 more notebooks,
13 flagged, 28 flags, 25 confirmed real (0.89 precision), 12/13
flagged notebooks genuinely leaky. First recall number: 0.60 over a
43-notebook audited subset (13 flagged + 30 miss-hunted), leakage
classes only. One new false-positive idiom (RFECV scout-subsample)
showed the corpus's 0.0% FP rate doesn't generalize.

Ground truth throughout is adversarial LLM review (separate TP/FP
reviewer, miss-hunter, and refutation pass), not expert human
labeling. Said explicitly in the post and here.

Repo: github.com/Wake360/wald
