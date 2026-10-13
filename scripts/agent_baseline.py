import argparse
import csv
import hashlib
import io
import json
import math
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

from nbclient import NotebookClient

from waldean.runtime.execute import scrubbed_env, stdout_lines, with_appended_code_cell

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "evals" / "agent-baseline"
MANIFEST = BENCH / "MANIFEST.json"
SCORING = BENCH / "scoring.tsv"
AGENT_ROOT = Path("/private/tmp/waldean-agent-baseline")
AGENT_KERNEL = "waldean-agent-baseline"
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
    if m["schema"] >= 2:
        return check_generated(args, m)
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


def check_generated(args, m: dict) -> int:
    for d in m["datasets"]:
        for name, key in (("data.csv", "csv_sha256"), ("columns.csv", "columns_sha256")):
            digest = sha256(args.data / d["name"] / name)
            if digest != d[key]:
                print(f"{d['name']}/{name}: sha256 {digest} != manifest {d[key]}", file=sys.stderr)
                return 3
        print(d["name"], "ok")
    return 0


def variants(m: dict) -> list[tuple[str, int]]:
    return [(variant, n) for variant, count in m["runs_per_cell"].items() for n in range(count)]


def prompt(m: dict, d: dict, variant: str) -> str:
    text = m["prompt"].format(question=d["question"])
    return text + m["hinted_suffix"].format(hint=d["hint"]) if variant == "hinted" else text


def agent_env(python_bin: Path, cli: str) -> dict:
    keep = {k: os.environ[k] for k in ("HOME", "USER", "LOGNAME", "LANG", "TERM") if k in os.environ}
    cli_dir = str(Path(shutil.which(cli) or cli).parent)
    return {**keep, "TMPDIR": "/private/tmp", "MPLBACKEND": "Agg", "PATH": os.pathsep.join([str(python_bin), cli_dir, "/usr/bin", "/bin"])}


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
             "-c", 'shell_environment_policy.inherit="core"',
             "-c", 'shell_environment_policy.set={MPLBACKEND="Agg"}', "-s", "workspace-write", text], env)


def usage_limited(log_text: str) -> bool:
    return "usage limit" in log_text.lower()


def read_own(path: Path) -> bytes:
    if path.parent.is_symlink():
        raise OSError(f"symlinked run dir: {path.parent}")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        return f.read()


def write_own(path: Path, text: str) -> None:
    if path.is_symlink() or path.exists():
        path.unlink()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def version(cli: str) -> str:
    return subprocess.run([cli, "--version"], capture_output=True, text=True).stdout.strip()


def cmd_run(args) -> int:
    m = manifest()
    if Path.home() in args.runs.resolve().parents or Path.home() in args.python.resolve().parents:
        print("--runs and --python must be outside the home directory, which the agent sandbox cannot read",
              file=sys.stderr)
        return 3
    jobs = [(d, agent, variant, n) for d in m["datasets"] if not args.only or d["name"] in args.only
            for agent in m["agents"] if not args.agents or agent in args.agents
            for variant, n in variants(m) if variant == "default" or d.get("hint")]
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
    if (run_dir / "meta.json").exists() or run_dir.is_symlink():
        return
    run_dir.mkdir(parents=True, exist_ok=True)
    if "run_files" in m:
        for name in m["run_files"]:
            shutil.copyfile(args.data / d["name"] / name, run_dir / name)
    else:
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
    if not (run_dir / "experiment.ipynb").exists() and usage_limited((run_dir / "agent.log").read_text(errors="replace")):
        print(run_dir.name, "usage limit, will rerun", flush=True)
        return
    meta = {"dataset": d["name"], "agent": agent, "variant": variant, "n": n,
            "prompt": text, "cli_version": version(m["agents"][agent]["cli"]),
            "model": m["agents"][agent]["model"], "exit": code,
            "seconds": round(time.time() - start),
            "notebook": (run_dir / "experiment.ipynb").exists()}
    write_own(run_dir / "meta.json", json.dumps(meta, indent=2) + "\n")
    print(run_dir.name, "exit", code, "notebook", meta["notebook"], flush=True)


def bindings() -> dict[str, tuple[str, str]]:
    if not SCORING.exists():
        return {}
    with SCORING.open(encoding="utf-8") as f:
        return {r["run"]: (r["sha256"], r["binding"].replace("\\n", "\n"))
                for r in csv.DictReader(f, delimiter="\t")}


def waldean_check(path: Path) -> list[str]:
    proc = subprocess.run([sys.executable, "-m", "waldean.cli", "check", str(path), "--format", "json"],
                          capture_output=True, text=True)
    try:
        flags = json.loads(proc.stdout).get("flags", [])
    except json.JSONDecodeError:
        return [f"error:{proc.returncode}"]
    return sorted({f["flaw_id"] for f in flags if f.get("confidence", 0) >= 0.8})


def probe(d: dict, nb, run_dir: Path, digest: str, reviewed: tuple[str, str] | None, timeout: int) -> str:
    if "probe_source_regex" in d:
        source = "\n".join(c.source for c in nb.cells if c.cell_type == "code")
        return "pass" if re.search(d["probe_source_regex"], source) else "fail"
    if reviewed is None:
        return "unbound"
    if reviewed[0] != digest:
        return "unreviewed"
    nb = with_appended_code_cell(nb, reviewed[1] + "\n" + d["probe"])
    try:
        with scrubbed_env():
            NotebookClient(nb, timeout=timeout, kernel_name=AGENT_KERNEL,
                           resources={"metadata": {"path": str(run_dir)}}).execute()
    except Exception as exc:
        return f"error:{type(exc).__name__}"
    lines = stdout_lines(nb, "PROBE")
    return "pass" if lines and lines[-1].split()[-1] == "True" else "fail"


def probes(d: dict, nb, run_dir: Path, digest: str, reviewed: tuple[str, str] | None, timeout: int) -> dict:
    crits = d["criteria"]
    if reviewed is None or reviewed[0] != digest:
        return {c: "unbound" if reviewed is None else "unreviewed" for c in crits}
    code = "\n".join([reviewed[1], *(src.replace("print('PROBE',", f"print('PROBE:{c}',") for c, src in crits.items()),
                      "print('HEADLINE:', globals().get('HEADLINE'))"])
    nb = with_appended_code_cell(nb, code)
    try:
        with scrubbed_env():
            NotebookClient(nb, timeout=timeout, kernel_name=AGENT_KERNEL,
                           resources={"metadata": {"path": str(run_dir)}}).execute()
    except Exception as exc:
        return {c: f"error:{type(exc).__name__}" for c in crits}
    out = {}
    for c in crits:
        lines = stdout_lines(nb, f"PROBE:{c} ")
        out[c] = "pass" if lines and lines[-1].split()[-1] == "True" else "fail"
    headline = stdout_lines(nb, "HEADLINE:")
    out["headline"] = headline[-1].removeprefix("HEADLINE:").strip() if headline else ""
    return out


def cmd_score(args) -> int:
    m = manifest()
    by_name = {d["name"]: d for d in m["datasets"]}
    bound = bindings()
    subprocess.run([str(args.python / "python"), "-m", "ipykernel", "install", "--prefix", str(args.python.parent),
                    "--name", AGENT_KERNEL], check=True, capture_output=True)
    os.environ["JUPYTER_PATH"] = str(args.python.parent / "share" / "jupyter")
    stripped = BENCH / "runs"
    stripped.mkdir(exist_ok=True)
    rows = []
    for meta_path in sorted(args.runs.glob("*/meta.json")):
        meta = json.loads(read_own(meta_path))
        run = meta_path.parent.name
        nb_path = meta_path.parent / "experiment.ipynb"
        d = by_name[meta["dataset"]]
        row = {"run": run, **{k: meta[k] for k in ("dataset", "agent", "variant", "cli_version", "model")}}
        if not nb_path.exists():
            row.update(sha256="", check="")
            if "criteria" in d:
                row.update({c: "fail:no-notebook" for c in d["criteria"]})
            else:
                row["probe"] = "fail:no-notebook"
        else:
            raw = read_own(nb_path)
            digest = hashlib.sha256(raw).hexdigest()
            nb = nbformat.reads(raw.decode("utf-8"), as_version=4)
            for c in nb.cells:
                if c.cell_type == "code":
                    c.outputs, c.execution_count = [], None
            nbformat.write(nb, stripped / f"{run}.ipynb")
            row["sha256"] = digest
            row["check"] = ",".join(waldean_check(stripped / f"{run}.ipynb"))
            if "criteria" in d:
                row.update(probes(d, nb, meta_path.parent, digest, bound.get(run), args.timeout))
            else:
                row["probe"] = "n/a" if not d["criterion"] else probe(
                    d, nb, meta_path.parent, digest, bound.get(run), args.timeout)
        rows.append(row)
        print(run, {k: v for k, v in row.items() if k not in ("dataset", "agent", "variant", "cli_version", "model")},
              flush=True)
    with (BENCH / "results.tsv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in rows for k in r)), delimiter="\t", restval="")
        w.writeheader()
        w.writerows(rows)
    report = ROOT / "evals" / f"{date.today().isoformat()}-{BENCH.name}.md"
    report.write_text(render_v2(m, rows) if m["schema"] >= 2 else render(m, rows), encoding="utf-8")
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


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    z = 1.96
    p = k / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    low = (centre - half) / (1 + z * z / n)
    high = (centre + half) / (1 + z * z / n)
    return (max(0.0, low), min(1.0, high))


def detector_counts(rows: list[dict]) -> dict[str, int]:
    out = {"flag_fail": 0, "flag_pass": 0, "noflag_fail": 0, "noflag_pass": 0}
    for r in rows:
        if r.get("selection") not in ("pass", "fail"):
            continue
        flagged = "leakage-test-selection" in r["check"].split(",")
        out[f"{'flag' if flagged else 'noflag'}_{r['selection']}"] += 1
    return out


def gate_v2(fails: int, total: int, open_runs: int) -> str:
    if open_runs or total == 0:
        return "incomplete"
    return "builder rule" if fails >= 2 and fails >= 0.2 * total else "solved by agents"


def render_v2(m: dict, rows: list[dict]) -> str:
    crits = list(m["criteria"])
    agents = list(m["agents"])
    out = [f"# {BENCH.name}, {date.today().isoformat()}", "",
           f"Indicative only. Pre-registered criteria and gate in `{BENCH.name}/MANIFEST.json`.", "",
           "| criterion | datasets | " + " | ".join(f"{a} fail" for a in agents) + " | failure rate | 95% CI | gate |",
           "|---|---|" + "---|" * len(agents) + "---|---|---|"]
    for c in crits:
        mine = [r for r in rows if r.get(c)]
        fails = [r for r in mine if r[c] != "pass"]
        open_runs = sum(r[c] in ("unbound", "unreviewed") for r in mine)
        names = ", ".join(dict.fromkeys(r["dataset"] for r in mine))
        per_agent = [f"{sum(r['agent'] == a for r in fails)}/{sum(r['agent'] == a for r in mine)}" for a in agents]
        rate = f"{len(fails) / len(mine):.0%}" if mine else "-"
        low, high = wilson(len(fails), len(mine))
        gate = gate_v2(len(fails), len(mine), open_runs)
        if gate != "incomplete" and low < 0.2 <= high:
            gate += " (interval includes 20%)"
        out.append(f"| {c} | {names} | " + " | ".join(per_agent)
                   + f" | {rate} | {low:.0%}-{high:.0%} | {gate} |")
    out += ["", "## Per dataset", "", "| dataset | criterion | " + " | ".join(f"{a} pass" for a in agents) + " |",
            "|---|---|" + "---|" * len(agents)]
    for d in m["datasets"]:
        for c in d["criteria"]:
            mine = [r for r in rows if r["dataset"] == d["name"]]
            out.append(f"| {d['name']} | {c} | " + " | ".join(
                f"{sum(r.get(c) == 'pass' for r in mine if r['agent'] == a)}/{sum(r['agent'] == a for r in mine)}"
                for a in agents) + " |")
    if "selection" in crits:
        k = detector_counts(rows)
        flagged = k["flag_fail"] + k["flag_pass"]
        fails = k["flag_fail"] + k["noflag_fail"]
        p_low, p_high = wilson(k["flag_fail"], flagged)
        r_low, r_high = wilson(k["flag_fail"], fails)
        out += ["", "## leakage-test-selection vs manual selection ruling", "",
                "| | ruling fail | ruling pass |", "|---|---|---|",
                f"| flagged | {k['flag_fail']} | {k['flag_pass']} |",
                f"| not flagged | {k['noflag_fail']} | {k['noflag_pass']} |", "",
                f"Precision {k['flag_fail']}/{flagged} (95% CI {p_low:.0%}-{p_high:.0%}), "
                f"recall {k['flag_fail']}/{fails} (95% CI {r_low:.0%}-{r_high:.0%})."]
    out += ["", "## Runs", "", "| run | cli | " + " | ".join(crits) + " | headline | waldean check (confident) |",
            "|---|---|" + "---|" * len(crits) + "---|---|"]
    out += [f"| {r['run']} | {r['cli_version']} | " + " | ".join(r.get(c) or "n/a" for c in crits)
            + f" | {r.get('headline') or '-'} | {r['check'] or '-'} |" for r in rows]
    out += ["", "## Prompt", "", f"`{m['prompt']}`", ""]
    return "\n".join(out)


def main() -> int:
    global BENCH, MANIFEST, SCORING
    p = argparse.ArgumentParser(prog="agent_baseline")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("prep", "run", "score"):
        s = sub.add_parser(name)
        s.add_argument("--bench", default="agent-baseline")
        s.add_argument("--data", type=Path)
        s.add_argument("--runs", type=Path)
        s.add_argument("--python", type=Path, default=AGENT_ROOT / "venv" / "bin")
        s.add_argument("--only", nargs="*")
        s.add_argument("--agents", nargs="*")
        s.add_argument("--timeout", type=int, default=1800)
        s.add_argument("--jobs", type=int, default=4)
    args = p.parse_args()
    BENCH = ROOT / "evals" / args.bench
    MANIFEST = BENCH / "MANIFEST.json"
    SCORING = BENCH / "scoring.tsv"
    suffix = args.bench.removeprefix("agent-baseline")
    args.data = args.data or ROOT / "scratch" / args.bench / "data"
    args.runs = args.runs or AGENT_ROOT / f"runs{suffix}"
    return {"prep": cmd_prep, "run": cmd_run, "score": cmd_score}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
