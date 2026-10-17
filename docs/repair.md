# Repair loop (experimental)

For a shuffled split on time-ordered data (`leakage-temporal-shuffle`) and for
a transformer fitted before the split (`leakage-fit-before-split`), `waldean
propose` writes a repair contract. A coding agent or a person applies it, and
`waldean verify` checks the result. With `--diff`, `propose` also writes
`patch.diff` when the fix is mechanical; today that is only
`X = scaler.fit_transform(X)` followed by a four-target
`train_test_split(X, ...)`.

```bash
waldean propose forecast.ipynb
claude -p "$(cat .waldean/repairs/forecast--leakage-temporal-shuffle/brief.md)"
waldean verify .waldean/repairs/forecast--leakage-temporal-shuffle
pip install 'waldean[execute]'
waldean verify .waldean/repairs/forecast--leakage-temporal-shuffle --execute --metric 'R2=(-?\d+\.\d+)'
```

`verify` rejects edits outside the cells the contract names, a deleted
evaluation call, a finding that is still there, and a new confident finding of
a class the original did not have. With `--execute` it runs the original and
the repaired notebook and records both metrics, package versions and file
hashes in `evidence.json`. A repair is `static-pass` without execution and
`verified` with it. Neither status says the new number is right.

## Evidence

On the mutation corpus the verifier accepted all 16 true temporal-shuffle
repairs and all 48 true fit-before-split repairs, and rejected all 48 and all
144 constructed bad repairs of three kinds (file unchanged, edit outside the
scope, evaluation call deleted). `propose --diff` wrote a patch for the 24
fit-before-split mutants in the scaler form, and all 24 patched notebooks
passed the static check
([`evals/2026-10-13-repair-loop.md`](../evals/2026-10-13-repair-loop.md)).
Agent trial: 5 of 5 demo runs verified, 2 of 2 real notebooks static-pass,
N=7, indicative
([`evals/2026-10-13-repair-trial.md`](../evals/2026-10-13-repair-trial.md)).

## Limits

Two flaw classes so far. Comparison is cell by cell, so an added cell is
rejected. `--execute` runs code on your machine with your permissions. It hides
secret-looking environment variables and isolates nothing else. `verify`
trusts the files in the repair directory, so do not let the agent write there.
The static check reads names and literal arguments, not behaviour, so a
disguised split can pass; read the delta in `evidence.json`.
`train_test_split(shuffle=False)` on rows not sorted by time passes the static
check; only `--execute` plus reading the evidence catches it. A `.py` file
without `# %%` markers is one cell, so the scope check covers the whole file.
The metric regex is yours; one that matches unrelated lines gives a misleading
delta. The kernel runs with Waldean's Python, so the notebook's dependencies
must be installed there. Both runs share the repaired notebook's directory, so
files one run writes can affect the other.
