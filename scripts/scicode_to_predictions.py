import json
import sys
from pathlib import Path

ID_MAP = {
    "ml-001": "leakage-fit-before-split",
    "ml-007": "leakage-fit-before-split",
    "ml-005": "leakage-temporal-shuffle",
    "ml-004": "baserate-accuracy-imbalanced",
}


def _corpus_files(root: Path) -> set[str]:
    files = set()
    for manifest in (root / "MANIFEST.json", root / "real" / "MANIFEST.json"):
        if manifest.exists():
            m = json.loads(manifest.read_text())
            files |= {e["file"] for e in m.get("clean", []) + m.get("mutants", [])}
    return files


def convert(results: list[dict], corpus_root: Path) -> dict[str, list[dict]]:
    root = corpus_root.resolve()
    preds, errored = {}, []
    for r in results:
        rel = Path(r["file"]).resolve().relative_to(root).as_posix()
        if r.get("error"):
            errored.append(rel)
            continue
        preds[rel] = [
            {"flaw_id": ID_MAP[short], "confidence": 1.0}
            for f in r["findings"]
            if (short := "-".join(f["id"].split("-")[:2])) in ID_MAP
        ]
    missing = sorted(_corpus_files(root) - set(preds) - set(errored))
    if errored or missing:
        raise ValueError(f"scicode-lint errored on {sorted(errored)}; no result for {missing}")
    return preds


def main(argv: list[str]) -> None:
    results_path, corpus_root, out = argv
    preds = convert(json.loads(Path(results_path).read_text()), Path(corpus_root))
    Path(out).write_text(json.dumps(preds, indent=1, sort_keys=True))
    print(f"wrote predictions for {len(preds)} files")


if __name__ == "__main__":
    main(sys.argv[1:])
