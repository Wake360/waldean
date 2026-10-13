"""Notebook execution for corpus building and mutation verification.

User notebooks are executed only by `waldean verify --execute`, in a separate waldean-verify kernel.
"""

from __future__ import annotations

import contextlib
import copy
import importlib.metadata
import os
import platform
import re
import sys

import nbformat
from ipykernel.kernelspec import install as install_kernelspec
from jupyter_client.kernelspec import KernelSpecManager, NoSuchKernel
from nbclient import NotebookClient

KERNEL_NAME = "waldean-verify"
SECRET_ENV_RE = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", re.IGNORECASE)


def _ensure_kernelspec(kernel_name: str = "python3") -> None:
    """Make kernel_name resolve to the running interpreter, not an ambient one."""
    try:
        spec = KernelSpecManager().get_kernel_spec(kernel_name)
    except NoSuchKernel:
        spec = None
    if spec is None or spec.argv[0] != sys.executable:
        install_kernelspec(user=True, kernel_name=kernel_name)


def execute(nb_node, timeout: int = 180, cwd: str | None = None, kernel_name: str = "python3"):
    """Execute a notebook node in place-safe copy; returns the executed node."""
    nb = copy.deepcopy(nb_node)
    _ensure_kernelspec(kernel_name)
    resources = {"metadata": {"path": cwd}} if cwd else {}
    client = NotebookClient(nb, timeout=timeout, kernel_name=kernel_name, resources=resources)
    client.execute()
    return nb


def with_appended_code_cell(nb_node, source: str):
    nb = copy.deepcopy(nb_node)
    nb.cells.append(nbformat.v4.new_code_cell(source))
    return nb


def stdout_lines(nb_node, prefix: str) -> list[str]:
    """Collect stream-output lines starting with prefix across all cells."""
    lines = []
    for cell in nb_node.cells:
        for out in cell.get("outputs", []):
            if out.get("output_type") == "stream":
                for line in out.get("text", "").splitlines():
                    if line.startswith(prefix):
                        lines.append(line)
    return lines


@contextlib.contextmanager
def scrubbed_env():
    removed = {k: os.environ.pop(k) for k in list(os.environ) if SECRET_ENV_RE.search(k)}
    try:
        yield sorted(removed)
    finally:
        os.environ.update(removed)


PROVENANCE_PACKAGES = ("numpy", "pandas", "scikit-learn")


def provenance() -> dict:
    packages = {}
    for name in PROVENANCE_PACKAGES:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    try:
        waldean_version = importlib.metadata.version("waldean")
    except importlib.metadata.PackageNotFoundError:
        waldean_version = "unknown"
    return {
        "waldean": waldean_version,
        "python": platform.python_version(),
        "platform": platform.system(),
        "packages": packages,
    }
