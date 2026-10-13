# agent-baseline-v3, 2026-10-13

Indicative only. Pre-registered criteria and gate in `agent-baseline-v3/MANIFEST.json`.

| criterion | datasets | claude fail | codex fail | failure rate | 95% CI | gate |
|---|---|---|---|---|---|---|
| temporal | maintenance, subscriptions | 8/30 | 0/0 | 27% | 14%-44% | builder rule (interval includes 20%) |
| group | clinic | 0/15 | 0/0 | 0% | -0%-20% | solved by agents (interval includes 20%) |
| leak | maintenance, subscriptions | 0/30 | 0/0 | 0% | -0%-11% | solved by agents |
| selection | clinic, control, maintenance, subscriptions | 28/60 | 0/0 | 47% | 35%-59% | builder rule |

## Per dataset

| dataset | criterion | claude pass | codex pass |
|---|---|---|---|
| maintenance | temporal | 15/15 | 0/0 |
| maintenance | leak | 15/15 | 0/0 |
| maintenance | selection | 6/15 | 0/0 |
| clinic | group | 15/15 | 0/0 |
| clinic | selection | 8/15 | 0/0 |
| subscriptions | temporal | 7/15 | 0/0 |
| subscriptions | leak | 15/15 | 0/0 |
| subscriptions | selection | 11/15 | 0/0 |
| control | selection | 7/15 | 0/0 |

## leakage-test-selection vs manual selection ruling

| | ruling fail | ruling pass |
|---|---|---|
| flagged | 10 | 0 |
| not flagged | 18 | 32 |

Precision 10/10 (95% CI 72%-100%), recall 10/28 (95% CI 21%-54%).

## Runs

| run | cli | temporal | group | leak | selection | headline | waldean check (confident) |
|---|---|---|---|---|---|---|---|
| clinic-claude-default-0 | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.619) | - |
| clinic-claude-default-1 | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.646) | - |
| clinic-claude-default-10 | 2.1.296 (Claude Code) | n/a | pass | n/a | fail | ('roc_auc', 0.646) | - |
| clinic-claude-default-11 | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.633) | - |
| clinic-claude-default-12 | 2.1.296 (Claude Code) | n/a | pass | n/a | fail | ('roc_auc', 0.648) | - |
| clinic-claude-default-13 | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.648) | - |
| clinic-claude-default-14 | 2.1.296 (Claude Code) | n/a | pass | n/a | fail | ('roc_auc', 0.649) | - |
| clinic-claude-default-2 | 2.1.296 (Claude Code) | n/a | pass | n/a | fail | ('roc_auc', 0.636) | leakage-test-selection |
| clinic-claude-default-3 | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.63) | - |
| clinic-claude-default-4 | 2.1.296 (Claude Code) | n/a | pass | n/a | fail | ('roc_auc', 0.636) | leakage-test-selection |
| clinic-claude-default-5 | 2.1.296 (Claude Code) | n/a | pass | n/a | fail | ('roc_auc', 0.647) | - |
| clinic-claude-default-6 | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.648) | - |
| clinic-claude-default-7 | 2.1.296 (Claude Code) | n/a | pass | n/a | fail | ('roc_auc', 0.646) | leakage-test-selection |
| clinic-claude-default-8 | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.648) | - |
| clinic-claude-default-9 | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.648) | - |
| control-claude-default-0 | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.775) | - |
| control-claude-default-1 | 2.1.296 (Claude Code) | n/a | n/a | n/a | fail | ('roc_auc', 0.775) | leakage-test-selection |
| control-claude-default-10 | 2.1.296 (Claude Code) | n/a | n/a | n/a | fail | ('roc_auc', 0.781) | - |
| control-claude-default-11 | 2.1.296 (Claude Code) | n/a | n/a | n/a | fail | ('roc_auc', 0.775) | - |
| control-claude-default-12 | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.775) | - |
| control-claude-default-13 | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.775) | - |
| control-claude-default-14 | 2.1.296 (Claude Code) | n/a | n/a | n/a | fail | ('roc_auc', 0.781) | - |
| control-claude-default-2 | 2.1.296 (Claude Code) | n/a | n/a | n/a | fail | ('roc_auc', 0.775) | leakage-test-selection |
| control-claude-default-3 | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.775) | - |
| control-claude-default-4 | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.775) | - |
| control-claude-default-5 | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.775) | - |
| control-claude-default-6 | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.775) | - |
| control-claude-default-7 | 2.1.296 (Claude Code) | n/a | n/a | n/a | fail | ('roc_auc', 0.781) | - |
| control-claude-default-8 | 2.1.296 (Claude Code) | n/a | n/a | n/a | fail | ('roc_auc', 0.781) | - |
| control-claude-default-9 | 2.1.296 (Claude Code) | n/a | n/a | n/a | fail | ('roc_auc', 0.775) | - |
| maintenance-claude-default-0 | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.756) | - |
| maintenance-claude-default-1 | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.7566448522427287) | - |
| maintenance-claude-default-10 | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7548579042353314) | - |
| maintenance-claude-default-11 | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.7834940169848404) | - |
| maintenance-claude-default-12 | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.7513709287350159) | - |
| maintenance-claude-default-13 | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.7564525434297402) | - |
| maintenance-claude-default-14 | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.7566448522427287) | leakage-test-selection |
| maintenance-claude-default-2 | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7443854456824512) | - |
| maintenance-claude-default-3 | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7550918128893525) | - |
| maintenance-claude-default-4 | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.7582749390668522) | - |
| maintenance-claude-default-5 | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7481121605153203) | - |
| maintenance-claude-default-6 | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7513709287350159) | - |
| maintenance-claude-default-7 | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.7513709287350159) | - |
| maintenance-claude-default-8 | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.746888057103064) | leakage-test-selection |
| maintenance-claude-default-9 | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 'time-CV 0.70-0.74 (logreg 0.706, hist-GB 0.736)') | - |
| subscriptions-claude-default-0 | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.6730618674069337) | leakage-test-selection |
| subscriptions-claude-default-1 | 2.1.296 (Claude Code) | fail | n/a | pass | pass | ('roc_auc', 'text: about 0.69') | - |
| subscriptions-claude-default-10 | 2.1.296 (Claude Code) | fail | n/a | pass | pass | ('roc_auc', 'text: 0.66-0.68') | - |
| subscriptions-claude-default-11 | 2.1.296 (Claude Code) | fail | n/a | pass | pass | ('roc_auc', 0.696) | - |
| subscriptions-claude-default-12 | 2.1.296 (Claude Code) | fail | n/a | pass | pass | ('roc_auc', 'text: about 0.67-0.68') | - |
| subscriptions-claude-default-13 | 2.1.296 (Claude Code) | fail | n/a | pass | pass | ('roc_auc', 'text: about 0.66-0.68') | - |
| subscriptions-claude-default-14 | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 'text: about 0.67-0.68') | - |
| subscriptions-claude-default-2 | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 'text: 0.68-0.72') | - |
| subscriptions-claude-default-3 | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.6730094517958412) | - |
| subscriptions-claude-default-4 | 2.1.296 (Claude Code) | fail | n/a | pass | pass | ('roc_auc', 0.6882454386430238) | - |
| subscriptions-claude-default-5 | 2.1.296 (Claude Code) | fail | n/a | pass | pass | ('roc_auc', 'text: about 0.67') | - |
| subscriptions-claude-default-6 | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.6880634246338512) | leakage-test-selection |
| subscriptions-claude-default-7 | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 'text: 0.71-0.72') | - |
| subscriptions-claude-default-8 | 2.1.296 (Claude Code) | fail | n/a | pass | fail | ('roc_auc', 'text: about 0.67-0.68') | - |
| subscriptions-claude-default-9 | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.6985587604577519) | leakage-test-selection |

## Notes

- Deviation from the pre-registration: after 24 runs, with no codex run scored, the codex arm was dropped on the user's instruction. Codex had hit its provider usage limit on every attempt. v3 is 60 claude (sonnet) runs, 15 per dataset, not 120. The registered manifest is unchanged. The codex columns above read 0/0 for that reason. Applicable runs are temporal 30, group 15, leak 30, selection 60.
- 60 runs planned after the deviation and 60 scored. Every run produced a notebook. No `error:*`, `unbound` or `unreviewed` rows. The 30 codex attempts all stopped on the usage limit, wrote no notebook, and were moved aside unscored. Two claude runs were excluded and rerun, see below. No usage-limited claude run occurred.
- Independence. The claude sandbox shares the temp dirs `/private/tmp/claude` and `/private/tmp/claude-501` across runs, and agents leave their notebook builder scripts there. clinic-claude-12 was a verbatim copy of clinic-claude-8, because two concurrent runs used the same `/tmp/claude/nb/build.py`. control-claude-2 was a verbatim copy of control-claude-1 even with one job at a time, because run 2 executed run 1's leftover builder. Both were excluded and rerun after a sweep of builder files from those dirs. From clinic on, runs went one at a time, with the shared dirs moved aside before each batch. Several agents ran or copied a stale script and then replaced the result with their own notebook: maintenance-claude-3, -5, -8 and -13, clinic-claude-4, subscriptions-claude-2 and -3, and control-claude-10 and -11. A line-level similarity scan over all 60 notebook sources found no other copies. The highest remaining pair is control-claude-7/-8 at 0.42, sharing generic idioms; they were judged independent. No notebook or log names another run's directory. The plan's `grep runs-v3/` check alone would not have caught either copy.
- Notebooks were read in full by a session agent before scoring, one reviewer per dataset. No notebook uses the network, subprocesses or the shell. A few set `MPLCONFIGDIR` to a temp dir. Bindings are in `agent-baseline-v3/scoring.tsv`.
- Borderline selection rulings (first rater):
  - maintenance: 0, 1, 4, 7 and 13 fail, and 2, 3, 5, 6 and 10 pass. The common pattern is gradient boosting headlined over logistic on the same rows with no explicit pick. Runs fail when all downstream analysis uses the headlined model and the plan did not name it in advance.
  - clinic: 0, 1, 6, 8, 9 and 13 pass (both models reported, none picked), and 10 fails (hard-coded `best` after the table shows it ahead). The rerun of 12 fails, with logistic called "best" on the same out-of-fold rows.
  - subscriptions: 8 fails (feature set chosen on a table that mixes CV and test), 2 passes (the pick sits on a score the notebook labels optimistic), and 14 passes (grouped CV labelled optimistic).
  - control: 7 and 10 fail (the choice cites CV and test), 9 fails (code picks on test and that pick drives the headline), and 6 and 12 pass. The rerun of control-2 fails, picking `best` on test in code while the text cites CV.
- Second rater: a fresh agent saw only the rule and 24 notebooks, drawn with `random.Random(20261014).sample(sorted(runs_with_notebook), 24)`. The registered count of 24 was kept, which is 40% of 60. Agreement was 19/24, Cohen's kappa 0.57. All five disagreements are first-rater fail and second-rater pass: maintenance-claude-0, -11 and -12, and control-claude-7 and -10. They are the borderline patterns above (gradient boosting headlined with no stated pick; a choice citing both CV and test). The first rater's ruling is primary. With all five flipped, selection would be 23/60 = 38% (95% CI 27%-51%), still a builder rule.
- Comparison with v2 (claude arm only; two separate measurements, same datasets and prompt):
  - selection: v2 8/20 = 40% (22%-61%), v3 28/60 = 47% (35%-59%).
  - temporal: v2 3/10 = 30% (11%-60%), v3 8/30 = 27% (14%-44%). All 8 v3 temporal failures are subscriptions runs that report a GroupKFold-by-account CV next to a temporal holdout. maintenance had 15/15 temporal passes.
  - leak: v2 0/10, v3 0/30.
  - group: v2 0/5, v3 0/15.
- Detector: `leakage-test-selection` was built after reading the v2 notebooks, so v3 is its first held-out agent test. On the 60 v3 notebooks it flagged 10, all manual selection fails: precision 10/10 (95% CI 72%-100%), recall 10/28 (21%-54%).
- Limits: four synthetic datasets, one prompt, one agent (claude sonnet), a single first rater whose rulings agreed with a second rater at kappa 0.57. The group upper bound of 20% sits exactly on the gate threshold. The "-0%" lower bounds come from float rounding in the interval code. Indicative only. No claim about agents in general.
- Pre-registered decision: selection is a builder rule. Temporal is a builder rule at 27%, but its interval (14%-44%) includes 20%. Under the v2 decision rule ("a data trap is a rule"), Builder plan 09 Phase 2-3 applies to the temporal trap. That rests on claude sonnet alone; the manifest's out-of-scope rule requires a recheck on the then-default Claude model before any public claim. Leak is solved by agents. Group is solved by agents, interval includes 20%.

## Prompt

`Here is data.csv and its data dictionary columns.csv. I want to know whether we can predict {question}. Build a notebook and save it as experiment.ipynb.`
