# Agent skill for Waldean

Date: 2026-10-13. Status: design, approved in chat.

## Goal

Coding agents (Claude Code, Codex, Cursor and others that read `SKILL.md`)
should follow the methodology checklist when they write a notebook or script
that trains, evaluates or reports a model, and run `waldean check` before they
report a metric. The skill is the distribution channel: one install command,
no change to the human's workflow.

Not in scope: an MCP server, a separate skills repo, shipping the skill inside
the PyPI package, new CLI flags, new detectors.

## What exists

- `waldean check <file> --format json`, exit codes 0 / 1 / 2 / 3.
- `evals/agent-protocol/checklist.md`: seven methodology rules, pre-registered.
  Pilot: 18 of 20 agent runs valid with it in the prompt
  (`evals/2026-10-13-agent-protocol-pilot.md`, indicative).
- `docs/agent-gate.md` and `examples/hooks/waldean-gate.sh`: Claude Code hook
  that blocks an edit on a HIGH finding.
- `scripts/agent_baseline.py` with pre-registered arms in
  `evals/agent-protocol/MANIFEST.json` (A none, B checklist in prompt, C
  locked protocol).

## Layout

```
skills/
  waldean/
    SKILL.md
    checklist.md
```

`npx skills add Wake360/waldean` finds `skills/waldean/SKILL.md`. Claude Code
reads the same directory when copied to `.claude/skills/waldean/`.

## SKILL.md

Frontmatter:

```yaml
name: waldean
description: Use when writing or editing a notebook or .py script that trains or evaluates a model, splits data, runs statistical tests, or reports a metric. Methodology checklist plus `waldean check` before any reported number.
```

Body, in this order, plain sentences, no numbers that are not in a dated eval
file:

1. When this applies. One paragraph.
2. Checklist. The seven items, included by reference to `checklist.md` in the
   same directory and repeated inline so the agent does not need a second read.
3. Install. `pip install waldean`. If it is missing, say so to the user and
   continue with the checklist alone.
4. Run. `waldean check <file> --format json` after the split and preprocessing
   are in place, and again before reporting any metric. Exit code table.
5. Act on findings. HIGH: fix the cell the report names, re-run, do not report
   the metric until it is gone. MEDIUM: fix if the fix is local, otherwise
   report the finding next to the metric. Candidate (below the confidence
   floor): read it, mention it only if it holds. Never suppress a finding by
   rewriting the code so the detector no longer sees it; the report names the
   mechanism, fix the mechanism.
6. Limits. A clean report is not a clean notebook. List the known miss
   idioms from README (per-group imputation, `fillna(df[col].mean())` before
   the split, scaler fit on full data feeding `cross_val_score`, Python 2
   cells). The checklist covers these; the linter does not.
7. Repair loop. One sentence: for `leakage-temporal-shuffle`, `waldean propose`
   and `waldean verify` exist and are experimental.

## checklist.md

A byte-identical copy of `evals/agent-protocol/checklist.md`. A unit test
asserts the two files are equal so they cannot drift. The eval copy stays the
source because it is pre-registered.

## README

A section "For coding agents", under "Pre-commit", four lines: what the skill
does, the install command, a link to `skills/waldean/SKILL.md`, a link to
`docs/agent-gate.md` for the hook.

## Measurement

A new arm D in `evals/agent-protocol/MANIFEST.json`, added before any D run:

```json
"D": {"suffix": "", "files": [".claude/skills/waldean/SKILL.md", ".claude/skills/waldean/checklist.md"], "tools": ["Bash(waldean *)"]}
```

`run_one` already copies `arm.files` into the run directory, so the only
harness change is that `files` entries may contain a directory path. Arm D
asks the same question as B with no checklist in the prompt: does the agent
load the skill and act on it. Scored with the existing probes. Five runs per
dataset, Claude Code first; Codex when its skill discovery is confirmed.
Report in `evals/<date>-agent-skill.md`, indicative. No number from arm D
goes into `SKILL.md` or README before that file exists.

## Verification

1. `uv run pytest tests/test_skill.py -q`: checklist copy equals the eval copy;
   `SKILL.md` frontmatter parses and has `name` and `description`.
2. In an empty temp directory, `npx skills add Wake360/waldean -y` installs
   `skills/waldean` (run after the branch is on GitHub; before that, point the
   command at the local path if the CLI accepts one).
3. Arm D run as above, log shows `waldean check` invoked in at least one run
   without being named in the prompt.

## Files

- Create `skills/waldean/SKILL.md`, `skills/waldean/checklist.md`,
  `tests/test_skill.py`.
- Edit `README.md` (new section), `evals/agent-protocol/MANIFEST.json`
  (arm D), `scripts/agent_baseline.py` only if copying a nested path needs it.
