"""Result model for the health system. Stdlib only, mypy --strict clean."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    """A check's outcome.

    ``SKIP`` is deliberately NOT a pass: it means the check could not run and the question it
    answers remains open. Callers that need certainty must treat SKIP as unknown, never as green.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


class Stage(str, Enum):
    """Execution stages, in the order they run. Foundation first."""

    STRUCTURE = "1-structure"
    RULE_LAYER = "2-rule-layer"
    CONSISTENCY = "3-consistency"
    BUILD = "4-build"
    SUITES = "5-suites"


@dataclass(frozen=True)
class CheckResult:
    """One check's outcome plus the evidence that justifies it.

    ``evidence`` is mandatory in spirit: a PASS with no evidence is indistinguishable from a check
    that did nothing, which is the exact failure mode this whole system exists to prevent.
    """

    check_id: str
    stage: Stage
    status: Status
    summary: str
    evidence: str = ""
    detail: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True only for an actual pass. SKIP is not ok — it is unknown."""
        return self.status is Status.PASS
