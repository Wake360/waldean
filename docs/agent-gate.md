# Waldean as a mechanical gate for agent-written notebooks

## Why

LLM agents write analysis notebooks now — Claude Code, Cursor, Copilot
Workspace, cron-scheduled data agents. They make the same finite set of
mistakes a human analyst makes under deadline pressure: fit the scaler
before the split, run twenty t-tests and report the two that cleared
p<0.05, quote accuracy on a 98/2 class split, filter to "active users" and
then talk about "all users." These are not creativity failures. They are
catalogued, mechanical errors — the kind a linter catches, not the kind
that needs a second opinion.

Waldean is built to sit in that loop as a hard gate rather than a suggestion.
It is deterministic (no LLM in the static layer, same input always
produces the same flags), key-free (`waldean check` calls no API unless you
pass `--llm`), and exit-code gated: `0` clean, `1` medium-severity findings,
`2` high-severity findings, `3` usage or input error (bad path, bad flag).
That last distinction matters for automation — `3` means "the gate itself
is misconfigured," not "the notebook has a flaw," so a CI script or hook
can tell "fix your invocation" apart from "fix your analysis." Three
recipes follow: a Claude Code hook that blocks a bad edit before it lands,
a pre-commit hook that blocks a bad commit, and a CI job that blocks a bad
merge.

## Recipe A: Claude Code PostToolUse hook

Blocks Claude Code itself from leaving a leaky notebook on disk. The hook
fires after every `Edit` or `Write`, runs `waldean check` on the touched file,
and — only on a HIGH finding (waldean exit code `2`) — exits `2` with the
report on stderr. Claude Code's hook contract treats exit `2` as
block-with-feedback: the tool call is blocked and stderr is fed back to the
model, so the agent sees the exact flaw and fixes it instead of moving on.
Exit `1` (medium) and `3` (usage error) pass through unchanged — Claude
Code treats any non-zero, non-`2` exit as non-blocking, so the run
continues and the message is just shown to the user.

`.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "examples/hooks/waldean-gate.sh"
          }
        ]
      }
    ]
  }
}
```

The hook script (`examples/hooks/waldean-gate.sh` in this repo, already
executable):

```bash
#!/usr/bin/env bash
input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')

case "$file" in
  *.ipynb) ;;
  *) exit 0 ;;
esac

report=$(waldean check "$file" 2>&1)
code=$?

if [ "$code" -eq 2 ]; then
  printf '%s\n' "$report" >&2
  exit 2
fi

exit "$code"
```

The `jq -r '.tool_input.file_path // empty'` line is the extraction: Claude
Code's `PostToolUse` payload puts the touched path at `.tool_input.file_path`
for both `Edit` and `Write`; `// empty` makes the case statement below skip
cleanly (exit `0`) on any tool call where that field is absent instead of
erroring on `null`.

## Recipe B: pre-commit

Blocks a commit that touches a notebook with an uncorrected HIGH or MEDIUM
finding. `waldean check` accepts multiple paths and returns the worst exit
code across all of them, so pre-commit can hand it every staged `.ipynb` in
one call.

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: waldean
        name: waldean (statistical-integrity gate)
        entry: waldean check
        language: system
        files: \.ipynb$
```

`pre-commit run waldean` (or a normal `git commit`) fails the hook whenever
`waldean check` exits non-zero — `1` for a medium finding, `2` for a high one,
`3` if a staged file isn't a valid notebook.

## Recipe C: GitHub Actions

`--format sarif` emits one SARIF 2.1.0 log for the whole invocation —
every taxonomy entry as a `rule`, every confident flag as a `result` with
severity, location, evidence and fix folded into the message. Upload it
with `github/codeql-action/upload-sarif` to get findings as inline PR
annotations in the Files Changed view, on top of the exit-code gate.

```yaml
name: waldean
on: [pull_request]

jobs:
  check-notebooks:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - run: pip install -e ".[corpus,dev]"

      - name: Find changed notebooks
        id: changed
        run: |
          files=$(git diff --name-only \
            origin/${{ github.base_ref }}...${{ github.sha }} -- '*.ipynb')
          echo "files=$files" >> "$GITHUB_OUTPUT"

      - name: waldean check
        id: waldean
        if: steps.changed.outputs.files != ''
        run: |
          set +e
          waldean check ${{ steps.changed.outputs.files }} --format sarif \
            > waldean-report.sarif
          echo "exit_code=$?" >> "$GITHUB_OUTPUT"

      - name: Upload SARIF
        if: always() && steps.changed.outputs.files != ''
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: waldean-report.sarif

      - name: Gate on waldean exit code
        if: steps.changed.outputs.files != ''
        run: exit ${{ steps.waldean.outputs.exit_code }}
```

The job fails (red X, blocks merge if the check is required) on exit `1`
or `2`; a `3` (bad notebook file, bad invocation) fails it too, which is
the right default for CI even though it's a different failure mode than a
real finding. The SARIF upload runs regardless (`if: always()`) so findings
show up as PR annotations even on a failing run — that's the point of
uploading before gating.

## Recipe D: repair loop

```bash
waldean propose forecast.ipynb
claude -p --model sonnet --permission-mode acceptEdits --allowedTools "Read,Edit,NotebookEdit,Bash(waldean verify:*)" < .waldean/repairs/forecast--leakage-temporal-shuffle/brief.md
waldean verify .waldean/repairs/forecast--leakage-temporal-shuffle
```

The gate recipes block a bad notebook, while this recipe turns the block into a scoped task for the agent and checks the agent's answer.

## What it will and will not catch

The static layer — the only layer active in any recipe above, since none
pass `--llm` — decides three flaw classes on its own, deterministically:
`leakage-fit-before-split`, `testing-multiple-uncorrected`, and
`baserate-accuracy-imbalanced`. It also emits a low-confidence *candidate*
for `selection-survivorship-cohort` that these recipes will not fail the
build on (candidates sit below the confidence floor by design). The
remaining four classes in the taxonomy — `leakage-future-feature`,
`selection-survivorship-cohort` (confident), `significance-meaningless`,
`regression-to-mean-claim`, `linearity-extrapolation` — need the narrative
layer (`--llm`, an API key, and per the README the G2/G3 quality gates
haven't run yet), so none of these recipes catch them. The full, versioned
list of what Waldean checks lives in `waldean/taxonomy/flaws.yaml`.

On measured quality: mutation testing gives precision 1.00 and recall 1.00
on `leakage-fit-before-split` (24 mutants), `leakage-temporal-shuffle`
(16 mutants), `testing-multiple-uncorrected` (96 mutants), and
`baserate-accuracy-imbalanced` (8 mutants), with a 0.0%
false-positive rate on the 83-notebook clean corpus. The 27 real notebooks
in that corpus also shaped the static layer during dogfood, so this is not
an out-of-sample test for them — the real-notebook share of the 0.0% leans
optimistic. Dogfooding on 34 real
notebooks went through one failed iteration — the first pass flagged 50%
of files, 119 of 124 flags false positives — before the detector was
rebuilt (flow-sensitive dataflow, transformer/estimator distinction,
CV-aware sinks); after the fix, 3 confident flags on the same 34
notebooks, all three confirmed real leaks, 0 known false positives. Real-
flaw recall is measured against only 7 confirmed instances so far — enough
to fix the detector, too few to report as a recall number.

What none of these recipes can catch, because no tool that reads notebooks
can: a flaw with no imprint in code, stored outputs, or prose. Survivorship
bias living in data that never entered the notebook is invisible by
construction. Waldean claims only the detectable classes.
