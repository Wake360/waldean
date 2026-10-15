# CLI details

```bash
waldean check notebook.ipynb            # exit 0 clean / 1 medium / 2 high / 3 input or usage error
waldean check analysis.py               # plain script, or percent-format (# %% cell markers)
waldean check notebooks/ --keep-going   # continue past unreadable files; exit 3 if any file failed
waldean check notebook.ipynb --format json   # one object; a JSON array for several files
waldean rules                           # the flaw classes; --format json for machines
```

## Inputs

Directory arguments collect only `*.ipynb`. Pass a `.py` file explicitly.

Reported lines for `.py` input are file-absolute, not relative to the cell.
The markdown report keeps `cell N, line M`, where `N` is the percent-cell's
position in the file. A `.py` file without `# %%` markers is one cell.

## Errors

By default `waldean check` stops at the first unreadable file. `--keep-going`
continues: each unreadable file is reported on stderr, and the run still exits
3 if any file failed, even when another file has a high finding that would
otherwise exit 2. The multi-file summary line gains a `, N failed` suffix.

## Execution

Waldean reads code and stored outputs. It runs your code only with
`waldean check --probe`, `waldean verify --execute` or `waldean experiment
--run`. Corpus notebooks it wrote itself are executed at corpus build time to
verify mutations.

## `--probe`

For `leakage-fit-before-split`, `--probe` runs an `.ipynb` up to the split in a
separate `waldean-verify` kernel and reads the fitted transformer's
`n_samples_seen_`. Confidence goes up when the fit saw every row and down when
it saw fewer. Candidates below the floor keep their confidence and gain only
the measurement note. The probe runs your code with your permissions.

## Experiment builder (experimental)

```bash
pip install 'waldean[builder]'
waldean experiment data.csv --target churn          # plan.yaml, design.md, experiment.ipynb in data-experiment/
waldean experiment data.csv --target churn --run    # also executes it and writes evidence/
```

The builder reads the CSV and picks the task (binary, multi-class or
regression, from the target), the split (time column, then repeated-entity
column, then stratified or random) and the metrics (never accuracy). It
excludes constant, identifier, high-cardinality and target-leaking columns and
prints each exclusion with the flag that reverses it (`--keep COL`). Every
notebook is a `ColumnTransformer` plus model pipeline fitted inside each fold.
`design.md` gives the reasons, and `waldean check` runs on the result.
Overrides: `--task`, `--time-column`, `--group-column COL|none`, `--exclude`,
`--keep`. Leak detection is near-perfect correlation or purity against the
target only; a weaker future-derived feature passes.

Measured with the v3 temporal probe on two synthetic datasets: the earlier
temporal-only builder passed on maintenance and subscriptions (1/1 each).
Claude sonnet default runs passed 15/15 on maintenance and 7/15 on
subscriptions. Indicative only: one deterministic builder run per dataset
against 30 sampled agent runs, scored at commit 15c61d3; later renderer changes
mean a fresh build differs
([`evals/2026-10-13-builder-vs-agents.md`](../evals/2026-10-13-builder-vs-agents.md)).

`--run` executes the notebook in the `waldean-verify` kernel with
secret-looking environment variables hidden. It is not a sandbox.
