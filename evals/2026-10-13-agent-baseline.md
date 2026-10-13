# Agent baseline, 2026-10-13

Indicative only: 4 default runs per trap. Pre-registered criteria in `agent-baseline/MANIFEST.json`.

| trap | criterion | default pass (claude) | default pass (codex) | gate | hinted pass |
|---|---|---|---|---|---|
| temporal | every training row is earlier than every test row | 2/2 | 2/2 | solved by agents | 2/2 |
| group | no patient_nbr appears in both train and test | 2/2 | 2/2 | solved by agents | 2/2 |
| imbalance | a test metric other than accuracy is computed | 2/2 | 2/2 | solved by agents | 2/2 |
| leak | duration is not among the fitted features | 2/2 | 1/2 | solved by agents | 2/2 |

## Runs

| run | agent | cli | probe | waldean check (confident) |
|---|---|---|---|---|
| control-claude-default-0 | claude | 2.1.296 (Claude Code) | n/a | - |
| control-claude-default-1 | claude | 2.1.296 (Claude Code) | n/a | - |
| control-codex-default-0 | codex | codex-cli 0.160.1 | n/a | - |
| control-codex-default-1 | codex | codex-cli 0.160.1 | n/a | - |
| group-claude-default-0 | claude | 2.1.296 (Claude Code) | pass | - |
| group-claude-default-1 | claude | 2.1.296 (Claude Code) | pass | - |
| group-claude-hinted-0 | claude | 2.1.296 (Claude Code) | pass | - |
| group-codex-default-0 | codex | codex-cli 0.160.1 | pass | - |
| group-codex-default-1 | codex | codex-cli 0.160.1 | pass | - |
| group-codex-hinted-0 | codex | codex-cli 0.160.1 | pass | - |
| imbalance-claude-default-0 | claude | 2.1.296 (Claude Code) | pass | - |
| imbalance-claude-default-1 | claude | 2.1.296 (Claude Code) | pass | - |
| imbalance-claude-hinted-0 | claude | 2.1.296 (Claude Code) | pass | - |
| imbalance-codex-default-0 | codex | codex-cli 0.160.1 | pass | - |
| imbalance-codex-default-1 | codex | codex-cli 0.160.1 | pass | - |
| imbalance-codex-hinted-0 | codex | codex-cli 0.160.1 | pass | - |
| leak-claude-default-0 | claude | 2.1.296 (Claude Code) | pass | - |
| leak-claude-default-1 | claude | 2.1.296 (Claude Code) | pass | - |
| leak-claude-hinted-0 | claude | 2.1.296 (Claude Code) | pass | - |
| leak-codex-default-0 | codex | codex-cli 0.160.1 | fail | - |
| leak-codex-default-1 | codex | codex-cli 0.160.1 | pass | - |
| leak-codex-hinted-0 | codex | codex-cli 0.160.1 | pass | - |
| temporal-claude-default-0 | claude | 2.1.296 (Claude Code) | pass | - |
| temporal-claude-default-1 | claude | 2.1.296 (Claude Code) | pass | - |
| temporal-claude-hinted-0 | claude | 2.1.296 (Claude Code) | pass | - |
| temporal-codex-default-0 | codex | codex-cli 0.160.1 | pass | - |
| temporal-codex-default-1 | codex | codex-cli 0.160.1 | pass | - |
| temporal-codex-hinted-0 | codex | codex-cli 0.160.1 | pass | - |

## Prompt

`Here is data.csv. I want to know whether we can predict {question}. Build a notebook and save it as experiment.ipynb.`

Hinted runs append ` Note: {hint}`.
## Notes

- All 28 notebooks were read by hand before scoring. They only read `data.csv` and use pandas, scikit-learn, matplotlib and seaborn. The bindings in `scoring.tsv` are tied to each notebook's sha256.
- Bindings use the split behind the headline test metric. Two temporal runs also report a secondary cross-validation that is not time-ordered: day-grouped leave-one-out in `temporal-claude-default-0`, day-grouped 6-fold over all days in `temporal-claude-default-1`. Their holdout passes; the secondary numbers would not.
- The one failure, `leak-codex-default-0`, restricts its candidate models to the feature set with `duration` and reports that model without a caveat.
- `waldean check` raised no confident flag on any notebook, including the leak failure. Waldean has no detector for a post-outcome feature such as `duration`.
- Notebooks were executed in the agents' venv (kernel `waldean-agent-baseline`), not in Waldean's own environment.
- Four macOS crash reports (10:54, 10:54, 11:04, 11:05) came from codex subprocesses opening the matplotlib GUI backend before the agent venv defaulted to `Agg` at 11:05. No agent log mentions the crash. Runs that finished before 11:05 may have been affected; the effect on their notebooks is unknown.
- Sample size is 2 default runs per agent per trap. A different seed or model version can change any cell.
