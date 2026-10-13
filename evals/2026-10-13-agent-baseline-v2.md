# Agent baseline v2, 2026-10-13

Indicative only. Pre-registered criteria and gate in `agent-baseline-v2/MANIFEST.json`.

| criterion | datasets | claude fail | codex fail | failure rate | gate |
|---|---|---|---|---|---|
| temporal | maintenance, subscriptions | 3/10 | 0/10 | 15% | solved by agents |
| group | clinic | 0/5 | 0/5 | 0% | solved by agents |
| leak | maintenance, subscriptions | 0/10 | 0/10 | 0% | solved by agents |
| selection | clinic, control, maintenance, subscriptions | 8/20 | 6/15 | 40% | builder rule |

## Per dataset

| dataset | criterion | claude pass | codex pass |
|---|---|---|---|
| maintenance | temporal | 4/5 | 5/5 |
| maintenance | leak | 5/5 | 5/5 |
| maintenance | selection | 1/5 | 2/5 |
| clinic | group | 5/5 | 5/5 |
| clinic | selection | 3/5 | 2/5 |
| subscriptions | temporal | 3/5 | 5/5 |
| subscriptions | leak | 5/5 | 5/5 |
| subscriptions | selection | 5/5 | 5/5 |
| control | selection | 3/5 | 0/0 |

## Runs

| run | cli | temporal | group | leak | selection | headline | waldean check (confident) |
|---|---|---|---|---|---|---|---|
| clinic-claude-default-0 | 2.1.296 (Claude Code) | n/a | pass | n/a | fail | ('roc_auc', 0.6211) | - |
| clinic-claude-default-1 | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.648) | - |
| clinic-claude-default-2 | 2.1.296 (Claude Code) | n/a | pass | n/a | fail | ('roc_auc', 0.648) | - |
| clinic-claude-default-3 | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.6484) | - |
| clinic-claude-default-4 | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 'text: 0.63-0.65 across models') | - |
| clinic-codex-default-0 | codex-cli 0.160.1 | n/a | pass | n/a | fail | ('roc_auc', 0.624) | - |
| clinic-codex-default-1 | codex-cli 0.160.1 | n/a | pass | n/a | fail | ('roc_auc', 0.624) | - |
| clinic-codex-default-2 | codex-cli 0.160.1 | n/a | pass | n/a | pass | ('roc_auc', 0.611) | - |
| clinic-codex-default-3 | codex-cli 0.160.1 | n/a | pass | n/a | fail | ('roc_auc', 0.63) | - |
| clinic-codex-default-4 | codex-cli 0.160.1 | n/a | pass | n/a | pass | ('average_precision', 0.291) | - |
| control-claude-default-0 | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.775) | - |
| control-claude-default-1 | 2.1.296 (Claude Code) | n/a | n/a | n/a | fail | ('roc_auc', 0.775) | - |
| control-claude-default-2 | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.782) | - |
| control-claude-default-3 | 2.1.296 (Claude Code) | n/a | n/a | n/a | fail | ('roc_auc', 0.782) | - |
| control-claude-default-4 | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.775) | - |
| maintenance-claude-default-0 | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.757) | - |
| maintenance-claude-default-1 | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 'core features, text: ~0.68') | - |
| maintenance-claude-default-2 | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.778) | - |
| maintenance-claude-default-3 | 2.1.296 (Claude Code) | fail | n/a | pass | fail | ('roc_auc', 0.757) | - |
| maintenance-claude-default-4 | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.795) | - |
| maintenance-codex-default-0 | codex-cli 0.160.1 | pass | n/a | pass | pass | ('average_precision', 0.08) | - |
| maintenance-codex-default-1 | codex-cli 0.160.1 | pass | n/a | pass | fail | ('roc_auc', 0.807) | - |
| maintenance-codex-default-2 | codex-cli 0.160.1 | pass | n/a | pass | fail | ('roc_auc', 0.768) | - |
| maintenance-codex-default-3 | codex-cli 0.160.1 | pass | n/a | pass | fail | ('roc_auc', 0.828) | - |
| maintenance-codex-default-4 | codex-cli 0.160.1 | pass | n/a | pass | pass | ('average_precision', 0.036) | - |
| subscriptions-claude-default-0 | 2.1.296 (Claude Code) | fail | n/a | pass | pass | ('roc_auc', 0.6773193246853989) | - |
| subscriptions-claude-default-1 | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 'text: about 0.68') | - |
| subscriptions-claude-default-2 | 2.1.296 (Claude Code) | fail | n/a | pass | pass | ('roc_auc', 'text: 0.66-0.69') | - |
| subscriptions-claude-default-3 | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 'text: 0.69-0.71') | - |
| subscriptions-claude-default-4 | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 'text: about 0.69') | - |
| subscriptions-codex-default-0 | codex-cli 0.160.1 | pass | n/a | pass | pass | ('average_precision', 0.3) | - |
| subscriptions-codex-default-1 | codex-cli 0.160.1 | pass | n/a | pass | pass | ('average_precision', 0.285) | - |
| subscriptions-codex-default-2 | codex-cli 0.160.1 | pass | n/a | pass | pass | ('roc_auc', 0.713) | - |
| subscriptions-codex-default-3 | codex-cli 0.160.1 | pass | n/a | pass | pass | ('average_precision', 0.206) | - |
| subscriptions-codex-default-4 | codex-cli 0.160.1 | pass | n/a | pass | pass | ('average_precision', 0.289) | - |

## Notes

- 35 of 40 planned runs. All 5 control-codex runs stopped on the Codex usage limit and were not rerun. They cannot change the gate: with 5 passes, selection would be 14/40 = 35%.
- Every notebook was read by hand before scoring. Bindings and rulings are in `agent-baseline-v2/scoring.tsv`.
- Selection rule, fixed before scoring: fail if the headline model, feature set or threshold was picked from two or more candidates by comparing scores on the headline rows, in code or in text. Reporting several models without picking one is not selection.
- Numbers the notebook itself labels invalid or optimistic are excluded from scoring.
- Borderline rulings: control-claude-1 and -3 fail (the choice cites test numbers); control-claude-0, -2, -4 pass (the choice cites CV); clinic-claude-1, -3, -4 pass (both models reported, none picked); subscriptions-claude-2 temporal fail (grouped CV reported as robustness); subscriptions-claude-3 group CV excluded (labelled optimistic); maintenance-claude-4 shuffled CV excluded (labelled a comparison).
- The selection criterion is strict. It measures evaluation hygiene, not the size of the bias; on these datasets the candidates differ by a few AUC points.
- Small sample, one prompt, the same two agents as v1. Indicative only.
- `waldean check` at the time of the runs flagged nothing. The `leakage-test-selection` detector (branch `test-selection`) flags 9 of these 35 notebooks with confidence 0.9; 8 are manual selection fails and one (control-claude-2) selects on test in code while its headline cites CV. Fails it misses pick the model in prose or hard-code the choice.
- Pre-registered decision applies: only selection is a builder rule, so a waldean detector for test-set selection is preferred over a Builder.

## Prompt

`Here is data.csv and its data dictionary columns.csv. I want to know whether we can predict {question}. Build a notebook and save it as experiment.ipynb.`
