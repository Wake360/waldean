# agent-protocol-pilot, 2026-10-13

Indicative only. Pre-registered arms, criteria and decision rule in `agent-protocol-pilot/MANIFEST.json`.

| arm | runs | notebook | valid (95% CI) | temporal fail | group fail | leak fail | selection fail | median abs gap (n) |
|---|---|---|---|---|---|---|---|---|
| B | 20 | 20 | 18/20 (70%-97%) | 2/10 | 0/5 | 0/10 | 0/20 | - (0) |

## Differences in failure rate

| comparison | difference | 95% CI (Newcombe) |
|---|---|---|

## Runs

| run | arm | cli | temporal | group | leak | selection | headline | future AUC | waldean check |
|---|---|---|---|---|---|---|---|---|---|
| clinic-claude-B-0 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.641) | None | - |
| clinic-claude-B-1 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.636) | None | - |
| clinic-claude-B-2 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.655) | None | - |
| clinic-claude-B-3 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.655) | None | leakage-test-selection |
| clinic-claude-B-4 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.655) | None | - |
| control-claude-B-0 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('test_roc_auc', 0.7662936513574387) | None | - |
| control-claude-B-1 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('test_roc_auc', 0.7703603076520296) | None | - |
| control-claude-B-2 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('test_roc_auc', 0.7662936513574387) | None | - |
| control-claude-B-3 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('test_roc_auc', 0.7806285544751391) | None | - |
| control-claude-B-4 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('test_roc_auc', 0.7645773887249924) | None | - |
| maintenance-claude-B-0 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('average_precision', 0.076) | None | - |
| maintenance-claude-B-1 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('average_precision', 0.085) | None | - |
| maintenance-claude-B-2 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('average_precision', 0.073) | None | - |
| maintenance-claude-B-3 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('average_precision', 0.087) | None | - |
| maintenance-claude-B-4 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('average_precision', 0.082) | None | - |
| subscriptions-claude-B-0 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.703) | None | - |
| subscriptions-claude-B-1 | B | 2.1.296 (Claude Code) | fail | n/a | pass | pass | ('roc_auc', 0.737) | None | - |
| subscriptions-claude-B-2 | B | 2.1.296 (Claude Code) | fail | n/a | pass | pass | ('roc_auc', 0.702) | None | - |
| subscriptions-claude-B-3 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('average_precision', 0.241) | None | - |
| subscriptions-claude-B-4 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('pr_auc', 0.217) | None | - |

## Prompt

`Here is data.csv and its data dictionary columns.csv. I want to know whether we can predict {question}. Build a notebook and save it as experiment.ipynb.`

Arm B appends ` Follow the methodology checklist in checklist.md. You can run `waldean check experiment.ipynb` to lint the notebook for statistical flaws.`.

## Notes

- Decision rule (MANIFEST `decision`): stop needs selection fails at most 1 of 20 and temporal fails 0 of 10. Observed selection 0/20, temporal 2/10. Result: continue to the held-out datasets and the protocol.
- The two temporal failures are subscriptions-claude-B-1 (test set is the latest-starting 20% of accounts with all their rows, so test rows overlap train rows in calendar time; CV folds are account cohorts that overlap in time) and subscriptions-claude-B-2 (test set is months 2025-09 onward, but CV is GroupKFold on accounts, so folds train on months later than their validation rows). Both follow checklist item 1 for entities and miss its time half, or the reverse in CV.
- Group 0/5, leak 0/10, selection 0/20. All 20 runs produced a notebook. `waldean check` reported a confident `leakage-test-selection` on clinic-claude-B-3; the probe rules selection pass there (threshold chosen on CV predictions, test scored once). The linter flag is a false positive on this notebook.
- Independence. Agent scratch files land in `/private/tmp/claude-501`, not only `/private/tmp/claude`. The harness sweeps `/private/tmp/claude` around each run and records, read only, the entries each run adds to `/private/tmp/claude-501` (`user_tmp_new` in meta.json). maintenance-claude-B-1 executed `/tmp/claude-501/mk.py` left by maintenance-claude-B-4 and produced a byte-identical notebook (similarity 1.00); its own log says so. It was moved to `runs-protocol-pilot-excluded/`, the entries listed in `user_tmp_new` were moved aside to `stale-scratch/claude-501-pilot/`, and the run was repeated. After the rerun the highest pair is 0.26. subscriptions-claude-B-1 left `build.py` in `/private/tmp/claude`, swept into its run dir.
- Several agents could not start a Jupyter kernel in the sandbox and ran the cells as a script, so some notebooks (for example clinic-claude-B-0 and -B-4) have no saved outputs. Scoring executes every notebook, so the reported numbers exist at scoring time; reviewers bound them from the code.
- `future AUC` is None for every run: the v3 datasets have no `future.csv`. Headlines mix metrics (roc_auc, average_precision, pr_auc); the gap column applies only to the main experiment.
- Five runs per dataset, one agent (Claude Code, model sonnet, CLI 2.1.296). Indicative only.
