"""Counter-examples for the Phase-6 completeness layer — the acceptance set, falsified both ways.

`BUILD_PLAN.md` row 6's acceptance set was written before any of this code existed. These are the
probes those lines select.

**The report must MOVE, or it is a picture.** Every state and every ratchet verdict here is proven
by changing the evidence in a throwaway copy of the tree and watching the answer change, then
restoring it and watching it change back. A report that always says the same thing would satisfy a
probe that only asserted its shape.

**Every subject set is derived** (`LESSONS.md` L-37), and every `-k` token selects its whole group —
Phase 5 measured that a token matching one probe of eleven satisfies an acceptance line while
gutting it.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.blueprint import completeness as comp
from tools.blueprint.model import build_model
from tools.tests.lab import ROOT as _ROOT
from tools.tests.lab import LabCase, force_rmtree


def _first_block_is_a_doc_header(text: str) -> bool:
    """Does this file's FIRST front-matter block declare a doc-system header?

    Written independently of `completeness._front_matter_keys` on purpose — a probe that calls its
    subject's own function shares its blind spot. But "independent" is not "naive": the first
    version scanned the opening kilobyte and matched a doc-system header shown as an EXAMPLE inside
    a fenced code block in `skills/document-engine/SKILL.md`, which has its own unrelated YAML
    header. Bounding the scan to the first block is what makes it independent AND right.
    """
    if not text.startswith("---\n"):
        return False
    block = text.split("---\n", 2)
    if len(block) < 3:
        return False
    body = block[1]
    return bool(
        re.search(r"^id:\s*\S", body, re.MULTILINE) and re.search(r"^classification:\s*\S", body, re.MULTILINE)
    )


def _env() -> dict[str, str]:
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = str(_ROOT)
    return env


class _Phase6Lab(LabCase):
    lab_prefix = "bp6-lab-"

    def setUp(self) -> None:
        # The lab is shared per class, so a probe that mutates the spec and does not restore it
        # poisons every probe that runs after — measured: the ratchet's positive control failed
        # because an earlier probe deleted a floor and left it deleted. Snapshot and restore around
        # EVERY test rather than trusting each one to clean up after itself.
        self._spec_backup = (self.lab / "system.spec.json").read_text(encoding="utf-8")
        self.addCleanup(
            lambda: (self.lab / "system.spec.json").write_text(self._spec_backup, encoding="utf-8")
        )

    def report(self) -> dict[str, Any]:
        report: dict[str, Any] = build_model(self.lab)["completeness"]
        return report

    def spec(self) -> dict[str, Any]:
        doc: dict[str, Any] = json.loads(
            (self.lab / "system.spec.json").read_text(encoding="utf-8")
        )
        return doc

    def write_spec(self, doc: dict[str, Any]) -> None:
        (self.lab / "system.spec.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")


class CompletenessClassifiesEveryNodeFromEvidence(_Phase6Lab):
    """A-1 and A-2 — the three states, and the proof that they are measured rather than declared."""

    def test_completeness_every_node_lands_in_exactly_one_state(self) -> None:
        report = self.report()
        nodes = report["nodes"]
        model_modules = {n["id"] for n in build_model(self.lab)["graph"]["nodes"]}
        self.assertTrue(model_modules, "derived subject set is empty")
        self.assertEqual(set(nodes), model_modules, "every node must be classified, and only nodes")
        for module_id, record in nodes.items():
            self.assertIn(record["state"], comp.NODE_STATES, module_id)
            self.assertTrue(record["why"], f"{module_id} carries no reason for its state")
        self.assertEqual(sum(report["summary"].values()), len(nodes))

    def test_completeness_the_summary_agrees_with_the_per_node_states(self) -> None:
        """A summary that disagrees with its own detail is the `OG-132` shape."""
        report = self.report()
        counted: dict[str, int] = {state: 0 for state in comp.NODE_STATES}
        for record in report["nodes"].values():
            counted[record["state"]] += 1
        self.assertEqual(counted, report["summary"])

    def test_completeness_every_documented_node_satisfies_its_definition(self) -> None:
        """`OG-217` — a verifier found the `documented` definition said `rungs 2-3` while the code
        classified 33 rung-4 nodes as `documented` (and the module docstring said `rungs 2-4`, a
        drifted third copy). Every node must satisfy the state it is given: `documented` = rungs 2-3,
        OR rung 4 or deeper whose owning document is not verified. This is the L-39 shape one layer up
        — a definition contradicted by the logic that assigns it.

        Extended after a later verifier drove the SAME shape one rung further: once a node's owning
        document claims verified, `depth.py` reads it at rung 5 (`detail`), so a `verified`/
        `documented` node can measure rung 5 — and a definition that named a TERMINAL `rung 4`
        excluded that node's real rung. The rung numbers are FLOORS; the invariant below ties the
        wording to the classification constant so a point-rung claim cannot be reintroduced.
        """
        model = build_model(self.lab)
        report = comp.build(self.lab, model)
        depths = model["depth"]["modules"]
        rung4_documented = 0
        for module_id, record in report["nodes"].items():
            depth = int(depths[module_id]["depth"])
            state = record["state"]
            if state == comp.SKETCHED:
                self.assertLess(depth, 2, f"{module_id} is sketched but reached rung {depth}")
            elif state == comp.DOCUMENTED:
                self.assertGreaterEqual(depth, 2, f"{module_id} is documented but only rung {depth}")
                if depth >= comp._VERIFIED_FROM_RUNG:
                    rung4_documented += 1
            elif state == comp.VERIFIED:
                self.assertGreaterEqual(
                    depth, comp._VERIFIED_FROM_RUNG,
                    f"{module_id} is verified but only rung {depth}",
                )
        # The definition's second clause ('or rung 4 not yet verified') must describe real nodes, or
        # it is dead prose claiming a case that never occurs. While `verified` is 0 this is all of
        # them; it stays > 0 after a container-owning document is stamped, because most rung-4 nodes
        # keep no verified owner.
        self.assertGreater(
            rung4_documented, 0,
            "no rung-4 documented node — the `documented` definition's second clause is dead prose",
        )
        # OG-217 (rung-5 recurrence): the definitions must name the FLOOR rung AND mark it "or deeper"
        # — a terminal `rung N` excludes a node the ladder measures above N (the moat reaches rung 5).
        # Tied to the constant so the number and the floor-marker cannot drift apart or regress.
        floor_phrase = f"rung {comp._VERIFIED_FROM_RUNG} or deeper"
        self.assertIn(
            floor_phrase, comp.STATE_DEFINITIONS[comp.VERIFIED],
            f"the `verified` definition must say '{floor_phrase}' (a floor), not a terminal rung — "
            "else it excludes a node measured deeper than the floor (OG-217, the rung-5 recurrence)",
        )
        self.assertIn(
            floor_phrase, comp.STATE_DEFINITIONS[comp.DOCUMENTED],
            f"the `documented` definition's upper clause must say '{floor_phrase}' (uncertified), so "
            "a rung-5 uncertified node is described rather than excluded",
        )
        # OG-217 round 2 (R2V3-5): the floor-phrase pin above binds only the "or deeper" clause, so a
        # verifier re-expressed the ORIGINAL OG-217 defect — `documented`'s first clause back to the
        # over-claiming "rungs 2-4" — with every test green. Pin the first-clause span too: `documented`
        # spans rungs 2-3 (below rung 4), and writing "rungs 2-4" would textually overlap `verified`
        # and un-partition the states in prose while the code still partitions them.
        self.assertIn(
            "rungs 2-3", comp.STATE_DEFINITIONS[comp.DOCUMENTED],
            "the `documented` definition's first clause must span `rungs 2-3`, not `rungs 2-4` (which "
            "the OG-217 defect over-claimed) — otherwise it overlaps `verified` and un-partitions the "
            "rung-4 nodes the two states are defined to split",
        )

    def test_completeness_rendered_table_is_emitted_from_the_constant(self) -> None:
        """`OG-217` round 2 (R2V3-4) — the definitions are single-sourced in `STATE_DEFINITIONS`, and
        the module comment claims a probe compares the RENDERED table with the constant. No such probe
        existed: a verifier re-hardcoded a renderer row to the historically-refuted wording and every
        test stayed green — the exact 'the fix landed where no reader of the report looks' shape the
        single source exists to prevent. This renders the table and asserts each state's row carries
        its `STATE_DEFINITIONS` text character-for-character, so the renderer cannot drift from it."""
        from tools.blueprint.render import render_completeness

        rendered = render_completeness(build_model(self.lab))
        for state, definition in comp.STATE_DEFINITIONS.items():
            expected = f"| `{state}` | {definition} |"
            self.assertIn(
                expected, rendered,
                f"the rendered COMPLETENESS.md row for `{state}` does not match STATE_DEFINITIONS "
                "character-for-character — the renderer has drifted from its single source",
            )

    def test_completeness_a_node_falls_when_its_evidence_is_removed(self) -> None:
        """The measurement, falsified. Take a docstring away and the state must drop to `sketched`.

        The subject is derived from the live model rather than named, so the probe cannot rot when
        the tree changes around it.
        """
        before = self.report()["nodes"]
        victim = next(
            (
                m for m, r in sorted(before.items())
                if r["state"] == comp.DOCUMENTED
                and (self.lab / (m.replace(".", "/") + ".py")).is_file()
            ),
            None,
        )
        self.assertIsNotNone(victim, "no documented leaf module — derived subject set is empty")
        assert victim is not None
        path = self.lab / (victim.replace(".", "/") + ".py")
        original = path.read_text(encoding="utf-8")
        self.addCleanup(lambda: path.write_text(original, encoding="utf-8"))

        # Strip everything that could satisfy rungs 1 and 2 at once.
        path.write_text("_ = None\n", encoding="utf-8")
        after = self.report()["nodes"]
        self.assertEqual(
            after[victim]["state"], comp.SKETCHED,
            f"{victim} lost its purpose and its contents but did not fall to sketched",
        )
        path.write_text(original, encoding="utf-8")
        self.assertEqual(self.report()["nodes"][victim]["state"], comp.DOCUMENTED)

    def test_completeness_verified_is_REACHABLE_positive_control(self) -> None:
        """**The probe whose absence let a three-state report become a two-state one.**

        A verifier hardwired the stamp check to always fail — making `verified` structurally
        unreachable — and ran `-k completeness` (5), this file (15) and the whole suite (502). All
        green. Only the DENIAL was proven; nothing anywhere demonstrated a node reaching the state.

        This builds one end to end through unmodified machinery: govern a container-owning document,
        commit it, stamp it at that commit, and require nodes at rung 4 in that container to report
        `verified`.
        """
        model = build_model(self.lab)
        # A container whose owning document has modules AT RUNG 4 — below that, `verified` is
        # correctly unreachable however well-stamped the document is, so a shallower container would
        # make this probe pass for the wrong reason.
        depths = model["depth"]["modules"]
        owner = model["ownership"]["owner"]
        target = next(
            (
                c for c in model["containers"]
                if any(depths.get(m, {}).get("depth", 0) >= 4
                       for m, cid in owner.items() if cid == c["id"])
            ),
            None,
        )
        self.assertIsNotNone(target, "no container has a rung-4 module — subject set is empty")
        assert target is not None
        rel = target["document"]
        path = self.lab / rel
        original = path.read_text(encoding="utf-8")
        self.addCleanup(lambda: path.write_text(original, encoding="utf-8"))

        header = (
            "---\n"
            "id: WF-902\nclassification: public\ntitle: Positive control\naudience: technical\n"
            "owner: probe\nstatus: final\nexport_allowed: true\nsurface: web\n"
            "last_reviewed: 2026-08-29\nverified_state: verified\n"
            "---\n\n"
        )
        path.write_text(header + original, encoding="utf-8")
        sha = subprocess.run(
            ("git", "-C", str(self.lab), "-c", "user.email=l@l", "-c", "user.name=l",
             "commit", "-q", "-a", "-m", "positive control"),
            capture_output=True, text=True, timeout=120, check=False,
        )
        self.assertEqual(sha.returncode, 0, sha.stderr)
        head = subprocess.run(
            ("git", "-C", str(self.lab), "rev-parse", "HEAD"),
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout.strip()
        # Appended with NO blank line before it. `body_without_stamps` removes the stamp LINE but
        # keeps every other line, so an inserted blank would survive stripping and read as body
        # drift — the stamp would be well-formed and the comparison would still fail.
        path.write_text(
            header + original
            + f"<!-- artifact-hardened: Approved @ {head} on 2026-08-29 via three-pass-v1 -->\n",
            encoding="utf-8",
        )

        nodes = self.report()["nodes"]
        deep = [m for m, cid in owner.items()
                if cid == target["id"] and depths.get(m, {}).get("depth", 0) >= 4]
        self.assertTrue(deep, "no rung-4 module in the chosen container")
        self.assertTrue(
            any(nodes[m]["state"] == comp.VERIFIED for m in deep),
            f"a governed, stamped owning document did not lift ANY rung-4 node in "
            f"{target['id']} to verified: {[nodes[m] for m in deep[:2]]}",
        )

    def test_completeness_verified_requires_rung_4_not_merely_a_stamped_document(self) -> None:
        """`verified` published as 'all of documented, AND the document' but asked only for rung 2.

        In a lab a module that no gate reads and no counter-example names reported `verified`. The
        state must now require the top of `documented`.
        """
        model = build_model(self.lab)
        depths = model["depth"]["modules"]
        nodes = self.report()["nodes"]
        for module_id, record in nodes.items():
            if record["state"] == comp.VERIFIED:
                self.assertGreaterEqual(
                    int(depths[module_id]["depth"]), 4,
                    f"{module_id} is verified at rung {depths[module_id]['depth']}",
                )

    def test_completeness_verified_requires_a_stamp_not_merely_a_claim(self) -> None:
        """The exit condition's load-bearing word is *evidence*.

        A document that CLAIMS `verified_state: verified` with no stamp behind it must not lift its
        container's nodes to `verified`. This is the split Phase 5 had to correct its own docstring
        for: the ladder reads the claim, this report demands the evidence.
        """
        model = build_model(self.lab)
        depths0 = model["depth"]["modules"]
        owner0 = model["ownership"]["owner"]
        container = next(
            c for c in model["containers"]
            if any(depths0.get(m, {}).get("depth", 0) >= 4
                   for m, cid in owner0.items() if cid == c["id"])
        )
        doc_rel = container["document"]
        doc_path = self.lab / doc_rel
        original = doc_path.read_text(encoding="utf-8")
        self.addCleanup(lambda: doc_path.write_text(original, encoding="utf-8"))

        header = (
            "---\n"
            "id: WF-901\nclassification: public\ntitle: Probe\naudience: technical\n"
            "owner: probe\nstatus: final\nexport_allowed: true\nsurface: web\n"
            "last_reviewed: 2026-08-29\nverified_state: verified\n"
            "---\n\n"
        )
        doc_path.write_text(header + original, encoding="utf-8")
        after = build_model(self.lab)
        nodes = after["completeness"]["nodes"]
        depths = after["depth"]["modules"]
        owned = [m for m, c in after["ownership"]["owner"].items() if c == container["id"]]
        self.assertTrue(owned, "container owns no modules — derived subject set is empty")
        deep = [m for m in owned if int(depths.get(m, {}).get("depth", 0)) >= 4]
        self.assertTrue(deep, "no rung-4 module — the subject could not reach verified anyway")
        for module_id in deep:
            self.assertNotEqual(
                nodes[module_id]["state"], comp.VERIFIED,
                f"{module_id} reached `verified` on a claim with no stamp behind it",
            )
            # Rung-4 nodes are eligible, so the reason must be about the STAMP, not the rung.
            self.assertIn("stamp", nodes[module_id]["why"])


class LifecycleReportsEveryStepFromItsOwner(_Phase6Lab):
    """A-3 — tag / wire / date / version / changelog / stamp, per governed document.

    **Every step is falsified independently, and every expectation is computed independently.**
    The first version of this class did neither, and a verifier proved the cost: it computed the
    governed set with the SAME expression as the code (blind to archived snapshots being injected),
    called the IDENTICAL wrong `archive_id` expression for `version` (blind to that step being
    structurally unreachable), ran that check over ZERO subjects, and guarded its own vacuity with
    `assertEqual(checked, <recount of checked>)` — `0 == 0`, always true. Four of the six steps were
    never falsified at all.
    """

    def _lifecycle(self) -> dict[str, dict[str, bool]]:
        return {d["path"]: d["steps"] for d in self.report()["documents"]}

    def _a_governed_document(self) -> str:
        """A governed document path, derived WITHOUT the code's own predicate.

        Independent oracle: parse the file's own front matter and require a real `id` and
        `classification`. The subject must not be chosen by the expression under test.
        """
        for rel in subprocess.run(
            ("git", "-C", str(self.lab), "ls-files", "*.md"),
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout.split():
            if "/archive/" in rel:
                continue
            if _first_block_is_a_doc_header((self.lab / rel).read_text(
                    encoding="utf-8", errors="replace")):
                return rel
        self.fail("no governed document found by independent parsing — subject set is empty")
        raise AssertionError

    def test_lifecycle_covers_the_governed_documents_by_independent_parsing(self) -> None:
        governed = set()
        for rel in subprocess.run(
            ("git", "-C", str(self.lab), "ls-files", "*.md"),
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout.split():
            if _first_block_is_a_doc_header((self.lab / rel).read_text(
                    encoding="utf-8", errors="replace")):
                governed.add(rel)
        self.assertTrue(governed, "derived subject set is empty")
        reported = set(self._lifecycle())
        # Archived snapshots are governed by this oracle but are NOT live documents; the report must
        # exclude them, and a verifier proved it did not until `is_archived_path` was wired in.
        self.assertEqual(reported, {g for g in governed if "/archive/" not in g})

    def test_lifecycle_reports_all_six_steps_for_every_document(self) -> None:
        for doc in self.report()["documents"]:
            self.assertEqual(set(doc["steps"]), set(comp.LIFECYCLE_STEPS), doc["path"])
            self.assertEqual(doc["of"], len(comp.LIFECYCLE_STEPS))

    def test_lifecycle_wire_follows_the_manifest_ROW_not_the_file_text(self) -> None:
        """The manifest's rule is a TYPE PREFIX row, not a substring of the file.

        A verifier flipped a document to `wire: true` by appending a comment saying it *"was deleted
        and must never be built"* — the report asserting the opposite of the text it read.
        """
        rel = self._a_governed_document()
        self.assertTrue(self._lifecycle()[rel]["wire"], f"{rel} should start wired")
        manifest = self.lab / "docs/design/doc-system/DOC_MANIFEST.md"
        original = manifest.read_text(encoding="utf-8")
        self.addCleanup(lambda: manifest.write_text(original, encoding="utf-8"))

        # The prefix comes from the MANIFEST's own rows, not from re-splitting the id the way the
        # code does. The first version computed `doc_id.split("-", 1)[0]` — character for character
        # the expression under test — so it was blind by construction to the code disagreeing with
        # `classification._extract_prefix`, which is exactly what it did.
        from tools.docgen import doc_manifest, engine_config

        doc_id = next(d["id"] for d in self.report()["documents"] if d["path"] == rel)
        rows = doc_manifest.read_manifest(engine_config.doc_manifest_path())
        prefix = next((r.id for r in rows if doc_id.startswith(r.id + "-")), None)
        self.assertIsNotNone(prefix, f"no manifest row matches {doc_id} — subject set is empty")

        # Removing that ROW must unwire it. (The previous "prose does not wire it" assertion was a
        # tautology: it checked the report's ids for a document that was never created.)
        stripped = "\n".join(
            line for line in original.splitlines()
            if not (line.lstrip().startswith("|")
                    and line.split("|")[1].strip().strip("`") == prefix)
        )
        manifest.write_text(stripped, encoding="utf-8")
        self.assertFalse(
            self._lifecycle()[rel]["wire"],
            f"the manifest no longer carries a `{prefix}` row, but `wire` still reports complete",
        )

    def test_lifecycle_date_reads_the_header_field_not_the_body_text(self) -> None:
        """Three false positives a verifier demonstrated: field deleted but discussed in prose,
        field present but EMPTY, and a `produced_by` standing in for a review date."""
        rel = self._a_governed_document()
        path = self.lab / rel
        original = path.read_text(encoding="utf-8")
        self.addCleanup(lambda: path.write_text(original, encoding="utf-8"))
        self.assertTrue(self._lifecycle()[rel]["date"], f"{rel} should start dated")

        import re as _re

        # (1) field removed entirely, the word left in the body
        path.write_text(
            _re.sub(r"^last_reviewed:.*$", "", original, flags=_re.MULTILINE)
            + "\n\nThis document explains the `last_reviewed` field.\n",
            encoding="utf-8",
        )
        self.assertFalse(self._lifecycle()[rel]["date"], "prose mentioning the field dated it")

        # (2) field present but empty
        path.write_text(_re.sub(r"^last_reviewed:.*$", "last_reviewed:", original, flags=_re.MULTILINE),
                        encoding="utf-8")
        self.assertFalse(self._lifecycle()[rel]["date"], "an empty field counted as a date")

    def test_lifecycle_tag_requires_the_surface_its_contract_names(self) -> None:
        """`tag` was half tautology and never read the `surface` its own comment claimed."""
        import re as _re

        rel = self._a_governed_document()
        path = self.lab / rel
        original = path.read_text(encoding="utf-8")
        self.addCleanup(lambda: path.write_text(original, encoding="utf-8"))
        self.assertTrue(self._lifecycle()[rel]["tag"])
        path.write_text(_re.sub(r"^surface:.*$", "surface:", original, flags=_re.MULTILINE), encoding="utf-8")
        self.assertFalse(self._lifecycle()[rel]["tag"], "a document with no surface reported tagged")

    def test_lifecycle_version_is_REACHABLE_and_follows_a_real_archive_cut(self) -> None:
        """The step was structurally unreachable: it resolved a path slug while the writer used the
        header id, so no governed document could ever satisfy it. Proven by cutting a real version
        through the engine's own command — not by recomputing the id the way the code does."""
        rel = self._a_governed_document()
        self.assertFalse(self._lifecycle()[rel]["version"], f"{rel} should start unversioned")
        proc = subprocess.run(
            (sys.executable, "-m", "tools.docgen.cli", "archive", "cut", rel, "--date", "2026-08-29"),
            cwd=self.lab, capture_output=True, text=True, timeout=300,
            env={**_env(), "ENGINE_HOST_ROOT": str(self.lab)}, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.addCleanup(lambda: shutil.rmtree(self.lab / "docs/archive", ignore_errors=True))

        # A cut that is not staged is not a version anyone else has. `version` resolves against
        # `git ls-files`, like every other fact in the map, on the stated grounds that an untracked
        # file is present for its author and absent for everybody else — so an unstaged cut must
        # still report incomplete, and staging it must flip the step.
        self.assertFalse(
            self._lifecycle()[rel]["version"],
            "an UNTRACKED snapshot was counted as a version a fresh clone would not have",
        )
        subprocess.run(("git", "-C", str(self.lab), "add", "-A"),
                       check=True, capture_output=True, timeout=120)
        self.addCleanup(lambda: subprocess.run(
            ("git", "-C", str(self.lab), "rm", "-r", "-q", "--cached", "--ignore-unmatch",
             "docs/archive"), capture_output=True, timeout=120, check=False))
        self.assertTrue(
            self._lifecycle()[rel]["version"],
            f"a real, tracked snapshot was cut for {rel} and `version` still reports incomplete",
        )

    def test_lifecycle_stamp_requires_a_BODY_CERTIFYING_kind(self) -> None:
        """Presence-only accepted any kind, including ones the engine excludes by design."""
        rel = self._a_governed_document()
        path = self.lab / rel
        original = path.read_text(encoding="utf-8")
        self.addCleanup(lambda: path.write_text(original, encoding="utf-8"))
        self.assertFalse(self._lifecycle()[rel]["stamp"])

        path.write_text(
            original + "\n<!-- session-state: current @ deadbeef on 2026-08-29 via three-pass-v1 -->\n",
            encoding="utf-8",
        )
        self.assertFalse(
            self._lifecycle()[rel]["stamp"],
            "a kind the engine excludes from body certification counted as a stamp",
        )
        # A body-certifying stamp whose sha RESOLVES and whose body still matches. The first version
        # asserted that `@ deadbeef` — a sha that resolves to nothing — counted as a stamp, so the
        # false positive was load-bearing: any fix requiring a resolvable commit turned this probe
        # RED. A probe must not pin the defect it was written beside.
        path.write_text(
            original + "<!-- artifact-hardened: Approved @ deadbeef on 2026-08-29 via three-pass-v1 -->\n",
            encoding="utf-8",
        )
        self.assertFalse(
            self._lifecycle()[rel]["stamp"],
            "a stamp whose commit resolves to nothing was counted as complete",
        )
        path.write_text(original, encoding="utf-8")
        subprocess.run(
            ("git", "-C", str(self.lab), "-c", "user.email=l@l", "-c", "user.name=l",
             "commit", "-q", "-a", "-m", "stamp base"),
            capture_output=True, text=True, timeout=120, check=False,
        )
        head = subprocess.run(
            ("git", "-C", str(self.lab), "rev-parse", "HEAD"),
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout.strip()
        path.write_text(
            original
            + f"<!-- artifact-hardened: Approved @ {head} on 2026-08-29 via three-pass-v1 -->\n",
            encoding="utf-8",
        )
        self.assertTrue(
            self._lifecycle()[rel]["stamp"],
            "a body-certifying stamp that still covers the body was not counted",
        )

    def test_lifecycle_changelog_follows_the_change_record(self) -> None:
        rel = self._a_governed_document()
        changelog = self.lab / "CHANGELOG.md"
        original = changelog.read_text(encoding="utf-8")
        self.addCleanup(lambda: changelog.write_text(original, encoding="utf-8"))
        doc_id = next(d["id"] for d in self.report()["documents"] if d["path"] == rel)
        changelog.write_text(
            original.replace(rel, "docs/ZZ_REMOVED.md").replace(doc_id, "ZZ-000"), encoding="utf-8"
        )
        self.assertFalse(
            self._lifecycle()[rel]["changelog"],
            "the change record no longer names this document, but the step still reports complete",
        )


class TheDepthRatchetIsEnforcedInBothDirections(_Phase6Lab):
    """A-4 — the ladder ENFORCED. A ratchet that can be loosened is a suggestion."""

    def test_floor_the_committed_tree_is_level(self) -> None:
        """The positive control. Without it every probe below could pass on a broken checker."""
        self.assertEqual(self.report()["floor_findings"], [])

    def test_floor_a_container_below_its_floor_is_refused(self) -> None:
        doc = self.spec()
        container = doc["containers"][0]
        container["depthFloor"] = container["depthFloor"] + 3
        self.write_spec(doc)
        findings = self.report()["floor_findings"]
        self.assertTrue(any(container["id"] in f and "below" in f for f in findings), findings)

    def test_floor_written_beneath_the_measurement_is_also_refused(self) -> None:
        """The direction that is easy to slip past review: a regression made permanent in advance."""
        doc = self.spec()
        container = next(c for c in doc["containers"] if c["depthFloor"] > 0)
        container["depthFloor"] = 0
        self.write_spec(doc)
        findings = self.report()["floor_findings"]
        self.assertTrue(any(container["id"] in f and "slack" in f for f in findings), findings)

    def test_floor_a_container_with_no_floor_at_all_is_refused(self) -> None:
        doc = self.spec()
        del doc["containers"][0]["depthFloor"]
        self.write_spec(doc)
        findings = self.report()["floor_findings"]
        self.assertTrue(any("declares no `depth_floor`" in f for f in findings), findings)

    def test_floor_a_LOOSENING_is_refused_even_after_it_is_committed(self) -> None:
        """**The direction that had no probe at all, in a lab that can finally express it.**

        The ratchet's memory was `HEAD`, and `HEAD` is written by the commit under scrutiny — a
        verifier defeated it by committing the loosening. Worse, the shared lab `git init`s its own
        tree, so inside every probe `HEAD` IS the state under test: the memory could not exist, and
        `test_floor_the_committed_tree_is_level` reported level on a loosened tree while the report
        claimed `ratchet memory: git HEAD`.

        This builds its own repository with REAL history — a pristine commit, then the loosening as
        a second commit — which is the only shape in which the fix is testable at all.
        """
        import tempfile

        from tools.blueprint import completeness as c
        from tools.blueprint.model import build_model as bm

        tmp = tempfile.TemporaryDirectory(prefix="ratchet-hist-", ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name) / "repo"
        shutil.copytree(self.lab, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        git = ("git", "-C", str(repo))
        subprocess.run((*git, "init", "-q"), check=True, capture_output=True)

        def commit(message: str) -> None:
            subprocess.run((*git, "add", "-A"), check=True, capture_output=True)
            subprocess.run(
                (*git, "-c", "user.email=l@l", "-c", "user.name=l", "commit", "-q", "-m", message),
                check=True, capture_output=True,
            )

        commit("pristine — the floors this project committed to")
        spec_path = repo / "system.spec.json"
        pristine = json.loads(spec_path.read_text(encoding="utf-8"))
        target = next(c_ for c_ in pristine["containers"] if int(c_["depthFloor"]) > 0)
        was = int(target["depthFloor"])

        target["depthFloor"] = 0
        spec_path.write_text(json.dumps(pristine, indent=2), encoding="utf-8")
        commit("lower a floor, and commit it — the attack that defeated HEAD-based memory")

        report = c.build(repo, bm(repo))
        self.assertIn(
            "git history", str(report["ratchet_memory"]),
            "the ratchet reported no usable memory in a repository that has one",
        )
        self.assertTrue(
            any(target["id"] in f and "previously been committed" in f
                for f in report["floor_findings"]),
            f"lowering {target['id']} from {was} to 0 across a commit was not refused: "
            f"{report['floor_findings']}",
        )

    def test_floor_a_shallow_clone_reports_UNAVAILABLE_not_confident_memory(self) -> None:
        """`OG-218` — a shallow clone truncates history with NO rewrite, so the max-over-history the
        ratchet trusts is only a max-over-a-PREFIX and can sit below the true high-water mark. It must
        report the memory UNAVAILABLE, not confidently trust the truncated set. Off the local-hook
        path (a working clone is full) but newly reachable under CI's default `fetch-depth: 1`."""
        import tempfile

        from tools.blueprint import completeness as c
        from tools.blueprint.model import build_model as bm

        tmp = tempfile.TemporaryDirectory(prefix="ratchet-shallow-", ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        origin = Path(tmp.name) / "origin"
        shutil.copytree(self.lab, origin, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        git = ("git", "-C", str(origin))
        subprocess.run((*git, "init", "-q"), check=True, capture_output=True)

        def commit(msg: str, *extra: str) -> None:
            subprocess.run((*git, "add", "-A"), check=True, capture_output=True)
            subprocess.run(
                (*git, "-c", "user.email=l@l", "-c", "user.name=l", "commit", "-q", "-m", msg, *extra),
                check=True, capture_output=True,
            )

        commit("c1 — pristine")
        commit("c2 — a second commit, so depth 1 genuinely truncates", "--allow-empty")

        shallow = Path(tmp.name) / "shallow"
        clone = subprocess.run(
            ("git", "clone", "--depth", "1", "-q", f"file://{origin}", str(shallow)),
            capture_output=True, text=True, check=False,
        )
        if clone.returncode != 0:  # pragma: no cover - environment without file:// shallow support
            self.skipTest(f"could not create a shallow clone here: {clone.stderr.strip()}")
        is_shallow = subprocess.run(
            ("git", "-C", str(shallow), "rev-parse", "--is-shallow-repository"),
            capture_output=True, text=True, check=False,
        ).stdout.strip()
        self.assertEqual(is_shallow, "true", "the clone is not shallow; the guard cannot be exercised")

        hist, gap = c._historical_floors(shallow)
        self.assertIsNone(hist, "a shallow clone must not yield confident historical floors")
        self.assertIn("shallow", gap)
        report = c.build(shallow, bm(shallow))
        self.assertIn("UNAVAILABLE", str(report["ratchet_memory"]))

    def test_floor_a_raise_committed_in_an_EVIL_MERGE_is_remembered(self) -> None:
        """`OG-233` — a depthFloor committed uniquely in a MERGE commit's tree must not be forgotten.
        The round-2 `--diff-filter=ACMR` (added to tell a deletion from a missing object) DROPPED
        merge commits from the walk — a merge's default diff is empty — so a verifier lowered a
        floor-9-in-a-merge to 8 with `floor_findings == []` unseen. The fix walks `--full-history`
        with NO `--diff-filter` and uses `git ls-tree` for the deletion/missing distinction, so a
        merge's floor is read. On a synthetic repo, because the real spec history is linear."""
        import tempfile

        from tools.blueprint import completeness as c

        tmp = tempfile.TemporaryDirectory(prefix="ratchet-evilmerge-", ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name)

        def git(*a: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(("git", "-C", str(repo), *a), capture_output=True, text=True, check=False)

        def spec(floor: int) -> None:
            (repo / "system.spec.json").write_text(
                json.dumps({"containers": [{"id": "x", "depthFloor": floor}]}), encoding="utf-8")

        git("init", "-q")
        git("config", "user.email", "l@l"); git("config", "user.name", "l")
        git("config", "commit.gpgsign", "false")
        spec(5); git("add", "."); git("commit", "-q", "-m", "c1")
        base = git("symbolic-ref", "--short", "HEAD").stdout.strip()
        git("checkout", "-q", "-b", "br"); spec(6); git("add", "."); git("commit", "-q", "-m", "br6")
        git("checkout", "-q", base)
        # The evil merge: floor 9 committed IN the merge, present in neither parent's tree.
        git("merge", "--no-commit", "--no-ff", "br")
        spec(9); git("add", "system.spec.json"); git("commit", "-q", "-m", "evil merge floor 9")
        spec(8); git("add", "."); git("commit", "-q", "-m", "lower to 8")

        hist, gap = c._historical_floors(repo)
        self.assertEqual(gap, "", f"the whole history is present; memory must not be UNAVAILABLE: {gap!r}")
        self.assertEqual(
            (hist or {}).get("x"), 9,
            "the floor 9 committed in the evil merge was forgotten — a `--diff-filter` dropping the "
            "merge would report 8 and pass a real loosening (OG-233)",
        )

    def test_floor_a_replace_graft_relocated_by_GIT_REPLACE_REF_BASE_is_caught(self) -> None:
        """1.0.0 audit re-attack — the mirror of `OG-228`, one graft mechanism over. `git replace
        --graft` under the DEFAULT `refs/replace/` base was already detected; but git honours replace
        refs under a base named by `GIT_REPLACE_REF_BASE`, so a graft relocated there was ACTIVE for
        `git log` yet invisible to a literal `refs/replace` scan — `_historical_floors` returned a
        confident LOWERED max (a false green), while the sibling `info/grafts` mechanism already
        defended its own `GIT_GRAFT_FILE` env override. Falsified both ways: the relocated graft is
        caught (UNAVAILABLE, never a lowered max), and an unset base still trusts a clean history."""
        import os
        import tempfile

        from tools.blueprint import completeness as c

        tmp = tempfile.TemporaryDirectory(prefix="ratchet-replacebase-", ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name)

        def git(*a: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(("git", "-C", str(repo), *a), capture_output=True, text=True,
                                  check=False)

        def spec(floor: int) -> None:
            (repo / "system.spec.json").write_text(
                json.dumps({"containers": [{"id": "x", "depthFloor": floor}]}), encoding="utf-8")

        git("init", "-q")
        git("config", "user.email", "l@l"); git("config", "user.name", "l")
        git("config", "commit.gpgsign", "false")
        spec(9); git("add", "."); git("commit", "-q", "-m", "c1 floor 9")
        c1 = git("rev-parse", "HEAD").stdout.strip()
        spec(3); git("add", "."); git("commit", "-q", "-m", "c2 lower to 3")
        c2 = git("rev-parse", "HEAD").stdout.strip()

        # Baseline: the full linear history remembers the floor-9 raise.
        hist, _ = c._historical_floors(repo)
        self.assertEqual((hist or {}).get("x"), 9, "the linear history must remember floor 9")

        # Graft c2's parent away (hiding the floor-9 commit), then RELOCATE the replace ref off the
        # default base — git honours it via GIT_REPLACE_REF_BASE, the literal `refs/replace` scan does
        # not see it.
        git("replace", "--graft", c2)
        # Move refs/replace/<c2> -> refs/altbase/<c2>.
        ref = git("for-each-ref", "--format=%(refname)", "refs/replace").stdout.strip()
        self.assertTrue(ref, "the graft ref was not created under refs/replace")
        target = git("rev-parse", ref).stdout.strip()
        git("update-ref", f"refs/altbase/{c2}", target)
        git("update-ref", "-d", ref)

        env = dict(os.environ, GIT_REPLACE_REF_BASE="refs/altbase/")
        # Sanity: git DOES honour the relocated graft (log truncates to the grafted prefix).
        log = subprocess.run(
            ("git", "-C", str(repo), "log", "--format=%H"),
            capture_output=True, text=True, check=False, env=env,
        ).stdout.split()
        self.assertNotIn(c1, log, "git did not honour the relocated graft; the vector is not set up")

        prev = os.environ.get("GIT_REPLACE_REF_BASE")
        os.environ["GIT_REPLACE_REF_BASE"] = "refs/altbase/"
        try:
            hist2, gap2 = c._historical_floors(repo)
        finally:
            if prev is None:
                os.environ.pop("GIT_REPLACE_REF_BASE", None)
            else:
                os.environ["GIT_REPLACE_REF_BASE"] = prev
        self.assertIsNone(
            hist2,
            "a graft relocated via GIT_REPLACE_REF_BASE was trusted as confident memory — the "
            "false green the refs/replace guard exists to stop, one env-var relocation over",
        )
        self.assertIn("refs/replace", gap2)

    def test_floor_a_container_cannot_shed_its_floor_by_being_RENAMED(self) -> None:
        """Memory keyed on an id nothing requires to persist is memory with a rename bypass."""
        import tempfile

        from tools.blueprint import completeness as c
        from tools.blueprint.model import build_model as bm

        tmp = tempfile.TemporaryDirectory(prefix="ratchet-rename-", ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name) / "repo"
        shutil.copytree(self.lab, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        git = ("git", "-C", str(repo))
        subprocess.run((*git, "init", "-q"), check=True, capture_output=True)
        subprocess.run((*git, "add", "-A"), check=True, capture_output=True)
        subprocess.run(
            (*git, "-c", "user.email=l@l", "-c", "user.name=l", "commit", "-q", "-m", "pristine"),
            check=True, capture_output=True,
        )
        spec_path = repo / "system.spec.json"
        doc = json.loads(spec_path.read_text(encoding="utf-8"))
        victim = next(c_ for c_ in doc["containers"] if int(c_["depthFloor"]) > 0)
        old_id = victim["id"]
        victim["id"] = f"{old_id}-v2"
        spec_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

        report = c.build(repo, bm(repo))
        self.assertTrue(
            any(old_id in f and "no longer exists" in f for f in report["floor_findings"]),
            f"renaming {old_id} shed its remembered floor silently: {report['floor_findings']}",
        )

    def test_floor_the_command_exits_1_on_a_finding_and_0_when_restored(self) -> None:
        """End to end through the real command, both directions, in one test."""
        def run() -> int:
            return subprocess.run(
                (sys.executable, "-m", "tools.blueprint", "completeness", "--check"),
                cwd=self.lab, capture_output=True, text=True, timeout=600,
                env={**_env(), "ENGINE_HOST_ROOT": str(self.lab)}, check=False,
            ).returncode

        original = (self.lab / "system.spec.json").read_text(encoding="utf-8")
        self.addCleanup(
            lambda: (self.lab / "system.spec.json").write_text(original, encoding="utf-8")
        )
        self.assertEqual(run(), 0, "the lab must be level before it is broken")
        doc = self.spec()
        doc["containers"][0]["depthFloor"] = doc["containers"][0]["depthFloor"] + 5
        self.write_spec(doc)
        self.assertEqual(run(), 1, "a container below its floor must fail the command")
        (self.lab / "system.spec.json").write_text(original, encoding="utf-8")
        self.assertEqual(run(), 0, "the command must return to 0 once the floor is restored")


class TheAuthoringContractMatchesWhatTheCodeEnforces(unittest.TestCase):
    """A-6 — a procedure that claims a gate nobody runs is the defect, one document over."""

    def test_lifecycle_steps_in_the_contract_match_the_code(self) -> None:
        contract = (_ROOT / "docs/process/AUTHORING_CONTRACT.md").read_text(encoding="utf-8")
        skill = (_ROOT / "skills/doc-lifecycle/SKILL.md").read_text(encoding="utf-8")
        for step in comp.LIFECYCLE_STEPS:
            self.assertIn(
                f"**{step}**", contract, f"the contract does not name the `{step}` step"
            )
            self.assertIn(step, skill, f"the skill does not name the `{step}` step")

    def test_completeness_every_enforcer_the_contract_credits_really_exists(self) -> None:
        """Every GUARD and every GATE the contract credits must be in the live registries.

        The first version regexed only `` `x` guard `` and validated **2 of about 7** enforcement
        claims. A verifier replaced the gate names with `flying_pony` and `imaginary_drift` — keeping
        real file paths and real check ids, so the other guards stayed quiet — and the whole corpus
        check plus this probe came back clean. Gate names were the hole; both universes are checked
        now, and both are imported rather than listed.
        """
        from tools.corpus_check.guards import guard_names
        from tools.docgen.export_sanitizer import PRECEDENCE

        contract = (_ROOT / "docs/process/AUTHORING_CONTRACT.md").read_text(encoding="utf-8")
        registered_guards = set(guard_names())
        registered_gates = set(PRECEDENCE)

        cited_guards = set(re.findall(r"`([a-z][a-z_-]+)`(?= corpus guard| and `)", contract))
        cited_guards |= set(re.findall(r"`([a-z][a-z_-]+)` guard", contract))
        cited_gates = set(re.findall(r"`([a-z][a-z_.-]+)` gate", contract))

        self.assertTrue(cited_guards or cited_gates, "the contract credits nothing — it claims nothing")
        unknown_guards = {g for g in cited_guards if g not in registered_guards | registered_gates}
        unknown_gates = {g for g in cited_gates if g not in registered_gates | registered_guards}
        self.assertEqual(
            unknown_guards | unknown_gates, set(),
            "the contract credits enforcers that are in no registry: "
            f"{sorted(unknown_guards | unknown_gates)}",
        )


class VerifiedIsReachableOnTheCommittedTree(unittest.TestCase):
    """`BUILD_PLAN.md` Phase-7 **A-5** — `verified` is non-zero on the tree AS COMMITTED, and it is a
    CONSEQUENCE, falsified both ways: removing the owning document's verified claim, OR its stamp,
    drops the count back to `0`.

    The lab probes above prove `verified` is reachable IN PRINCIPLE by constructing the condition in
    a synthetic tree. This one is the acceptance line: it asserts the state is reached IN FACT on the
    real committed corpus — the deliverable of `OG-207` — and then proves the number is earned rather
    than pinned, by taking away each thing that earns it and watching it fall to zero.

    Selected by ``-k verified_reachable`` (the token names the method, not a lab fixture).
    """

    def _verified(self, root: Path) -> list[str]:
        nodes = build_model(root)["completeness"]["nodes"]
        return sorted(m for m, r in nodes.items() if r["state"] == comp.VERIFIED)

    def _owning_documents(self, root: Path, verified_ids: list[str]) -> set[str]:
        model = build_model(root)
        owner = model["ownership"]["owner"]
        containers = {c["id"]: c for c in model["containers"]}
        docs: set[str] = set()
        for module_id in verified_ids:
            container = containers.get(owner.get(module_id, ""))
            if container and container.get("document"):
                docs.add(container["document"])
        return docs

    def _faithful_clone(self) -> Path:
        """A ``git clone`` — NOT the fresh-init lab — so the committed history travels with the copy.

        A hardening stamp certifies a body at a specific commit; the completeness model only calls a
        node `verified` when that commit is reachable and the body still matches. `build_lab` does a
        fresh ``git init``, so the stamped commit would be absent and `verified` would read `0` before
        any mutation — passing the negative controls below for the wrong reason. A clone carries the
        real history, so the stamp resolves exactly as it does on the tree under test. The working
        tree is clean at close, so the clone equals the committed state.
        """
        tmp = tempfile.mkdtemp(prefix="a5-verified-reachable-")
        self.addCleanup(force_rmtree, Path(tmp))
        dest = Path(tmp) / "repo"
        subprocess.run(
            ("git", "clone", "--quiet", "--no-hardlinks", str(_ROOT), str(dest)),
            check=True, capture_output=True, text=True, timeout=180,
        )
        return dest

    def test_verified_reachable_and_proven_a_consequence(self) -> None:
        # Positive: the LIVE committed tree, read through the same model the real commands use.
        live = self._verified(_ROOT)
        self.assertGreaterEqual(
            len(live), 1,
            "verified is 0 on the committed tree — OG-207's consequence is not present as committed",
        )
        docs = self._owning_documents(_ROOT, live)
        self.assertTrue(docs, f"the {len(live)} verified node(s) resolve to no owning document")

        clone = self._faithful_clone()
        self.assertEqual(
            self._verified(clone), live,
            "the faithful clone did not reproduce the committed verified set — not a valid baseline",
        )
        originals = {rel: (clone / rel).read_text(encoding="utf-8") for rel in docs}

        # (a) Remove the verified CLAIM from every owning document -> the count must fall to 0.
        for rel, text in originals.items():
            (clone / rel).write_text(
                re.sub(r"(?m)^verified_state:.*\n", "", text), encoding="utf-8"
            )
        self.assertEqual(
            self._verified(clone), [],
            "removing the verified claim from the owning document(s) did NOT drop verified to 0",
        )
        for rel, text in originals.items():
            (clone / rel).write_text(text, encoding="utf-8")
        self.assertEqual(
            self._verified(clone), live, "restoring the claim did not return the baseline"
        )

        # (b) Remove the STAMP line from every owning document -> the count must fall to 0.
        for rel, text in originals.items():
            (clone / rel).write_text(
                re.sub(r"(?m)^<!-- artifact-hardened:.*-->[ \t]*\n", "", text), encoding="utf-8"
            )
        self.assertEqual(
            self._verified(clone), [],
            "removing the hardening stamp from the owning document(s) did NOT drop verified to 0",
        )


if __name__ == "__main__":
    unittest.main()
