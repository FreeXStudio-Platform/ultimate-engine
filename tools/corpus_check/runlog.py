"""Per-guard coverage history — a WARNING signal layered on top of the absolute floor.

`P8-054`: `model.passed()`'s floor is a fixed constant compared against a SINGLE run's `checked`
count. A floor low enough to survive ordinary corpus edits is also low enough that a guard can
lose most of its real coverage and still clear it — `register`'s floor is 1 against 442 real
checks, `built-claims`' was 3 against 422. That is exactly `OG-142`'s and `OG-165`'s shape: an
exemption silently widened, `checked` fell hard, and the floor never noticed because nothing ever
asked it to notice a DROP — only an absolute minimum, chosen once and never revisited.

**Why this is advisory, and never a second hard gate.** The number this module compares against
is the guard's own history IN THIS REPOSITORY, which several sessions edit concurrently. A
legitimate correction that fixes ten stale claims at once (`docs/process/RULES.md` Rule 2 being
obeyed — a claim removed because prose stopped restating a derivable fact) lowers `checked` by
design, in the exact shape a real regression takes from the outside. A hard gate on that shape
would either ratchet the corpus into never being allowed to shrink, or need a human escape hatch
identical to `lint_baseline.json`'s pinned ceiling — infrastructure the finding's own fix hint
does not ask for and this package has nowhere to keep out of every other lane's way. So this
module WARNS — visible in the human report and in `--json` — without moving `GuardResult.status`
and without changing the process exit code, the same posture `ci-cost-control.md` §6 describes for
its own budget guard: a WARN is not a finding until it repeats or worsens, and a human reads it.

**Where the log lives.** `.docgen/corpus_check/runs.jsonl`, inside the already-gitignored
`.docgen/` tree `rendered_output.py` uses for its own build output — derived, ephemeral, and never
committed, so no `.gitignore` edit is needed to add this.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tools.corpus_check.model import GuardResult, Status

_LOG_REL = Path(".docgen") / "corpus_check" / "runs.jsonl"

# A guard that checked less than this fraction of its own recorded high-water mark warns. Half is
# deliberately generous — the goal is catching a silent collapse (`OG-165` measured `is_historical`
# suppressing a THIRD of two guards' coverage before it was narrowed), not flagging ordinary
# day-to-day fluctuation as corpus content changes under concurrent edits.
_DROP_RATIO = 0.5

# A bounded tail read, not a full-history scan. This is a rolling window for "has this guard's
# coverage recently collapsed", not an audit trail — `VERIFICATION_LOG.md` and the register files
# are that. An ever-growing log must never make every future run slower to start.
_MAX_LINES_READ = 2000


@dataclass(frozen=True)
class CoverageWarning:
    """One guard whose current PASS checked far fewer claims than its own recorded best."""

    guard: str
    checked: int
    watermark: int

    def render(self) -> str:
        pct = (self.checked / self.watermark) if self.watermark else 0.0
        return (
            f"{self.guard}: checked {self.checked}, a recorded high of {self.watermark} "
            f"claim(s) ({pct:.0%}) — coverage may have silently narrowed; not a failure by itself"
        )


def _log_path(root: Path) -> Path:
    return root / _LOG_REL


def watermark(root: Path, guard: str) -> int | None:
    """The highest `checked` count this guard has ever PASSED with, from recorded history.

    The high-water mark, not the immediately preceding run: a guard that passed at 400, dropped to
    380 on a real fix, then collapsed to 40 has a story the last-run-only comparison cannot tell,
    because by the time of the collapse the "previous" run is already the eroded 380. `None` when
    there is no history to compare against — a fresh checkout, a fresh `.docgen/`, or a guard that
    has never once passed here — which is "nothing to warn about", not "clean".
    """
    path = _log_path(root)
    if not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-_MAX_LINES_READ:]
    except OSError:
        return None
    best: int | None = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        if entry.get("guard") != guard or entry.get("status") != Status.PASS.value:
            continue
        checked = entry.get("checked")
        if isinstance(checked, int) and (best is None or checked > best):
            best = checked
    return best


def record(root: Path, results: list[GuardResult]) -> None:
    """Append this run's outcome, one JSON line per guard result.

    Never raises. A logging failure (read-only filesystem, missing permissions) is an environment
    fact, not a corpus defect, and a guard run must never abort because a directory could not be
    created — the same fail-open posture `rendered_output` takes on a missing render engine.
    """
    path = _log_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for r in results:
                fh.write(
                    json.dumps(
                        {"guard": r.guard, "status": r.status.value, "checked": r.checked, "floor": r.floor}
                    )
                    + "\n"
                )
    except OSError:
        return


def coverage_warnings(root: Path, results: list[GuardResult]) -> list[CoverageWarning]:
    """One `CoverageWarning` per guard whose current PASS is a large drop from its watermark.

    Only guards that PASSED this run are considered: a guard already FAILing has a real finding
    attached to it already, and a SKIP made no claim about coverage to compare. Read the watermark
    from history recorded BEFORE this run — call this before `record()`, not after, or every guard
    would be compared against a watermark that already includes its own current number.
    """
    out: list[CoverageWarning] = []
    for r in results:
        if r.status is not Status.PASS:
            continue
        mark = watermark(root, r.guard)
        if mark is None or mark <= 0:
            continue
        if r.checked < mark * _DROP_RATIO:
            out.append(CoverageWarning(guard=r.guard, checked=r.checked, watermark=mark))
    return out
