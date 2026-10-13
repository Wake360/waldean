import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import nbformat
import pandas as pd

from waldean.execute import execute, stdout_lines, with_appended_code_cell
from waldean.repair import KERNEL_NAME, scrubbed_env

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "evals" / "agent-baseline"
MANIFEST = BENCH / "MANIFEST.json"
SCORING = BENCH / "scoring.tsv"
VARIANTS = (("default", 0), ("default", 1), ("hinted", 0))
AGENT_ROOT = Path("/private/tmp/waldean-agent-baseline")
CLAUDE_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "NotebookEdit",
                "Bash(python *)", "Bash(python3 *)", "Bash(jupyter *)", "Bash(ls *)", "Bash(head *)"]
HOME = str(Path.home())
CLAUDE_SETTINGS = json.dumps({
    "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True, "allowUnsandboxedCommands": False,
                "filesystem": {"denyRead": [HOME]}},
    "permissions": {"deny": [f"{tool}(~/**)" for tool in ("Read", "Edit", "Write", "Glob", "Grep", "NotebookEdit")]},
})


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepared(name: str, raw: bytes) -> pd.DataFrame:
    if name == "temporal":
        lines = [ln for ln in raw.decode().splitlines() if ln[:1].isdigit()]
        df = pd.read_csv(io.StringIO("\n".join(lines)), header=None,
                         names=["id", "date", "Temperature", "Humidity", "Light", "CO2", "HumidityRatio", "Occupancy"])
        return df.drop(columns="id").sort_values("date", kind="stable").reset_index(drop=True)
    if name == "imbalance":
        text = raw.decode()
        rows = text[text.lower().index("@data") + 5:].strip()
        df = pd.read_csv(io.StringIO(rows), header=None, quotechar="'",
                         names=[f"attr{i}" for i in range(1, 7)] + ["class"])
        df["class"] = (df["class"].astype(int) == 1).astype(int)
        return df
    return pd.read_csv(io.BytesIO(raw), low_memory=False)


def cmd_prep(args) -> int:
    m = manifest()
    args.data.mkdir(parents=True, exist_ok=True)
    changed = False
    for d in m["datasets"]:
        out = args.data / f"{d['name']}.csv"
        if not out.exists():
            with urllib.request.urlopen(d["url"]) as r:
                prepared(d["name"], r.read()).to_csv(out, index=False)
        digest = sha256(out)
        if d.get("csv_sha256") not in (None, digest):
            print(f"{d['name']}: sha256 {digest} != manifest {d['csv_sha256']}", file=sys.stderr)
            return 3
        if "csv_sha256" not in d:
            d["csv_sha256"] = digest
            changed = True
        print(d["name"], digest, len(pd.read_csv(out, low_memory=False)))
    if changed:
        MANIFEST.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
    return 0


def prompt(m: dict, d: dict, variant: str) -> str:
    text = m["prompt"].format(question=d["question"])
    return text + m["hinted_suffix"].format(hint=d["hint"]) if variant == "hinted" else text


def agent_env(python_bin: Path, cli: str) -> dict:
    keep = {k: os.environ[k] for k in ("HOME", "USER", "LOGNAME", "LANG", "TERM") if k in os.environ}
    cli_dir = str(Path(shutil.which(cli) or cli).parent)
    return {**keep, "TMPDIR": "/private/tmp", "PATH": os.pathsep.join([str(python_bin), cli_dir, "/usr/bin", "/bin"])}


def agent_command(agent: str, m: dict, text: str, codex_home: Path, python_bin: Path) -> tuple[list[str], dict]:
    cfg = m["agents"][agent]
    env = agent_env(python_bin, cfg["cli"])
    if agent == "claude":
        return (["claude", "-p", text, "--model", cfg["model"], "--setting-sources", "project",
                 "--strict-mcp-config", "--settings", CLAUDE_SETTINGS, "--permission-mode", "acceptEdits",
                 "--allowedTools", *CLAUDE_TOOLS], env)
    env["CODEX_HOME"] = str(codex_home)
    return (["codex", "exec", "--skip-git-repo-check", "-m", cfg["model"],
             "-c", f"model_reasoning_effort={cfg['reasoning_effort']}",
             "-c", 'shell_environment_policy.inherit="core"', "-s", "workspace-write", text], env)


def version(cli: str) -> str:
    return subprocess.run([cli, "--version"], capture_output=True, text=True).stdout.strip()


def cmd_run(args) -> int:
    m = manifest()
    if Path.home() in args.runs.resolve().parents or Path.home() in args.python.resolve().parents:
        print("--runs and --python must be outside the home directory, which the agent sandbox cannot read",
              file=sys.stderr)
        return 3
    jobs = [(d, agent, variant, n) for d in m["datasets"] if not args.only or d["name"] in args.only
            for agent in m["agents"] for variant, n in VARIANTS if variant == "default" or d["hint"]]
    codex_home = Path(tempfile.mkdtemp(prefix="waldean-codex-home-"))
    (codex_home / "auth.json").symlink_to(Path.home() / ".codex" / "auth.json")
    try:
        with ThreadPoolExecutor(args.jobs) as pool:
            list(pool.map(lambda job: run_one(args, m, codex_home, *job), jobs))
    finally:
        shutil.rmtree(codex_home)
    return 0


def run_one(args, m: dict, codex_home: Path, d: dict, agent: str, variant: str, n: int) -> None:
    run_dir = args.runs / f"{d['name']}-{agent}-{variant}-{n}"
    if (run_dir / "meta.json").exists():
        return
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.data / f"{d['name']}.csv", run_dir / "data.csv")
    text = prompt(m, d, variant)
    cmd, env = agent_command(agent, m, text, codex_home, args.python)
    start = time.time()
    with (run_dir / "agent.log").open("w") as log:
        try:
            code = subprocess.run(cmd, cwd=run_dir, env=env, stdout=log, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL, timeout=args.timeout).returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
    meta = {"dataset": d["name"], "agent": agent, "variant": variant, "n": n,
            "prompt": text, "cli_version": version(m["agents"][agent]["cli"]),
            "model": m["agents"][agent]["model"], "exit": code,
            "seconds": round(time.time() - start),
            "notebook": (run_dir / "experiment.ipynb").exists()}
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(run_dir.name, "exit", code, "notebook", meta["notebook"], flush=True)


def bindings() -> dict[str, str]:
    if not SCORING.exists():
        return {}
    with SCORING.open(encoding="utf-8") as f:
        return {r["run"]: r["binding"].replace("\\n", "\n") for r in csv.DictReader(f, delimiter="\t")}


def waldean_check(path: Path) -> list[str]:
    proc = subprocess.run([sys.executable, "-m", "waldean.cli", "check", str(path), "--format", "json"],
                          capture_output=True, text=True)
    try:
        flags = json.loads(proc.stdout).get("flags", [])
    except json.JSONDecodeError:
        return [f"error:{proc.returncode}"]
    return sorted({f["flaw_id"] for f in flags if f.get("confidence", 0) >= 0.8})


def probe(d: dict, nb_path: Path, binding: str | None, timeout: int) -> str:
    if "probe_source_regex" in d:
        nb = nbformat.read(nb_path, as_version=4)
        source = "\n".join(c.source for c in nb.cells if c.cell_type == "code")
        return "pass" if re.search(d["probe_source_regex"], source) else "fail"
    if binding is None:
        return "unbound"
    nb = with_appended_code_cell(nbformat.read(nb_path, as_version=4), binding + "\n" + d["probe"])
    try:
        with scrubbed_env():
            done = execute(nb, timeout=timeout, cwd=str(nb_path.parent), kernel_name=KERNEL_NAME)
    except Exception as exc:
        return f"error:{type(exc).__name__}"
    lines = stdout_lines(done, "PROBE")
    return "pass" if lines and lines[-1].split()[-1] == "True" else "fail"


def cmd_score(args) -> int:
    m = manifest()
    by_name = {d["name"]: d for d in m["datasets"]}
    bound = bindings()
    stripped = BENCH / "runs"
    stripped.mkdir(exist_ok=True)
    rows = []
    for meta_path in sorted(args.runs.glob("*/meta.json")):
        meta = json.loads(meta_path.read_text())
        run = meta_path.parent.name
        nb_path = meta_path.parent / "experiment.ipynb"
        d = by_name[meta["dataset"]]
        row = {"run": run, **{k: meta[k] for k in ("dataset", "agent", "variant", "cli_version", "model")}}
        if not nb_path.exists():
            row.update(probe="fail:no-notebook", check="")
        else:
            nb = nbformat.read(nb_path, as_version=4)
            for c in nb.cells:
                if c.cell_type == "code":
                    c.outputs, c.execution_count = [], None
            nbformat.write(nb, stripped / f"{run}.ipynb")
            row["check"] = ",".join(waldean_check(nb_path))
            row["probe"] = "n/a" if not d["criterion"] else probe(d, nb_path, bound.get(run), args.timeout)
        rows.append(row)
        print(run, row["probe"], row["check"], flush=True)
    with (BENCH / "results.tsv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    report = ROOT / "evals" / f"{date.today().isoformat()}-agent-baseline.md"
    report.write_text(render(m, rows), encoding="utf-8")
    print("wrote", report)
    return 0


def verdict(passes: int, total: int) -> str:
    if total < 4:
        return "incomplete"
    if passes >= 3:
        return "solved by agents"
    return "builder rule" if total - passes >= 2 else "neither"


def render(m: dict, rows: list[dict]) -> str:
    out = [f"# Agent baseline, {date.today().isoformat()}", "",
           "Indicative only: 4 default runs per trap. Pre-registered criteria in `agent-baseline/MANIFEST.json`.", "",
           "| trap | criterion | default pass (claude) | default pass (codex) | gate | hinted pass |",
           "|---|---|---|---|---|---|"]
    for d in m["datasets"]:
        if not d["criterion"]:
            continue
        mine = [r for r in rows if r["dataset"] == d["name"]]
        default = [r for r in mine if r["variant"] == "default"]
        hinted = [r for r in mine if r["variant"] == "hinted"]
        per_agent = [f"{sum(r['probe'] == 'pass' for r in default if r['agent'] == a)}/"
                     f"{sum(r['agent'] == a for r in default)}" for a in m["agents"]]
        passes = sum(r["probe"] == "pass" for r in default)
        out.append(f"| {d['name']} | {d['criterion']} | {per_agent[0]} | {per_agent[1]} | "
                   f"{verdict(passes, len(default))} | {sum(r['probe'] == 'pass' for r in hinted)}/{len(hinted)} |")
    out += ["", "## Runs", "", "| run | agent | cli | probe | waldean check (confident) |", "|---|---|---|---|---|"]
    out += [f"| {r['run']} | {r['agent']} | {r['cli_version']} | {r['probe']} | {r['check'] or '-'} |" for r in rows]
    out += ["", "## Prompt", "", f"`{m['prompt']}`", "", f"Hinted runs append `{m['hinted_suffix']}`.", ""]
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(prog="agent_baseline")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("prep", "run", "score"):
        s = sub.add_parser(name)
        s.add_argument("--data", type=Path, default=ROOT / "scratch" / "agent-baseline" / "data")
        s.add_argument("--runs", type=Path, default=AGENT_ROOT / "runs")
        s.add_argument("--python", type=Path, default=AGENT_ROOT / "venv" / "bin")
        s.add_argument("--only", nargs="*")
        s.add_argument("--timeout", type=int, default=1800)
        s.add_argument("--jobs", type=int, default=4)
    args = p.parse_args()
    return {"prep": cmd_prep, "run": cmd_run, "score": cmd_score}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
