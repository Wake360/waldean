from __future__ import annotations

import copy
import dataclasses
import re

from nbclient.exceptions import CellExecutionError

from waldean.core.flag import Flag
from waldean.runtime import execute as ex

PREFIX = "WALDEAN_PROBE"
CONFIRMED = 0.97
DEMOTED = 0.5
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _probe_source(receiver: str, arg: str) -> str:
    rows = f"len({arg})" if arg else "-1"
    return (
        f"_seen = getattr({receiver}, 'n_samples_seen_', None)\n"
        f"_rows = {rows}\n"
        f"print('{PREFIX}', -1 if _seen is None else int(_seen), int(_rows))"
    )


def _with(flag: Flag, confidence: float, note: str) -> Flag:
    return dataclasses.replace(flag, confidence=confidence, evidence=f"{flag.evidence}; probe: {note}")


def probe_fit_before_split(nb_node, flags: list[Flag], timeout: int = 180, cwd: str | None = None) -> list[Flag]:
    out: list[Flag] = []
    for flag in flags:
        if flag.flaw_id != "leakage-fit-before-split" or not flag.extra.get("receiver"):
            out.append(flag)
            continue
        sink = int(flag.extra.get("sink_cell", flag.cell))
        nb = copy.deepcopy(nb_node)
        nb.cells = nb.cells[: sink + 1]
        nb = ex.with_appended_code_cell(nb, _probe_source(flag.extra["receiver"], flag.extra.get("arg", "")))
        try:
            with ex.scrubbed_env():
                executed = ex.execute(nb, timeout=timeout, cwd=cwd, kernel_name=ex.KERNEL_NAME)
        except CellExecutionError as exc:
            out.append(_with(flag, flag.confidence, f"error ({ANSI_RE.sub('', str(exc)).strip().splitlines()[-1][:120]})"))
            continue
        lines = ex.stdout_lines(executed, PREFIX)
        if not lines:
            out.append(_with(flag, flag.confidence, "no output"))
            continue
        _, seen, rows = lines[-1].split()
        seen, rows = int(seen), int(rows)
        if seen < 0:
            out.append(_with(flag, flag.confidence, "no n_samples_seen_"))
        elif rows > 0 and seen == rows:
            out.append(_with(flag, CONFIRMED, f"n_samples_seen_ = {seen} of {rows} rows"))
        elif rows > 0:
            out.append(_with(flag, DEMOTED, f"n_samples_seen_ = {seen} of {rows} rows"))
        else:
            out.append(_with(flag, flag.confidence, f"n_samples_seen_ = {seen}, rows unknown"))
    return out
