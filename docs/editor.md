# Editor use

Waldean has no editor extension. It writes SARIF, which SARIF viewers read.

## VS Code and Cursor

1. Install the "SARIF Viewer" extension (Microsoft).
2. Write the log. Directories collect only `.ipynb`, so pass `.py` files by name:

   ```bash
   waldean check analysis.py notebooks/ --format sarif > waldean.sarif
   ```

3. Open `waldean.sarif`. Findings should show in the Problems pane, and for `.py` files inline at the flagged line. `.py` lines are file-absolute (pinned by `tests/test_report.py::test_sarif_script_region_uses_file_lines`).

For `.ipynb`, the SARIF line is relative to the cell. The message ends with `cell N, line M`. There is no inline marker in the notebook yet.

## pre-commit

The repo ships `.pre-commit-hooks.yaml` with two hooks: `waldean` (notebooks) and `waldean-scripts` (`.py` files). See the README, Pre-commit section.

## Next

An inline notebook extension is planned once recall on real-world notebooks is above 0.75. Current recall is 0.63 ([evals/2026-10-13-yang-pre-rerun.md](../evals/2026-10-13-yang-pre-rerun.md)).
