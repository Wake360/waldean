# Waldean

**Code linters check style. Waldean checks whether the analysis is a lie.**

[![PyPI](https://img.shields.io/pypi/v/waldean)](https://pypi.org/project/waldean/)
[![CI](https://github.com/Wake360/waldean/actions/workflows/ci.yml/badge.svg)](https://github.com/Wake360/waldean/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/waldean)](https://pypi.org/project/waldean/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/Wake360/waldean/blob/main/LICENSE)

A model scores 0.99. Was the scaler fitted on the test rows? Did the
cross-validation shuffle a time series? Were twenty tests run with no
correction? Waldean reads a notebook or `.py` script and answers those
questions. Each finding names the cell and line, the evidence, what goes wrong
and the fix. It is static analysis: no LLM, no API key, the same input gives
the same output, and it does not run your code.

![waldean check on a time-series notebook](https://raw.githubusercontent.com/Wake360/waldean/v0.6.0/assets/demo.gif)

## Try it

```bash
pip install waldean
waldean check your_notebook.ipynb
```

Exit codes: `0` clean, `1` medium, `2` high, `3` input error. On [`examples/leaky.ipynb`](https://github.com/Wake360/waldean/blob/v0.6.0/examples/leaky.ipynb):

```
$ waldean check examples/leaky.ipynb

# Waldean report — examples/leaky.ipynb

verdict: 1 high, 0 medium | static layer (no LLM)

## HIGH: leakage-fit-before-split
- **Where:** cell 5, line 2
- **Evidence:** `scaler.fit_transform(...)` consumes X, feeding `train_test_split` (cell 5) — the fit happened before the split
- **Flaw:** A transformation (scaler, imputer, encoder, feature selector, PCA, vectorizer) is fitted on data that contains the test set.
- **Failure scenario:** Test metrics are inflated; the production model will underperform the reported numbers.
- **Fix:** Fit the transformer on the training split only; apply transform to the test split.
- **Confidence:** 0.92
- **Repair:** `waldean propose examples/leaky.ipynb` writes a repair contract that an agent or a person can apply and Waldean can verify

## CLEAN (checked): baserate-accuracy-imbalanced, leakage-lag-full-series, leakage-resample-before-split, leakage-temporal-shuffle, leakage-test-selection, testing-multiple-uncorrected
```

[`temporal-cv-before-after.ipynb`](https://github.com/Wake360/waldean/blob/v0.6.0/examples/temporal-cv-before-after.ipynb)
scores one model with shuffled CV and with `TimeSeriesSplit`: how far the flaw moves the number.

## Who it is for

| | |
|---|---|
| Data scientists and ML engineers | Check a notebook before you report its number, and see which cell to change. |
| CI and platform owners | Gate pull requests with the GitHub Action or pre-commit; findings appear as SARIF annotations on the diff. |
| Teachers | Show why a method is unsound with a before/after notebook and the finding that explains it. |
| Coding agents | A skill that gives the agent a methodology checklist and has it run `waldean check` before it reports a metric. |

## What it checks

| Flaw class | What triggers it |
|---|---|
| `leakage-fit-before-split` | A scaler, imputer, encoder, selector or vectorizer is fitted on data that later feeds `train_test_split` or cross-validation |
| `leakage-temporal-shuffle` | Lag or rolling features on time-ordered data, evaluated with a shuffled split instead of `TimeSeriesSplit` or a time cutoff |
| `leakage-test-selection` | A model, feature set or threshold picked by its score on the rows that are then reported as the held-out result |
| `testing-multiple-uncorrected` | Many statistical tests with no multiple-comparison correction; reports the implied family-wise error rate |
| `baserate-accuracy-imbalanced` | Accuracy as the only metric while stored outputs show class imbalance |
| `selection-survivorship-cohort` | Candidate only: a filter on a survival-correlated column before aggregation |

`waldean rules` prints the full list. Misses: [Known limitations](#known-limitations).

## Evidence

| Set | Result | Record |
|---|---|---|
| Mutation corpus: 232 injected flaws, 91 clean notebooks | precision and recall 1.00 per static class, 0 false positives | [`2026-10-13-eval.md`](https://github.com/Wake360/waldean/blob/main/evals/2026-10-13-eval.md) |
| 60 fresh GitHub notebooks, leakage classes | 25 of 28 flags real (0.89); 12 of 20 leaky notebooks caught (0.60) | [`2026-07-07-dogfood-wide.md`](https://github.com/Wake360/waldean/blob/main/evals/2026-07-07-dogfood-wide.md) |
| Yang et al. (ASE'22), 100 notebooks, `pre` label | precision 0.62, recall 0.42 | [`2026-10-13-yang-pre.md`](https://github.com/Wake360/waldean/blob/main/evals/2026-10-13-yang-pre.md) |

Mutants are clean notebooks with one injected flaw, counted only if executing
them proves it (a scaler whose `n_samples_seen_` equals the full row count).
They use canonical idioms; real code is messier, hence rows two and three.
[Method](https://github.com/Wake360/waldean/blob/main/docs/EVALUATION.md).

## Compared with

| | Needs an LLM | Needs a GPU | Multiple testing | Reads stored outputs |
|---|---|---|---|---|
| Waldean | no | no | yes | yes |
| [SciCode-Lint](https://arxiv.org/abs/2603.17893) | yes (Qwen3-8B) | 16 GB | no | no |
| A chat LLM or coding agent asked to review | yes | no | if asked | if given them |

Three of SciCode-Lint's 66 patterns overlap Waldean classes. Any tool can be
scored on the Waldean corpus: [`docs/benchmark.md`](https://github.com/Wake360/waldean/blob/main/docs/benchmark.md).

## Use it in CI, pre-commit or an agent

GitHub Action, gating on high findings
([full workflow with SARIF upload](https://github.com/Wake360/waldean/blob/main/docs/ci.md)):

```yaml
- uses: Wake360/waldean@v0.6.0
  with:
    paths: notebooks/
    fail-on: high
```

pre-commit (`waldean` for `.ipynb`, `waldean-scripts` for `.py`):

```yaml
repos:
  - repo: https://github.com/Wake360/waldean
    rev: v0.6.0
    hooks:
      - id: waldean
      - id: waldean-scripts
```

Coding agents: a [skill](https://github.com/Wake360/waldean/blob/main/skills/waldean/SKILL.md) for agents that read `SKILL.md`.

```bash
/plugin install waldean --marketplace Wake360/waldean   # in Claude Code
npx skills add Wake360/waldean                          # other agents
```

With the checklist and `waldean check`, Claude Code built a valid experiment in
79 of 80 runs, against 25 of 32 without, on synthetic data with planted traps
([indicative](https://github.com/Wake360/waldean/blob/main/evals/2026-10-14-agent-protocol.md)).
A [hook](https://github.com/Wake360/waldean/blob/main/docs/agent-gate.md) can block any edit that adds a high finding.

## Experimental

- Repair loop: `waldean propose` writes a repair contract for
  `leakage-temporal-shuffle` and `leakage-fit-before-split`, and `waldean
  verify` checks the repair. With `--execute` it compares the metric before
  and after. Read the [limits](https://github.com/Wake360/waldean/blob/main/docs/repair.md)
  before you trust a verified status.
- Experiment builder: `waldean experiment data.csv --target y` writes a notebook with a split and
  pipeline chosen from the data ([details](https://github.com/Wake360/waldean/blob/main/docs/cli.md#experiment-builder-experimental)).
- Narrative layer: `--llm` checks prose claims against the computation. Its quality
  gates never ran; [no numbers are claimed](https://github.com/Wake360/waldean/blob/main/docs/ARCHITECTURE.md).

## Known limitations

- Misses on real code: a split returned from a helper or reached more than one
  helper level deep, test data known only by name, a manual `KFold.split`
  loop, files over the input size cap, and Python 2 cells. A scaler fitted on
  all rows that feeds `cross_val_score` is reported only as a candidate below
  the 0.8 floor, by design.
- The 0% false-positive rate holds on the curated corpus. Real-notebook
  evidence covers the leakage classes only.
- Flaws with no trace in code, outputs or prose are invisible to Waldean.
- Waldean runs your code only with `waldean check --probe`,
  `waldean verify --execute` or `waldean experiment --run`.

[All docs](https://github.com/Wake360/waldean/blob/main/docs/README.md) ·
[Contributing](https://github.com/Wake360/waldean/blob/main/CONTRIBUTING.md) · MIT license
