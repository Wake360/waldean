# GitHub Action

`Wake360/waldean@v0.6.0` is a composite action. It installs `waldean`, runs
`waldean check` on the paths you pass, writes a SARIF 2.1.0 log, and sets a
`gate-exit-code` output mapped through `fail-on` (`high`, `medium` or
`never`).

The action does not fail the job itself. It exposes the code so your
workflow can upload SARIF first, and findings show up as PR annotations even
on a failing run.

Requirements: `security-events: write` for the SARIF upload, Python 3.10 or
later on `PATH` (via `actions/setup-python`), and a Linux or macOS runner (the
steps are bash).

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

      - name: Find changed notebooks
        id: changed
        run: |
          files=$(git diff --name-only \
            origin/${{ github.base_ref }}...${{ github.sha }} -- '*.ipynb')
          echo "files=$files" >> "$GITHUB_OUTPUT"

      - name: waldean
        id: waldean
        if: steps.changed.outputs.files != ''
        uses: Wake360/waldean@v0.6.0
        with:
          paths: ${{ steps.changed.outputs.files }}
          fail-on: high

      - name: Upload SARIF
        if: always() && steps.changed.outputs.files != ''
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: ${{ steps.waldean.outputs.sarif-file }}

      - name: Gate on waldean
        if: steps.changed.outputs.files != ''
        run: exit ${{ steps.waldean.outputs.gate-exit-code }}
```

## Pre-commit

pre-commit fails a hook on any nonzero exit, so exit 1 (medium) and exit 2
(high) both block the commit. Raise `--floor` through `args` if you want fewer
low-confidence findings to count. `waldean-scripts` runs on every changed `.py`
file; scope it with `files:` or `exclude:` if your repo has many scripts that
are not analysis.
