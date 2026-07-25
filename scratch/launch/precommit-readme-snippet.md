## Pre-commit integration

Add wald to your pre-commit configuration:

```yaml
repos:
  - repo: https://github.com/Wake360/wald
    rev: v0.3.1
    hooks:
      - id: wald
```

Exit code 2 (high-severity finding) fails the hook and blocks the commit. Confident findings below the gate exit 1 and allow the commit. To fail on medium-severity findings too, add `args: [--severity-gate, medium]`.
