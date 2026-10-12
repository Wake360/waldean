import csv
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

FLAW = "leakage-fit-before-split"


def notebook_path(nb_label: str, notebooks_dir: Path) -> Path:
    _, _, day, name = nb_label.split("/")
    return notebooks_dir / f"{day}-{name.removesuffix('.py')}.ipynb"


def confusion(rows: list[dict], flagged: set[str]) -> dict[str, int]:
    c = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for r in rows:
        truth = r["pre"].strip().startswith("Y")
        pred = r["nb"] in flagged
        c[("t" if truth == pred else "f") + ("p" if pred else "n")] += 1
    return c


def score(rows: list[dict], outcomes: dict[str, str]) -> dict:
    flagged = {nb for nb, o in outcomes.items() if o == "flagged"}
    return {
        "confusion": confusion(rows, flagged),
        "errors": sorted(nb for nb, o in outcomes.items() if o == "error"),
        "flagged": sorted(flagged),
    }


def run_wald(path: Path) -> str:
    out = subprocess.run(["wald", "check", str(path), "--format", "json"],
                         capture_output=True, text=True)
    if out.returncode == 3 or not out.stdout.strip():
        return "error"
    report = json.loads(out.stdout)
    return "flagged" if any(f["flaw_id"] == FLAW for f in report["flags"]) else "clean"


def render(s: dict, rows: list[dict]) -> str:
    c = s["confusion"]
    precision = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else float("nan")
    recall = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else float("nan")
    truth = {r["nb"]: r["pre"] for r in rows}
    lines = [
        f"# Wald on Yang et al. ASE'22 (`pre` label) — {date.today().isoformat()}",
        "",
        f"{len(rows)} labeled notebooks; static layer, confident flags only (>= 0.8), class `{FLAW}`.",
        "",
        "| TP | FP | FN | TN | precision | recall |",
        "|---|---|---|---|---|---|",
        f"| {c['tp']} | {c['fp']} | {c['fn']} | {c['tn']} | {precision:.2f} | {recall:.2f} |",
        "",
        f"Errors (wald exit 3, counted as not flagged): {len(s['errors'])}",
        *[f"- {nb}" for nb in s["errors"]],
        "",
        "## Flagged",
        *[f"- {nb} — label `{truth[nb]}`" for nb in s["flagged"]],
        "",
        "## Missed (`pre` = Y, not flagged)",
        *[f"- {r['nb']} — label `{r['pre']}`" for r in rows
          if r["pre"].strip().startswith("Y") and r["nb"] not in s["flagged"]],
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> None:
    labels, notebooks_dir, out = argv
    rows = [r for r in csv.DictReader(open(labels)) if r["nb"]]
    outcomes = {r["nb"]: run_wald(notebook_path(r["nb"], Path(notebooks_dir))) for r in rows}
    Path(out).write_text(render(score(rows, outcomes), rows))
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
