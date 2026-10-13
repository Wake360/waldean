import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path

import nbformat

from waldean.repair.loop import propose, verify

CLASSES = ("leakage-temporal-shuffle", "leakage-fit-before-split")
CORPUS_METRIC = {
    "leakage-temporal-shuffle": re.compile(r"(?:mae=|cv neg_mae: )(-?\d+\.\d+)"),
    "leakage-fit-before-split": re.compile(r"(?:roc_auc=|r2=)(-?\d+\.\d+)"),
}
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
        outside = [c for i, c in enumerate(nb.cells) if c.cell_type == "code" and i not in scope]
        cell = next((c for c in outside if "dropna" in c.source), None) or next(
            c for c in outside if "pd.DataFrame(" in c.source)
        cell.source += "\ndf = df.iloc[: len(df) // 2]"
    if case == "eval-removed":
        for target in protocol["targets"]:
            cell = nb.cells[target["cell"]]
            cell.source = "\n".join(ln for ln in cell.source.splitlines() if target["sink"] not in ln)
    nbformat.write(nb, dest)
    return dest


def apply_patch(mutant: Path, patch: str, work: Path, dest: Path) -> Path:
    nb = nbformat.read(mutant, as_version=4)
    for chunk in re.split(r"^(?=--- cell )", patch, flags=re.M)[1:]:
        idx = int(chunk.split()[2])
        cell_file = work / f"cell{idx}.py"
        cell_file.write_text(nb.cells[idx].source + "\n", encoding="utf-8")
        subprocess.run(["patch", "-s", str(cell_file)], input=chunk, text=True, check=True)
        nb.cells[idx].source = cell_file.read_text(encoding="utf-8").rstrip("\n")
    nbformat.write(nb, dest)
    return dest


def run(corpus: Path, execute: bool) -> list[dict]:
    manifest = json.loads((corpus / "MANIFEST.json").read_text(encoding="utf-8"))
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for entry in manifest["mutants"]:
            if entry["flaw_id"] not in CLASSES:
                continue
            mutant, base = corpus / entry["file"], corpus / entry["base"]
            name = Path(entry["file"]).stem
            written, _ = propose(mutant, out_root=tmp_dir / name, diff=True)
            row = {"mutant": entry["file"], "flaw_id": entry["flaw_id"], "split": entry["split"],
                   "contracts": len(written)}
            if len(written) == 1:
                protocol = json.loads((written[0] / "protocol.json").read_text(encoding="utf-8"))
                for case in CASES:
                    fixed = variant(case, base, mutant, protocol, tmp_dir / f"{name}--{case}.ipynb")
                    row[case] = verify(written[0], fixed)["status"]
                patch = written[0] / "patch.diff"
                if patch.exists():
                    fixed = apply_patch(mutant, patch.read_text(encoding="utf-8"), tmp_dir,
                                        tmp_dir / f"{name}--patched.ipynb")
                    row["patched"] = verify(written[0], fixed)["status"]
                if execute:
                    evidence = verify(written[0], tmp_dir / f"{name}--clean-base.ipynb",
                                      CORPUS_METRIC[entry["flaw_id"]], 300)
                    row["executed"] = evidence["status"]
                    row["before"] = evidence["execution"]["before"]
                    row["after"] = evidence["execution"]["after"]
            rows.append(row)
    return rows


def render(rows: list[dict], day: str, execute: bool) -> str:
    lines = [
        f"# Repair loop on the mutation corpus — {day}",
        "",
        "Built by `scripts/repair_eval.py`. Each `leakage-temporal-shuffle` and `leakage-fit-before-split`",
        "mutant gets a repair contract from `waldean propose --diff`. `waldean verify` then judges four",
        "candidate repairs per contract: the clean base notebook (the true repair), the unchanged mutant,",
        "the clean base with an edit outside the edit scope, and the clean base with the evaluation call",
        "deleted. When `propose --diff` wrote a mechanical `patch.diff`, the patch is applied to the",
        "mutant with `patch` and the result is judged as a fifth candidate.",
        "",
        "| measure | " + " | ".join(f"`{c}`" for c in CLASSES) + " |",
        "|---|" + "---|" * len(CLASSES),
    ]
    by_class = {c: [r for r in rows if r["flaw_id"] == c] for c in CLASSES}

    def row(label, count):
        return f"| {label} | " + " | ".join(str(count(by_class[c])) for c in CLASSES) + " |"

    lines.append(row("mutants", len))
    lines.append(row("exactly one contract written", lambda rs: sum(r["contracts"] == 1 for r in rs)))
    for case in CASES:
        lines.append(row(f"{case} judged {EXPECTED[case]}", lambda rs, case=case: sum(r.get(case) == EXPECTED[case] for r in rs)))
    lines.append(row("patch.diff written", lambda rs: sum("patched" in r for r in rs)))
    lines.append(row("patched mutant judged static-pass", lambda rs: sum(r.get("patched") == "static-pass" for r in rs)))
    if execute:
        lines.append(row("clean base executed and verified", lambda rs: sum(r.get("executed") == "verified" for r in rs)))
    cols = [*CASES, "patched"]
    lines += ["", "| mutant | split | " + " | ".join(cols) + (" | before | after |" if execute else " |"),
              "|---|---|" + "---|" * len(cols) + ("---|---|" if execute else "")]
    for r in rows:
        cells = [Path(r["mutant"]).name, r["split"], *(r.get(c, "-") for c in cols)]
        if execute:
            cells += [str(r.get("before", "-")), str(r.get("after", "-"))]
        lines.append("| " + " | ".join(cells) + " |")
    if execute:
        for c in CLASSES:
            executed = [r for r in by_class[c] if "before" in r]
            if executed and all(r["before"] == r["after"] for r in executed):
                lines += ["", f"On every `{c}` mutant the metric is identical before and after the repair. The leakage",
                          "does not move these synthetic metrics, so execution shows that both notebooks run, not",
                          "that the leakage was removed."]
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
