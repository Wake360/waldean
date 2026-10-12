# Show HN submission

**URL:** https://github.com/Wake360/wald/blob/main/posts/2026-07-04-i-mutation-tested-statistical-malpractice.md

## Title (primary)

Show HN: I mutation-tested a linter for statistical malpractice, it was 96% wrong

(78 chars)

## Title alternatives

1. Show HN: wald – a linter that checks whether your data analysis is a lie (76 chars)
2. Show HN: My linter scored 1.00 on its own eval, then failed on real notebooks (77 chars)

## First comment (~150 words)

wald is a static linter for data-analysis notebooks. It checks for
train/test leakage, uncorrected multiple testing, survivorship bias,
and accuracy claims on imbalanced classes without a baseline. Static
layer only, no LLM, no API key, runs in CI, exits 2 on high-severity
findings.

I built it by mutation testing: inject a named statistical flaw into a
clean notebook, mechanically verify the flaw actually happened (e.g.
the scaler's `n_samples_seen_` really covers the full dataset), then
check whether the detector catches it. On the synthetic mutant corpus
it scored precision 1.00. On 34 real notebooks pulled from GitHub it
flagged 17, and only 3 of those 124 flags were real leaks — a 96%
false-positive rate. The post is about what broke and what I rebuilt
because of it.

A second, wider dogfood run (60 more notebooks) is in the post as a
dated addendum: 0.89 flag precision, 0.60 recall on the audited
subset, leakage classes only. Ground truth there is adversarial LLM
review, not expert human labeling — I say so in the post.

Feedback on the detector logic or the eval methodology welcome.
