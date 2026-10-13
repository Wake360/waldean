import argparse
import json
import os
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path

import nbformat

from waldean.repair import propose, verify

CORPUS_METRIC = re.compile(r"(?:mae=|cv neg_mae: )(-?\d+\.\d+)")
CASES = ("clean-base", "unchanged", "out-of-scope", "eval-removed")
EXPECTED = {"clean-base": "static-pass", "unchanged": "rejected",
            "out-of-scope": "rejected", "eval-removed": "rejected"}


def variant(case: str, base: Path, mutant: Path, protocol: dict, dest: Path) -> Path:
    if case == "unchanged":
        shutil.copyfile(mutant, dest)
        return dest
    nb = nbformat.read(base, as_version=4)
    scope = set(protocol["edit_scope"])
    if case == "out-of-scope":
        cell = next(c for i, c in enumerate(nb.cells)
                    if c.cell_type == "code" and i not in scope and "dropna" in c.source)
        cell.source += "\ndf = df.iloc[: len(df) // 2]"
    if case == "eval-removed":
        for target in protocol["targets"]:
            cell = nb.cells[target["cell"]]
            cell.source = "\n".join(ln for ln in cell.source.splitlines() if target["sink"] not in ln)
    nbformat.write(nb, dest)
    return dest


def run(corpus: Path, execute: bool) -> list[dict]:
    manifest = json.loads((corpus / "MANIFEST.json").read_text(encoding="utf-8"))
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for entry in manifest["mutants"]:
            if entry["flaw_id"] != "leakage-temporal-shuffle":
                continue
            mutant, base = corpus / entry["file"], corpus / entry["base"]
            name = Path(entry["file"]).stem
            written, _ = propose(mutant, out_root=tmp_dir / name)
            row = {"mutant": entry["file"], "split": entry["split"], "contracts": len(written)}
            if len(written) == 1:
                protocol = json.loads((written[0] / "protocol.json").read_text(encoding="utf-8"))
                for case in CASES:
                    fixed = variant(case, base, mutant, protocol, tmp_dir / f"{name}--{case}.ipynb")
                    row[case] = verify(written[0], fixed)["status"]
                if execute:
                    evidence = verify(written[0], tmp_dir / f"{name}--clean-base.ipynb", CORPUS_METRIC, 300)
                    row["executed"] = evidence["status"]
                    row["before"] = evidence["execution"]["before"]
                    row["after"] = evidence["execution"]["after"]
            rows.append(row)
    return rows


def render(rows: list[dict], day: str, execute: bool) -> str:
    n = len(rows)
    lines = [
        f"# Repair loop on the mutation corpus — {day}",
        "",
        "Built by `scripts/repair_eval.py`. Each `leakage-temporal-shuffle` mutant gets a repair contract",
        "from `waldean propose`. `waldean verify` then judges four candidate repairs per contract: the",
        "clean base notebook (the true repair), the unchanged mutant, the clean base with an edit outside",
        "the edit scope, and the clean base with the evaluation call deleted.",
        "",
        "| measure | count |",
        "|---|---|",
        f"| temporal-shuffle mutants | {n} |",
        f"| exactly one contract written | {sum(r['contracts'] == 1 for r in rows)} |",
    ]
    for case in CASES:
        hits = sum(r.get(case) == EXPECTED[case] for r in rows)
        lines.append(f"| {case} judged {EXPECTED[case]} | {hits} |")
    if execute:
        lines.append(f"| clean base executed and verified | {sum(r.get('executed') == 'verified' for r in rows)} |")
    lines += ["", "| mutant | split | " + " | ".join(CASES) + (" | before | after |" if execute else " |"),
              "|---|---|" + "---|" * len(CASES) + ("---|---|" if execute else "")]
    for r in rows:
        cells = [Path(r["mutant"]).name, r["split"], *(r.get(c, "-") for c in CASES)]
        if execute:
            cells += [str(r.get("before", "-")), str(r.get("after", "-"))]
        lines.append("| " + " | ".join(cells) + " |")
    lines += [
        "",
        "The corpus is synthetic and self-authored. These counts show that the verifier tells a true",
        "repair from three known bad ones on notebooks of this shape. They do not measure how often an",
        "agent writes an acceptable repair on real notebooks.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", default="corpus")
    parser.add_argument("--out", default="evals")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    rows = run(Path(args.corpus), args.execute)
    day = os.environ.get("WALDEAN_BUILD_DATE", date.today().isoformat())
    path = Path(args.out) / f"{day}-repair-loop.md"
    path.write_text(render(rows, day, args.execute), encoding="utf-8")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
