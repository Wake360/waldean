---
name: False positive
about: Waldean flagged legitimate code as a flaw
title: ""
labels: false-positive
---

**Flaw ID**

Which rule fired. Run `waldean rules` to list all flaw IDs (e.g. `leakage-fit-before-split`).
See `waldean/taxonomy/flaws.yaml` for flaw definitions.

**Waldean version and mode**

Output of `waldean --version` (or `pip show waldean`).

Which mode you ran: static-only or `--llm`. If `--llm`, which provider(s).

**Minimal code snippet**

A stripped-down notebook cell or script that still triggers the flag — remove unrelated cells,
large outputs, and imports to keep it minimal.

**Full flag output**

The complete waldean output for this cell, not a trimmed excerpt.
Use `--format json` if that's easier to paste in full.

**Why the code is legitimate**

What the code actually does that makes the flag incorrect. What invariant, pre-condition,
or post-processing step prevents the flagged pattern from being a real flaw.
