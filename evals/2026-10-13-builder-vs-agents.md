# builder-vs-agents, 2026-10-13

Indicative only. Criteria in `builder-vs-agents/MANIFEST.json`, derived from `agent-baseline-v3/MANIFEST.json` (only `maintenance` and `subscriptions`, only the `temporal` criterion, `agents` replaced by `builder`).

Result: the Builder implements the temporal rule on these two synthetic datasets. Nothing more is claimed.

## Temporal probe, Builder next to v3 Claude

| dataset | Builder (waldean 0.5.0) | v3 Claude (sonnet), default runs |
|---|---|---|
| maintenance | pass (1/1) | 15/15 pass |
| subscriptions | pass (1/1) | 7/15 pass |

The probe is the v3 temporal probe, unchanged: every split behind a reported number trains only on rows earlier than all of its test rows. One Builder run per dataset, because `create/build/run` is deterministic (see below).

## Scorer output

| criterion | datasets | builder fail | failure rate | 95% CI | gate |
|---|---|---|---|---|---|
| temporal | maintenance, subscriptions | 0/2 | 0% | 0%-66% | solved by agents (interval includes 20%) |

The gate column is the v3 gate rule applied to two runs. It is printed by the scorer and has no meaning here.

| run | cli | temporal | headline | waldean check (confident) |
|---|---|---|---|---|
| maintenance-builder-default-0 | waldean 0.5.0 | pass | None | - |
| subscriptions-builder-default-0 | waldean 0.5.0 | pass | None | - |

`headline` is None because the binding sets no `HEADLINE`. The v3 agent prompt does not apply: the Builder got no prompt, only the commands below.

## Scores

Candidate is `HistGradientBoostingClassifier(early_stopping=False)`, baseline is `DummyClassifier(strategy='prior')`. Holdout is the last 20% of distinct time values: for maintenance the last 1196 of 5978 distinct `inspected_at` timestamps, 1201/6000 rows; for subscriptions the last 5 of 23 months, 4068/14759 rows. CV is `TimeSeriesSplit(5)` over the training periods only.

| dataset | model | holdout ROC AUC | holdout average precision | holdout balanced accuracy | CV ROC AUC mean (min-max) | CV average precision mean |
|---|---|---|---|---|---|---|
| maintenance | baseline | 0.500 | 0.026 | 0.500 | 0.500 (0.500-0.500) | 0.163 |
| maintenance | candidate | 0.711 | 0.057 | 0.488 | 0.731 (0.678-0.808) | 0.340 |
| subscriptions | baseline | 0.500 | 0.095 | 0.500 | 0.500 (0.500-0.500) | 0.181 |
| subscriptions | candidate | 0.683 | 0.208 | 0.545 | 0.616 (0.571-0.653) | 0.259 |

For reference, the generator's `trap_check` gives temporal-holdout ROC AUC 0.71 (maintenance, last 25%) and 0.728 (subscriptions, last 6 months).

## What a human supplied

The Builder does not detect ID columns or leaking columns. A human read `columns.csv` and passed:

- maintenance: `--exclude asset_tag --exclude parts_replaced` (ID column, documented post-outcome leak)
- subscriptions: `--exclude account_ref --exclude lifetime_months` (ID column, documented post-outcome leak)

The first maintenance attempt, as the brief wrote it, failed with `several time columns ['asset_tag', 'inspected_at']`: the profile took `asset_tag` for a time column, because `AT-05534` parsed as the year 5534. The scored maintenance run was then created with `--time-column inspected_at`. Commit 6c8e992 fixed the profile: strings that parse to years outside 1900..2100 no longer count as dates. A rerun without `--time-column` (create, build, run into `/private/tmp/waldean-agent-baseline/runs-builder-rerun/maintenance-builder-default-0`) picked only `inspected_at`. Plan, built notebook and metrics are byte-identical, and the executed notebook matches apart from the cell execution timestamps. The scored run stays the original one. Subscriptions needed no `--time-column`.

Commands, with `D=/Users/filipvachek/dev/waldean/scratch/agent-baseline-v2/data` (the main checkout's gitignored scratch; sha256 of both `data.csv` files checked against the v3 MANIFEST) and `R=/private/tmp/waldean-agent-baseline/runs-builder`:

```bash
uv run waldean create $D/maintenance/data.csv --target failed_90d --exclude asset_tag --exclude parts_replaced --time-column inspected_at --out $R/maintenance-builder-default-0
uv run waldean create $D/subscriptions/data.csv --target churn_next_month --exclude account_ref --exclude lifetime_months --out $R/subscriptions-builder-default-0
for r in $R/*-builder-default-0; do uv run waldean build $r && uv run waldean run $r; done
uv run python scripts/agent_baseline.py score --bench builder-vs-agents --runs $R
```

## The one manual edit

For the scorer, each run dir got `evidence/experiment.ipynb` copied to `experiment.ipynb`, with `data.csv` next to it. The only change to the notebook is the `pd.read_csv` path, from the relative path to the scratch CSV to `'data.csv'`. Both datasets have no missing target, so `len(df)` equals the MANIFEST `rows` (6000, 14759) and row positions equal `data.csv` positions, as the binding requires.

Binding, written to `scoring.tsv` before scoring and tied to each notebook's sha256:

```
PROBE_EVALS = [(list(a), list(b), features) for a, b in folds] + [(list(np.flatnonzero(train)), list(np.flatnonzero(test)), features)]
PROBE_HEADLINE = list(np.flatnonzero(test))
PROBE_SELECTED_ON = []
```

## Determinism

After the first build and run of each experiment, `experiment.ipynb` and `evidence/metrics.json` were copied aside. Then, per dataset:

```bash
uv run waldean build $R/<dataset>-builder-default-0
cmp <saved>/<dataset>-build1.ipynb $R/<dataset>-builder-default-0/experiment.ipynb
uv run waldean run $R/<dataset>-builder-default-0
cmp <saved>/<dataset>-metrics1.json $R/<dataset>-builder-default-0/evidence/metrics.json
```

Output: `maintenance build identical`, `maintenance metrics identical`, `subscriptions build identical`, `subscriptions metrics identical`. `cmp` printed nothing and exited 0 in all four cases.

## Limits

Two datasets, both synthetic, from one generator. The Builder was designed after the v3 registration by someone who knows that generator, so passing shows it implements the rule, not that it generalises (MANIFEST `builder_comparison`). The comparison is two deterministic runs against 30 sampled agent runs. The v3 agent was sonnet, not the then-default Claude model. Generalisation needs real datasets and other people running `waldean create` (plan 09 Phase 4).
