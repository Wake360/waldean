---
name: Bug report
about: Waldean flagged wrong, missed a flaw, or crashed
title: ""
labels: bug
---

**Notebook**

Attach the notebook that reproduces the issue, or a minimal `.ipynb` that
still reproduces it (strip unrelated cells and large outputs).

**Waldean version**

Output of `waldean --version` (or `pip show waldean`).

**Static-only or `--llm`**

Which mode you ran. If `--llm`, include which provider(s).

**Full Waldean output**

The complete output of the `waldean check` invocation, not a trimmed excerpt.
Use `--format json` if that's easier to paste in full.
