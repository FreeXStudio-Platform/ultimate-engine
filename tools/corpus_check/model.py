"""Result model for the corpus checker. Stdlib only, ``mypy --strict`` clean.

Two ideas carry the whole design and are stated here rather than in each guard:

**A finding names a line.** `docs/process/VERIFICATION_LOG.md` is 410 lines of findings and the ones
that got fixed fastest were the ones that said ``file:line``. A finding a reader has to go hunting
for is a finding that gets deferred.

**A guard reports how much it examined.** ``GuardResult.checked`` is not decoration — it is the
anti-vacuity number. `LESSONS.md` L-19: a check that validates only the claims it can *find* passes
over a document containing none, so emptying the corpus turns every guard green. Each guard declares
a floor; falling under it is a FAILURE with both causes named, because "the corpus lost its claims"
and "the guard stopped seeing them" are equally serious and indistinguishable from here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    """How much a finding matters. Ordered worst-first when sorting output."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


_SEVERITY_ORDER: dict[str, int] = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}


class Status(str, Enum):
    """A guard's outcome.

    ``SKIP`` is deliberately not a pass — same contract as `tools/health/model.py`. It means the
    guard could not run and the question it answers is still open.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class Finding:
    """One defect, with enough evidence for a reader to act without re-deriving anything."""

    guard: str
    path: str
    line: int
    message: str
    evidence: str = ""
    severity: Severity = Severity.MEDIUM

    def where(self) -> str:
        """``path:line``, or just ``path`` for a whole-file finding (``line == 0``)."""
        return f"{self.path}:{self.line}" if self.line else self.path

    def render(self) -> str:
        """One line for a terminal, evidence appended when there is any."""
        head = f"{self.severity.value:<8} {self.where()}  {self.message}"
        return f"{head}\n{'':<9}{self.evidence}" if self.evidence else head


@dataclass(frozen=True)
class GuardResult:
    """One guard's outcome plus the two numbers that make it auditable.

    ``checked`` is how many claims the guard actually examined; ``floor`` is the minimum it must
    examine for its verdict to mean anything. A clean guard that examined nothing is reported as a
    FAILURE, never as a pass.
    """

    guard: str
    status: Status
    summary: str
    findings: list[Finding] = field(default_factory=list)
    checked: int = 0
    floor: int = 0
    evidence: str = ""

    @property
    def ok(self) -> bool:
        """True only for an actual pass. SKIP is unknown, never green."""
        return self.status is Status.PASS

    def sorted_findings(self) -> list[Finding]:
        """Worst first, then by location — the order a reader wants to work down."""
        return sorted(
            self.findings,
            key=lambda f: (_SEVERITY_ORDER[f.severity], f.path, f.line),
        )


def passed(guard: str, summary: str, *, checked: int, floor: int = 0, evidence: str = "") -> GuardResult:
    """A clean guard — **unless it examined too little to have decided anything**.

    The demotion happens here, once, rather than in nine guards that would each have to remember
    to do it.
    """
    if checked < floor:
        return GuardResult(
            guard=guard,
            status=Status.FAIL,
            summary=f"{guard}: examined only {checked} claim(s), floor is {floor}",
            checked=checked,
            floor=floor,
            evidence=(
                "Either the corpus lost the claims this guard exists to check, or the guard "
                "stopped being able to see them. Both are defects; passing over nothing is not a "
                "pass (LESSONS.md L-19)."
            ),
        )
    return GuardResult(
        guard=guard,
        status=Status.PASS,
        summary=summary,
        checked=checked,
        floor=floor,
        evidence=evidence,
    )


def failed(
    guard: str,
    findings: list[Finding],
    *,
    checked: int,
    floor: int = 0,
    summary: str = "",
) -> GuardResult:
    """A guard that found something. ``summary`` defaults to the finding count."""
    return GuardResult(
        guard=guard,
        status=Status.FAIL,
        summary=summary or f"{guard}: {len(findings)} finding(s) across {checked} claim(s) checked",
        findings=findings,
        checked=checked,
        floor=floor,
    )


def skipped(guard: str, reason: str, *, evidence: str = "") -> GuardResult:
    """A guard that could not run. Never counts as a pass."""
    return GuardResult(guard=guard, status=Status.SKIP, summary=reason, evidence=evidence)
