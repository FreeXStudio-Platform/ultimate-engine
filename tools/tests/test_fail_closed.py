"""Counter-examples for behaviour under corrupt, missing and hostile inputs.

Each mutation below was applied by an adversarial verifier and produced either a silent wrong
answer, a data loss, or an unhandled traceback. "Fails closed" is a claim, and a claim needs the
input that would falsify it.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.docgen import doc_manifest, export_sanitizer
from tools.docgen.models import DocHeader, Surface, Tier


class ManifestReaderDegrades(unittest.TestCase):
    """``read_manifest`` had NO try block at all, so an unreadable manifest raised straight through
    eight callers — two of them health checks, one of them ``generator.build``."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_absent_manifest_returns_empty(self) -> None:
        self.assertEqual(doc_manifest.read_manifest(self.dir / "nope.md"), [])

    def test_non_utf8_manifest_returns_empty_rather_than_raising(self) -> None:
        bad = self.dir / "DOC_MANIFEST.md"
        bad.write_bytes(b"x \xff\xfe y\n")
        self.assertEqual(doc_manifest.read_manifest(bad), [])

    def test_a_directory_where_a_file_is_expected_returns_empty(self) -> None:
        d = self.dir / "DOC_MANIFEST.md"
        d.mkdir()
        self.assertEqual(doc_manifest.read_manifest(d), [])


class ProjectIndexRefusesToOverwriteWhatItCannotRead(unittest.TestCase):
    """The quiet path was DATA LOSS: an unparseable index degraded to ``{"artifacts": []}`` and the
    next save wrote that empty list back over the file. Every registered artifact destroyed, exit
    code 0, nothing printed. Absent and unparseable are different questions and only one of them has
    a safe default."""

    def test_unreadable_index_raises_on_the_write_path(self) -> None:
        from tools.docgen import artifact_index as pindex

        with tempfile.TemporaryDirectory() as td:
            broken = Path(td) / "PROJECT_INDEX.json"
            broken.write_text('{"artifacts": [{"id": "keep-me"}\n', encoding="utf-8")
            before = broken.read_bytes()
            original = pindex._index_path
            pindex._index_path = lambda: broken
            self.addCleanup(setattr, pindex, "_index_path", original)

            with self.assertRaises(pindex.IndexUnreadable):
                pindex._load(for_write=True)
            self.assertEqual(broken.read_bytes(), before, "the file must not have been touched")

    def test_unreadable_index_degrades_quietly_on_the_read_path(self) -> None:
        """Readers that only list may safely see an empty index; only WRITERS must refuse."""
        from tools.docgen import artifact_index as pindex

        with tempfile.TemporaryDirectory() as td:
            broken = Path(td) / "PROJECT_INDEX.json"
            broken.write_text("{not json", encoding="utf-8")
            original = pindex._index_path
            pindex._index_path = lambda: broken
            self.addCleanup(setattr, pindex, "_index_path", original)
            self.assertEqual(pindex._load().get("artifacts"), [])


class EngineConfigSurvivesBadBytes(unittest.TestCase):
    """``UnicodeDecodeError`` is a ``ValueError`` and is NOT a ``JSONDecodeError``, so the narrower
    tuple let one bad byte in ``engine.config.json`` kill every entry point at import time."""

    def test_non_utf8_config_degrades_to_defaults(self) -> None:
        import os

        from tools.docgen import engine_config

        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "engine.config.json"
            bad.write_bytes(b'{"a": "\xff\xfe"}')
            prev = os.environ.get("ENGINE_CONFIG_PATH")
            os.environ["ENGINE_CONFIG_PATH"] = str(bad)
            engine_config._raw_config.cache_clear()
            try:
                self.assertEqual(engine_config._raw_config(), {})
            finally:
                if prev is None:
                    os.environ.pop("ENGINE_CONFIG_PATH", None)
                else:
                    os.environ["ENGINE_CONFIG_PATH"] = prev
                engine_config._raw_config.cache_clear()

class Gate9VariantOverlapIsProven(unittest.TestCase):
    """`OG-93` — Gate 9 (`variant_overlap`), the L18 cross-tier moat, had **no** counter-example.

    **What a Pass-6 analyzer reported, and what is actually true.** The finding said the gate "can
    never pass in the build path" and had zero test coverage. The second half was right; the first
    was overstated, and re-deriving it from the artifact rather than accepting it is the whole point
    of the separation-of-duties law. `run_gates` *does* reach the gate on every export — via the
    sibling-aware `_variant_overlap_against`, not via the public `gate_variant_overlap` overload
    whose docstring says it has no internal caller.

    **What IS true, and is now recorded rather than implied:** `generator.build` never passes
    `siblings=`, so the gate always receives `None`. Its fail-closed half therefore does all the
    work in production, and the overlap comparison itself is reachable only by a caller that
    supplies sibling text. In this repository no governed document declares `variants`, so the gate
    correctly has nothing to compare — that is a true no-op, not a broken gate.

    Three cases, two-sided, because the fail-closed contract is the half that runs.
    """

    @staticmethod
    def _header(variants: list[str]) -> DocHeader:
        return DocHeader(
            id="REF-1",
            title="t",
            classification=Tier.PUBLIC,
            surface=Surface.WEB,
            audience="technical",
            owner="o",
            status="draft",
            export_allowed=True,
            last_reviewed="2026-08-22",
            variants=variants,
        )

    def test_no_variants_declared_is_a_true_no_op(self) -> None:
        """The accepts-clean half. Without this, "it blocks" would pass for a gate that blocks all."""
        result = export_sanitizer.gate_variant_overlap(self._header([]), None)
        self.assertTrue(result.ok, "a document declaring no variants has nothing to compare")

    def test_declared_variants_with_no_sibling_text_fails_CLOSED(self) -> None:
        """The half that actually runs in production, since no caller supplies siblings.

        A missing sibling must never read as "no overlap" — a git-ignored CONFIDENTIAL sibling that
        happens not to be checked out would otherwise let a converged document through.
        """
        result = export_sanitizer.gate_variant_overlap(self._header(["SPEC-9"]), None)
        self.assertFalse(result.ok, "a declared sibling with no text must fail closed")
        self.assertTrue(any(f.blocking for f in result.findings))
        self.assertIn("failing closed", " ".join(f.message for f in result.findings))

    def test_a_real_cross_tier_overlap_is_refused(self) -> None:
        """The moat itself: shared content between a public document and its sibling."""
        body = (
            "The quick brown fox jumps over the lazy dog and then writes a great deal of "
            "documentation about it all day long."
        )
        result = export_sanitizer._variant_overlap_against(body, self._header(["SPEC-9"]), [body])
        self.assertFalse(result.ok, "identical sibling content is a cross-tier leak")
        self.assertIn("variant-overlap", " ".join(f.message for f in result.findings))

    def test_gate_9_fires_through_run_gates_the_PRODUCTION_path(self) -> None:
        """**Through `run_gates`, not the helper** — the probes above call the gate directly.

        A gate proven only through its own function is proven in isolation from the thing that
        decides whether it runs at all. `OG-93`'s original finding was precisely the claim that
        Gate 9 "cannot fire in the build path"; re-deriving it showed `run_gates` does reach it via
        `_variant_overlap_against` on every export. That re-derivation belongs in a retained
        counter-example, not only in a register row, so this asserts the wiring itself: a declared
        variant with no sibling text must produce a BLOCKING finding from the merged, adjudicated
        result an exporter actually consumes.
        """
        result = export_sanitizer.run_gates(
            "Ordinary public body text.", self._header(["SPEC-9"]), siblings=None
        )
        self.assertFalse(result.ok, "run_gates passed a document Gate 9 must block")
        self.assertTrue(
            any(f.blocking for f in result.findings),
            "the merged result carries no blocking finding",
        )

    def test_run_gates_does_not_fire_GATE_9_when_no_variant_is_declared(self) -> None:
        """Two-sided control for the probe above: a gate that blocked everything would satisfy it.

        Scoped to Gate 9's own finding rather than to `result.ok`, because `run_gates` merges seven
        gates and Gate 5 independently fails closed when no `DOC_MANIFEST` rows are supplied — a
        correct refusal that has nothing to do with variant overlap. Asserting `ok` here would tie
        this probe to another gate's preconditions and make it fail for a reason it does not test.
        """
        result = export_sanitizer.run_gates(
            "Ordinary public body text.", self._header([]), siblings=None
        )
        overlap = [
            f for f in result.findings
            if f.blocking and ("variant" in f.message.lower() or "overlap" in f.message.lower())
        ]
        self.assertEqual(
            overlap, [], f"Gate 9 fired with no variants declared: {[f.message for f in overlap]}"
        )

    def test_distinct_sibling_content_is_accepted(self) -> None:
        """The other side of the moat — otherwise "it blocks" proves nothing."""
        result = export_sanitizer._variant_overlap_against(
            "Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi.",
            self._header(["SPEC-9"]),
            ["Wholly unrelated prose about shipping schedules, invoices, and quarterly forecasts."],
        )
        self.assertTrue(result.ok, f"distinct content must pass: {[f.message for f in result.findings]}")

if __name__ == "__main__":  # pragma: no cover
    unittest.main()
