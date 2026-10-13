from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .analysis.dataflow import analyze
from .analysis.ingest import parse_notebook
from .checks.detect import run_static
from .llm.fuse import run_full_traced

# environment variable each api backend needs before it can make a request
KEY_BY_PROVIDER = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


def missing_subscription_clis() -> bool:
    """True if --llm-subscription can't shell out: claude and/or codex isn't on PATH."""
    return not (shutil.which("claude") and shutil.which("codex"))


def llm_backends(replay_dir, subscription=False):
    from .llm.backends import AgentBackend, AnthropicBackend, CodexBackend, OpenAIBackend, ReplayBackend

    if subscription:
        return AgentBackend(), CodexBackend()

    det, ver = AnthropicBackend(), OpenAIBackend()
    if replay_dir:
        det = ReplayBackend(Path(replay_dir) / "detector", det)
        ver = ReplayBackend(Path(replay_dir) / "verifier", ver)
    return det, ver


def heldout_refusal(path, det, ver) -> str | None:
    """Held-out corpus notebooks are gate-only (m2 item 11): block `check
    --llm` on them so the eval guard can't be sidestepped notebook-by-notebook
    with a replay/agent backend. Real-world corpus notebooks (corpus/real/*)
    are held-out material too — eval folds them into the heldout clean set and
    their manifest carries no per-entry split field, so they are refused by
    living under a `real/` manifest."""
    if det.kind == "api" and ver.kind == "api":
        return None
    p = Path(path).resolve()
    for anc in (p.parent, *p.parent.parents):
        manifest_path = anc / "MANIFEST.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        entries = manifest.get("clean", []) + manifest.get("mutants", [])
        for e in entries:
            f = e.get("file")
            # manifest paths are relative to the manifest dir (corpus/clean/..)
            # or to the corpus root (real/MANIFEST.json prefixes with "real/")
            if f is None or p not in ((anc / f).resolve(), (anc.parent / f).resolve()):
                continue
            if e.get("split") == "heldout" or anc.name == "real":
                return f"{path}: held-out corpus notebook is gate-only, refusing --llm check"
        break
    return None


def missing_llm_keys(*backends) -> list[str]:
    """Env vars an api backend needs but that are unset (replay/agent need none)."""
    missing = []
    for b in backends:
        if b.kind == "api":
            env = KEY_BY_PROVIDER.get(b.provider)
            if env and not os.environ.get(env):
                missing.append(env)
    return sorted(set(missing))


class EmptyDir(Exception):
    """A directory argument contained no notebooks."""


def expand_notebooks(paths: list[str]) -> list[str]:
    """Replace directory arguments with their *.ipynb files, recursive and
    sorted, skipping .ipynb_checkpoints copies. File arguments pass through."""
    expanded = []
    for path in paths:
        p = Path(path)
        if not p.is_dir():
            expanded.append(path)
            continue
        found = sorted(
            str(q) for q in p.rglob("*.ipynb") if ".ipynb_checkpoints" not in q.parts
        )
        if not found:
            raise EmptyDir(path)
        expanded.extend(found)
    return expanded


def absolutize(nb, flags):
    """Rewrite each flag's line-within-cell to a file-absolute line for .py
    scripts, using the cell's recorded start_line. No-op for notebooks."""
    if nb.path is None or nb.path.suffix != ".py":
        return flags
    for f in flags:
        if 0 <= f.cell < len(nb.cells):
            f.line = nb.cells[f.cell].start_line + f.line - 1
    return flags


class BackendError(Exception):
    pass


def check(path, det=None, ver=None, probe=False):
    nb = parse_notebook(path)
    flow = analyze(nb)
    if det is not None:
        flags, narrative, _ = run_full_traced(nb, det, ver)
        # a detector/verifier outage fails closed inside detect_narrative
        # (empty result tagged in `dropped`); surface it so a broken
        # backend can never read like a clean notebook.
        backend_error = next(
            (d for d in narrative.dropped if d.startswith("backend error:")), None
        )
        if backend_error is not None:
            raise BackendError(backend_error)
    else:
        flags = run_static(nb, flow)
    if probe:
        import nbformat

        from .runtime.probe import probe_fit_before_split

        flags = probe_fit_before_split(
            nbformat.read(str(path), as_version=4), flags, cwd=str(Path(path).resolve().parent)
        )
    return nb, flow, absolutize(nb, flags)
