"""Retained counter-examples for `OG-249`: `git show <sha>:<path>` from a host that is NOT the git top-level.

`git log -- <path>` and `git ls-tree <rev> -- <path>` resolve a bare path against the invocation
directory; `git show <rev>:<path>` resolves it against the repository TOP-LEVEL. The two agree only
when the scanned root is the top-level. On a host one directory below its `.git` — a vendored or
nested payload, which `CONFIGURATION.md` explicitly supports — every `git show` in the ratchet and
in the stamp guards read a path that did not exist there: the ratchet memory reported UNAVAILABLE
and every content-certifying stamp would have been unverifiable. Measured 2026-09-07 on a real
host of that shape. The `./` prefix makes `show` resolve from the working directory too.

Each probe builds a real repository with the host in a SUBDIRECTORY, so the bare-path form is
genuinely wrong there — a probe at the top-level would pass on the defective code.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.blueprint import completeness
from tools.corpus_check.corpus import Corpus
from tools.corpus_check.guards import identity as identity_guard
from tools.corpus_check.guards import stamps


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=probe", "-c", "user.email=probe@example.invalid",
         "-c", "commit.gpgsign=false", "-c", "gc.auto=0", *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


class _NestedHost(unittest.TestCase):
    """A git repository whose scanned host is `<repo>/host/`, one level below the top-level."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="og249-")
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name).resolve()
        self.host = self.repo / "host"
        self.host.mkdir()
        _git(self.repo, "init", "-q", "-b", "main")

    def commit(self, message: str) -> str:
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", message)
        return _git(self.repo, "rev-parse", "--short=12", "HEAD")


class RatchetMemoryReadsHistoryFromANestedHost(_NestedHost):
    def test_highest_ever_floor_is_remembered_when_the_host_is_a_subdirectory(self) -> None:
        spec = self.host / "system.spec.json"
        spec.write_text(json.dumps({"system": {"name": "probe"}, "containers": [
            {"id": "c", "name": "C", "purpose": "probe", "packages": ["p"], "depthFloor": 2,
             "document": "README.md"}]}, indent=2) + "\n", encoding="utf-8")
        self.commit("floor 2")
        doc = json.loads(spec.read_text(encoding="utf-8"))
        doc["containers"][0]["depthFloor"] = 1
        spec.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        self.commit("floor lowered to 1")

        historical, gap = completeness._historical_floors(self.host)

        self.assertEqual(gap, "", f"ratchet memory must be available for a nested host, got: {gap!r}")
        self.assertEqual(historical, {"c": 2}, "the highest floor ever committed must be remembered")


class StampGuardsSeeDriftFromANestedHost(_NestedHost):
    """The dangerous half. On the bare-path form the blob read FAILED for every stamp and the
    failure was routed to "unverifiable" *after* `checked` had been incremented — so a nested
    host reported `PASS, N checked` while no body was ever compared. A drifted body is the probe
    that tells the two apart: the fixed guards report it, the defective ones stayed green.
    """

    _HEADER = (
        "---\nid: SPEC-901\nclassification: public\ntitle: Probe\nsurface: repo\n"
        "audience: technical\nowner: probe\nstatus: review\nexport_allowed: true\n"
        "last_reviewed: 2026-09-07\nversion: 0\nrevision: 0\nproduced_by: probe\n"
        "verified_state: verified\n---\n"
    )

    def _stamped_then_drifted(self) -> None:
        note = self.host / "NOTE.md"
        note.write_text(self._HEADER + "# Note\n\nThe body the stamp certifies.\n", encoding="utf-8")
        anchor = self.commit("body")
        _head, _, _body = note.read_text(encoding="utf-8").partition("---\n")
        front, _, rest = note.read_text(encoding="utf-8")[4:].partition("\n---\n")
        stamped = "---\n" + front + "\n---\n" + f"<!-- artifact-hardened: Approved @ {anchor} on 2026-09-07 via probe -->\n" + rest
        note.write_text(stamped, encoding="utf-8")
        self.commit("stamp")
        note.write_text(stamped.replace("The body the stamp certifies.", "A body the stamp no longer covers."), encoding="utf-8")
        self.commit("drift after the stamp, undeclared")

    def test_stamps_guard_reports_an_undeclared_drift(self) -> None:
        self._stamped_then_drifted()
        result = stamps.run(Corpus(root=self.host))
        self.assertTrue(result.findings, f"a drifted stamp must be a finding, got PASS: {result.summary}")
        self.assertTrue(any("NOTE.md" in f.path for f in result.findings), [f.path for f in result.findings])

    def test_identity_guard_reports_a_verified_claim_whose_stamp_no_longer_covers_the_body(self) -> None:
        self._stamped_then_drifted()
        result = identity_guard.run(Corpus(root=self.host))
        self.assertTrue(
            any("no longer covers" in f.message for f in result.findings),
            f"verified_state: verified with a drifted stamp must be a finding, got: {result.summary} / {[f.message for f in result.findings]}",
        )


if __name__ == "__main__":
    unittest.main()
