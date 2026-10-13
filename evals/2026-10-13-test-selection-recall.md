# leakage-test-selection recall on agent-baseline-v3, 2026-10-13

In-sample. The three fixes below were designed from these 60 notebooks. Held-out recall is unknown until a new agent run.

## Result

Ground truth is the first-rater `selection` column in `agent-baseline-v3/results.tsv` (28 fail, 32 pass). Waldean flags counted at confidence 0.8 or higher, from `waldean check --format json` on each notebook in `agent-baseline-v3/runs/`.

| | ruling fail | ruling pass |
|---|---|---|
| flagged | 12 | 0 |
| not flagged | 16 | 32 |

| | precision | 95% CI | recall | 95% CI |
|---|---|---|---|---|
| before (`2026-10-13-agent-baseline-v3.md`) | 10/10 | 72%-100% | 10/28 | 21%-54% |
| after | 12/12 | 76%-100% | 12/28 | 27%-61% |

Intervals are Wilson 95%, from `wilson()` in `scripts/agent_baseline.py`.

The two new hits are control-claude-default-11 and clinic-claude-default-5. No new false positive. control-claude-default-9 was flagged by an earlier version of fix A and is no longer: its pick compares `res.loc['logistic regression','ROC AUC'] >= res.loc['gradient boosting','ROC AUC']-0.005`, and the narrowed if/else rule requires both compared operands to be bare subscripts with no numeric constant. The narrowing removes 0.9 flags on ordinary if/else code that selects nothing (verdict labels, PASS/FAIL, display counts, bar colours).

## Misses by class

Run names are short forms of `<dataset>-claude-default-<n>`.

| class | runs | count | static? | after |
|---|---|---|---|---|
| A: if/else pick comparing two lookups into a score table | control-9 | 1 | yes, without a margin | missed (margin `-0.005`) |
| B: label aliased through `.values`, so a real hit was demoted to a 0.6 candidate | control-11 | 1 | yes | flagged |
| C: user-defined metric wrapper; the wrapper's first argument was misread as the label | clinic-5 | 1 | yes | flagged |
| D: model name hardcoded after a printed score table; the choice is made in prose | clinic-10, -12, -14, control-7, -8, -10, -14 | 7 | no | missed |
| E: gradient boosting headlined by literal name, with no stated pick | maintenance-0, -1, -4, -7, -11, -12, -13 | 7 | no | missed |
| F: feature set fixed by a literal assignment; the reason is in a comment | subscriptions-8 | 1 | no | missed |

## Second-rater sensitivity

The second rater saw 24 of the 60 notebooks and ruled 5 of the misses as pass: control-7, control-10, maintenance-0, maintenance-11 and maintenance-12. Excluding them, recall is 12/23 = 52% (95% CI 33%-71%). This drops only the disagreements in that sample; the 36 unsampled notebooks keep the first rater's ruling. This figure is in-sample too.

## Remaining misses

The 15 D, E and F misses have no dataflow edge from the scores to the chosen name. A person reads the table and types the winner. The obvious proxy, a subscript keyed by a literal model name, appears in 28/32 pass notebooks and 23/28 fail notebooks, so it cannot be used. These need the narrative layer (claim to computation). They are not a static detector target. Count reproduced with this command (pass/fail from the `selection` column of `results.tsv`, a notebook counts if any code cell matches):

```bash
python3 -c "import csv,json,re,sys; R=re.compile(sys.argv[1]); v={r['run']:r['selection'] for r in csv.DictReader(open('evals/agent-baseline-v3/results.tsv'),delimiter='\t')}; h={k:any(R.search(''.join(c['source'])) for c in json.load(open(f'evals/agent-baseline-v3/runs/{k}.ipynb'))['cells'] if c['cell_type']=='code') for k in v}; [print(s, sum(h[k] for k in v if v[k]==s), sum(v[k]==s for k in v)) for s in ('pass','fail')]" "(?i)\[\s*['\"][^'\"]*(?:boost|logistic|forest|gbm|xgb|lgbm|hgb|lr|rf|gb)[^'\"]*['\"]\s*[],]"
```

## Notes

- Fixes, on branch test-selection-recall: if/else picks between two literal keys of a score table, `.values` and `.T` label aliases, labels resolved inside user metric wrappers, and one flag per selection line.
- 12/28 is what these three fixes reach on v3, not a proven static ceiling. It is in-sample: the fixes were designed from these exact notebooks. It is not a held-out recall, and no README or public text may present it as one.
- Corpus eval after the fixes is unchanged (`2026-10-13-eval.md`): `leakage-test-selection` 16/16, no FP, no other class moved. Gates G0/G1 pass.
- Per-notebook results came from `waldean check` and agree with a direct detector call on the same notebooks.
