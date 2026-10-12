#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
python3 - "$tmp/preds.json" <<'EOF'
import json, subprocess, sys
from pathlib import Path

manifest = json.loads(Path("corpus/MANIFEST.json").read_text())
files = [e["file"] for e in manifest["clean"]] + [e["file"] for e in manifest["mutants"]]
real = Path("corpus/real/MANIFEST.json")
if real.exists():
    files += [e["file"] for e in json.loads(real.read_text())["clean"]]

preds = {}
for f in files:
    out = subprocess.run(
        ["uv", "run", "wald", "check", str(Path("corpus") / f), "--format", "json"],
        capture_output=True, text=True,
    )
    report = json.loads(out.stdout)
    preds[f] = [
        {"flaw_id": fl["flaw_id"], "confidence": fl["confidence"]}
        for fl in report["flags"] + report["candidates"]
    ]
Path(sys.argv[1]).write_text(json.dumps(preds))
print(f"wrote predictions for {len(preds)} files")
EOF
uv run wald eval --corpus corpus --predictions "$tmp/preds.json"
