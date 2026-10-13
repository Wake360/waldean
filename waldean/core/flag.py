from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_CONFIDENCE_FLOOR = 0.8


@dataclass
class Flag:
    flaw_id: str
    severity: str
    confidence: float
    cell: int
    line: int
    evidence: str
    failure_scenario: str
    fix: str
    extra: dict = field(default_factory=dict)
