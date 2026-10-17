"""Counter-examples for the audience-view generator (``tools.docgen.views``).

Every case here is a defect that would be measurable if the generator regressed, not a
hypothetical -- see ``docs/process/RULES.md`` Rule 1 / this repo's own testing culture
(``tools/tests/test_docgen.py``'s module docstring). In particular
``GeneratedViewsGate9FalsificationCase`` is the single most important case in this file:
a gate that has never been SEEN to fail has not been shown to work, so it
is not enough to show gate 9 passes on a clean view -- it must also be shown to BLOCK a
leaked one.

**Imports ``tools.docgen.artifact_index`` directly, not the ``tools.project_index.index`` shim
(2026-09-24).** ``views._load_project_index()`` now imports ``tools.docgen.artifact_index``
(see that function's docstring for why), and this file's ``_IsolatedProjectIndexCase`` patches
the private ``_index_path`` and expects ``views.py``'s OWN calls into the registry to see the
patch -- which only works when the patch target is the module the registry functions were
actually defined in, since Python resolves a function's globals against its own ``__globals__``,
never the importer's alias. ``ViewsRegisterDespiteAnUnrelatedHostProjectIndexPackage`` below is
the counter-example that PROVES the fix: it shadows ``tools.project_index`` itself (the OLD
failure trigger) and shows a view registers anyway.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import unittest
import unittest.mock
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import ClassVar

from tools.docgen import artifact_index as project_index
from tools.docgen import doc_manifest, engine_config, export_sanitizer, generator, views
from tools.docgen.classification import parse_header
from tools.docgen.models import (
    Finding,
    GateResult,
    ManifestRow,
    Severity,
    Surface,
    Tier,
)

_REPO = Path(__file__).resolve().parents[2]

# A document exercising all four audience levels plus unmarked (default-inheriting) content,
# front and back. Ordering matters for the tests below: unmarked-public, github, commercial,
# internal, unmarked-public -- five segments, so the public view excludes 3 blocks, github
# excludes 2, commercial excludes 1, internal excludes 0 (it is the superset).
_FIX_ID = "VIEWFIX-001"
_INTERNAL_PHRASE = "INTERNAL-ONLY-ROADMAP-PHRASE-YAK-7734"
_GITHUB_PHRASE = "GITHUB-TIER-CONTRIBUTOR-NOTE-4471"
_COMMERCIAL_PHRASE = "COMMERCIAL-TIER-PARTNER-NOTE-8802"
_PUBLIC_INTRO_PHRASE = "Public intro paragraph visible to every reader."
_PUBLIC_TRAILING_PHRASE = "Public trailing paragraph, unmarked, inherits the document default."

_FIXTURE_ALL_FOUR = f"""---
id: {_FIX_ID}
classification: public
title: Audience View Fixture
surface: web
audience: technical
owner: doc-system
status: draft
export_allowed: true
last_reviewed: 2026-09-08
default_audience: public
---

# Audience View Fixture

{_PUBLIC_INTRO_PHRASE}

<!-- audience: github -->
{_GITHUB_PHRASE}
<!-- /audience -->

<!-- audience: commercial -->
{_COMMERCIAL_PHRASE}
<!-- /audience -->

<!-- audience: internal -->
{_INTERNAL_PHRASE}
<!-- /audience -->

{_PUBLIC_TRAILING_PHRASE}
"""

_FIXTURE_NO_DEFAULT = """---
id: NODEF-001
classification: public
title: Missing Default
surface: web
audience: technical
owner: doc-system
status: draft
export_allowed: true
last_reviewed: 2026-09-08
---

Unmarked lead-in.

<!-- audience: internal -->
secret block
<!-- /audience -->
"""

# --- fence-aware fixture: a document with a REAL marker AND a fenced-code-block example
# illustrating the marker syntax (the exact shape the engine's own docs use). Fixed
# behaviour: the fenced pair is inert text, so `parse_body_segments` sees 3 segments
# (intro / real-internal / everything-after-including-the-fence). A fence-blind
# tokenizer instead sees 5, splitting the illustrated example out as a fourth (fake)
# marked segment and stripping it from every non-internal view.
_FENCE_FIX_ID = "FENCETEST-001"
_FENCE_INTRO_PHRASE = "Public intro before the example, fence test."
_FENCE_REAL_INTERNAL_PHRASE = "REAL-INTERNAL-SECRET-PHRASE-FENCETEST-2233"
_FENCE_EXAMPLE_PHRASE = "EXAMPLE-CONTENT-PHRASE-FENCETEST-9911"
_FENCE_TRAILING_PHRASE = "Public trailing paragraph after the example, fence test."

_FIXTURE_FENCED_MARKER_EXAMPLE = f"""---
id: {_FENCE_FIX_ID}
classification: public
title: Fence Marker Test
surface: web
audience: technical
owner: doc-system
status: draft
export_allowed: true
last_reviewed: 2026-09-08
default_audience: public
---

# Fence Marker Test

{_FENCE_INTRO_PHRASE}

<!-- audience: internal -->
{_FENCE_REAL_INTERNAL_PHRASE}
<!-- /audience -->

Here is how audience markers work, illustrated inline:

```text
<!-- audience: internal -->
{_FENCE_EXAMPLE_PHRASE}
<!-- /audience -->
```

{_FENCE_TRAILING_PHRASE}
"""

# --- shingle-floor fixture: only needed to obtain a valid, parsed `DocHeader` via
# `parse_header` -- the actual gate-9 comparison in that test is driven directly
# against `export_sanitizer.run_gates`, never through the view generator, so the body
# text below is a placeholder.
_SHINGLE_FLOOR_FIX_ID = "SHINGLEFLOOR-001"
_FIXTURE_FOR_SHINGLE_FLOOR_TEST = f"""---
id: {_SHINGLE_FLOOR_FIX_ID}
classification: public
title: Shingle Floor Test
surface: web
audience: technical
owner: doc-system
status: draft
export_allowed: true
last_reviewed: 2026-09-08
---

Placeholder body -- unused by the test that parses this fixture.
"""

# 6 raw words, 3 CONTENT tokens after `_normalize_for_shingle` strips "this"/"is"/"a" --
# reproduces the measured example exactly (a short excluded block whose content
# token count falls below the n=4 shingle floor, so it produces zero shingles at every n
# `_variant_overlap_against` checks, no matter how verbatim it leaks).
_SHORT_LEAK_PHRASE = "This is a launch date confirmation"


def _manifest_row_for(doc_id: str) -> ManifestRow:
    """A ``ManifestRow`` that satisfies ``classification.check_manifest_drift`` for
    ``doc_id``. That check keys rows by DOC-TYPE PREFIX (e.g. ``VIEWFIX``), not by the
    full instance id (``VIEWFIX-001``) -- ``row.id == _extract_prefix(header.id)`` is
    the actual comparison, so the row below must carry the prefix alone."""
    prefix = doc_id.rsplit("-", 1)[0]
    return ManifestRow(
        id=prefix,
        title="fixture",
        type="article",
        variants=[Tier.PUBLIC],
        content_role="project-doc",
        surface=Surface.WEB,
        status="draft",
    )



# --- code-span fixture: identical to a clean document except for ONE line that is a CommonMark
# CODE SPAN (```x```), which a backtick fence's info-string rule forbids from opening a
# fence. Read as a fence-open it never closed, so the range ran to EOF, the REAL marker
# below it was never seen, and `build_and_gate_views` returned ok having written NO views.
_SPAN_FIX_ID = "CODESPAN-001"
_SPAN_INTERNAL_PHRASE = "REAL-INTERNAL-PHRASE-CODESPAN-7788"
_SPAN_PUBLIC_PHRASE = "Public trailing paragraph after the code span."

_FIXTURE_CODE_SPAN_LINE = f"""---
id: {_SPAN_FIX_ID}
classification: public
title: Code Span Test
surface: web
audience: technical
owner: doc-system
status: draft
export_allowed: true
last_reviewed: 2026-09-08
default_audience: public
---

# Code Span Test

```x```

<!-- audience: internal -->
{_SPAN_INTERNAL_PHRASE}
<!-- /audience -->

{_SPAN_PUBLIC_PHRASE}
"""

class _IsolatedProjectIndexCase(unittest.TestCase):
    """Base case: an isolated ``PROJECT_INDEX.json`` + a scratch ``out_directory`` under
    ``$TMPDIR``, so no test in this file can ever read or write the REAL repository index
    (same isolation pattern as ``tools/tests/test_project_index.py``'s ``ProjectIndexGateCase``)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out_dir = self.root / "out"
        self.out_dir.mkdir()
        self.index_file = self.root / "PROJECT_INDEX.json"
        patcher = unittest.mock.patch.object(project_index, "_index_path", lambda: self.index_file)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _build_views(self, md_text: str, **kwargs: object) -> views.ViewsBuildResult:
        header = parse_header(md_text)
        defaults: dict[str, object] = {
            "source_stem": header.id,
            "md_text": md_text,
            "header": header,
            "out_directory": self.out_dir,
            "manifest_rows": [_manifest_row_for(header.id)],
            "local_preview": False,
            "may_write": True,
        }
        defaults.update(kwargs)
        return views.build_and_gate_views(**defaults)  # type: ignore[arg-type]


class FourAudienceSplitAndPermissionRule(_IsolatedProjectIndexCase):
    """The core generator behaviour: one source, four views, each containing exactly the
    blocks its audience permits (the views registry's stated permission rule)."""

    def test_each_view_contains_exactly_the_permitted_phrases(self) -> None:
        result = self._build_views(_FIXTURE_ALL_FOUR)
        self.assertTrue(result.gate.ok, [f.message for f in result.gate.findings])
        self.assertEqual(
            set(result.outputs), {"view:public", "view:github", "view:commercial", "view:internal"}
        )

        expectations = {
            "public": {_PUBLIC_INTRO_PHRASE, _PUBLIC_TRAILING_PHRASE},
            "github": {_PUBLIC_INTRO_PHRASE, _GITHUB_PHRASE, _PUBLIC_TRAILING_PHRASE},
            "commercial": {
                _PUBLIC_INTRO_PHRASE, _GITHUB_PHRASE, _COMMERCIAL_PHRASE, _PUBLIC_TRAILING_PHRASE
            },
            "internal": {
                _PUBLIC_INTRO_PHRASE, _GITHUB_PHRASE, _COMMERCIAL_PHRASE,
                _INTERNAL_PHRASE, _PUBLIC_TRAILING_PHRASE,
            },
        }
        all_phrases = {
            _PUBLIC_INTRO_PHRASE, _GITHUB_PHRASE, _COMMERCIAL_PHRASE,
            _INTERNAL_PHRASE, _PUBLIC_TRAILING_PHRASE,
        }
        for audience, expected_present in expectations.items():
            text = self.out_dir.joinpath(f"{_FIX_ID}.{audience}.md").read_text(encoding="utf-8")
            for phrase in expected_present:
                self.assertIn(phrase, text, f"{audience} view is missing a permitted phrase")
            for phrase in all_phrases - expected_present:
                self.assertNotIn(phrase, text, f"{audience} view LEAKED an excluded phrase")

        # Exclusion counts follow the same ordering: internal is the superset (excludes
        # nothing), public excludes the most (github/commercial/internal blocks = 3).
        header = parse_header(_FIXTURE_ALL_FOUR)
        body = views._strip_body(_FIXTURE_ALL_FOUR)
        segments = views.parse_body_segments(body, default_audience="public", doc_id=header.id)
        _, excl_public = views.render_view(segments, "public")
        _, excl_github = views.render_view(segments, "github")
        _, excl_commercial = views.render_view(segments, "commercial")
        _, excl_internal = views.render_view(segments, "internal")
        self.assertEqual(len(excl_public), 3)
        self.assertEqual(len(excl_github), 2)
        self.assertEqual(len(excl_commercial), 1)
        self.assertEqual(len(excl_internal), 0)


class UnmarkedContentInheritsDefaultAudience(_IsolatedProjectIndexCase):
    def test_unmarked_content_takes_the_declared_default(self) -> None:
        md = _FIXTURE_ALL_FOUR.replace("default_audience: public", "default_audience: commercial")
        header = parse_header(md)
        body = views._strip_body(md)
        segments = views.parse_body_segments(body, default_audience="commercial", doc_id=header.id)
        _, excl_public = views.render_view(segments, "public")
        # The two unmarked segments now require 'commercial' -- so the PUBLIC view excludes
        # them too, on top of github/commercial/internal: all 5 segments are excluded from
        # 'public', and only 'internal' still sees everything.
        self.assertEqual(len(excl_public), 5)
        view_text, _ = views.render_view(segments, "commercial")
        self.assertIn(_PUBLIC_INTRO_PHRASE, view_text)
        self.assertIn(_PUBLIC_TRAILING_PHRASE, view_text)
        view_text_public, _ = views.render_view(segments, "public")
        self.assertEqual(view_text_public, "")


class MissingDefaultAudienceFailsClosed(unittest.TestCase):
    def test_marked_blocks_with_no_declared_default_raises_at_both_layers(self) -> None:
        header = parse_header(_FIXTURE_NO_DEFAULT)
        body = views._strip_body(_FIXTURE_NO_DEFAULT)
        with self.assertRaises(views.AudienceMarkerError) as ctx:
            views.parse_body_segments(body, default_audience=None, doc_id=header.id)
        self.assertIn(header.id, str(ctx.exception))
        self.assertIn("default_audience", str(ctx.exception))

        # The same failure must surface through the top-level orchestration seam too, not
        # just the lower-level parser -- ``generator.build()`` only ever calls the former.
        with (
            tempfile.TemporaryDirectory() as tmp,
            self.assertRaises(views.AudienceMarkerError),
        ):
                views.build_and_gate_views(
                    source_stem="NODEF-001",
                    md_text=_FIXTURE_NO_DEFAULT,
                    header=header,
                    out_directory=Path(tmp),
                    manifest_rows=[_manifest_row_for("NODEF-001")],
                )


class MalformedMarkersFailClosed(unittest.TestCase):
    """Unclosed / stray-close / unknown-audience / nested markers -- never 'best effort'."""

    def test_unclosed_marker_raises(self) -> None:
        body = "lead-in\n<!-- audience: internal -->\nnever closed\n"
        with self.assertRaises(views.AudienceMarkerError) as ctx:
            views.parse_body_segments(body, default_audience="public", doc_id="X-1")
        self.assertIn("unclosed", str(ctx.exception).lower())

        # A stray close with no matching open is the mirror-image malformation.
        stray_body = "lead-in\n<!-- /audience -->\ntrailing\n"
        with self.assertRaises(views.AudienceMarkerError) as ctx2:
            views.parse_body_segments(stray_body, default_audience="public", doc_id="X-2")
        self.assertIn("no matching open", str(ctx2.exception))

    def test_unknown_audience_name_raises(self) -> None:
        body = "<!-- audience: bogus -->\ntext\n<!-- /audience -->\n"
        with self.assertRaises(views.AudienceMarkerError) as ctx:
            views.parse_body_segments(body, default_audience="public", doc_id="X-3")
        self.assertIn("unknown audience", str(ctx.exception).lower())

    def test_nested_markers_raise(self) -> None:
        body = (
            "<!-- audience: internal -->\nouter\n"
            "<!-- audience: public -->\ninner\n<!-- /audience -->\n"
            "<!-- /audience -->\n"
        )
        with self.assertRaises(views.AudienceMarkerError) as ctx:
            views.parse_body_segments(body, default_audience="public", doc_id="X-4")
        self.assertIn("nested", str(ctx.exception).lower())


class DeterminismAcrossBuilds(_IsolatedProjectIndexCase):
    def test_two_builds_from_a_clean_tree_are_byte_identical(self) -> None:
        first_out = self.out_dir / "run1"
        second_out = self.out_dir / "run2"
        first_out.mkdir(parents=True, exist_ok=True)
        second_out.mkdir(parents=True, exist_ok=True)
        header = parse_header(_FIXTURE_ALL_FOUR)
        rows = [_manifest_row_for(header.id)]
        r1 = views.build_and_gate_views(
            source_stem=header.id, md_text=_FIXTURE_ALL_FOUR, header=header,
            out_directory=first_out, manifest_rows=rows,
        )
        r2 = views.build_and_gate_views(
            source_stem=header.id, md_text=_FIXTURE_ALL_FOUR, header=header,
            out_directory=second_out, manifest_rows=rows,
        )
        self.assertTrue(r1.gate.ok and r2.gate.ok)
        self.assertEqual(set(r1.outputs), set(r2.outputs))
        for key in r1.outputs:
            b1 = r1.outputs[key].read_bytes()
            b2 = r2.outputs[key].read_bytes()
            self.assertEqual(
                hashlib.sha256(b1).hexdigest(), hashlib.sha256(b2).hexdigest(),
                f"{key} differs across two builds of the same source",
            )
            self.assertEqual(b1, b2)


class Gate9IsArmedAndPassesOnACleanView(_IsolatedProjectIndexCase):
    def test_variants_are_armed_and_gate9_runs_clean_on_every_view(self) -> None:
        header = parse_header(_FIXTURE_ALL_FOUR)
        body = views._strip_body(_FIXTURE_ALL_FOUR)
        segments = views.parse_body_segments(body, default_audience="public", doc_id=header.id)
        _, excluded = views.render_view(segments, "public")
        view_header = views.build_view_header(header, excluded)
        self.assertEqual(len(view_header.variants), len(excluded))
        self.assertEqual(len(view_header.variants), 3)  # public excludes github/commercial/internal

        result = self._build_views(_FIXTURE_ALL_FOUR)
        self.assertTrue(result.gate.ok)
        # The strongest available assertion that gate 9 ran CLEAN rather than merely "not
        # present": zero variant_overlap findings among whatever findings DID come back.
        overlap_findings = [f for f in result.gate.findings if f.gate == "variant_overlap"]
        self.assertEqual(overlap_findings, [])


class GeneratedViewsGate9FalsificationCase(unittest.TestCase):
    """THE most important case in this file (a gate never seen to fail has
    not been shown to work). Simulates the realistic failure class gate 9 exists to catch --
    the WRITE path emitting text that does not match the correctly-computed excluded set
    (e.g. a future 'forgot to use the filtered variable' regression) -- entirely in memory,
    no file or git mutation of any kind."""

    def test_gate9_blocks_when_rendered_text_contains_an_excluded_block(self) -> None:
        header = parse_header(_FIXTURE_ALL_FOUR)
        body = views._strip_body(_FIXTURE_ALL_FOUR)
        segments = views.parse_body_segments(body, default_audience="public", doc_id=header.id)
        clean_text, excluded = views.render_view(segments, "public")
        view_header = views.build_view_header(header, excluded)
        rows = [_manifest_row_for(header.id)]

        clean_gate = export_sanitizer.run_gates(
            clean_text, view_header, siblings=excluded, manifest_rows=rows
        )
        self.assertTrue(clean_gate.ok, [f.message for f in clean_gate.findings])

        # The falsification: the INTERNAL block's text (siblings[-1], correctly identified as
        # excluded) ends up in the rendered text anyway -- the shape of bug that a broken
        # write path (not a broken filter) would produce.
        self.assertIn(_INTERNAL_PHRASE, excluded[-1])
        leaked_text = clean_text + "\n" + excluded[-1]
        leaked_gate = export_sanitizer.run_gates(
            leaked_text, view_header, siblings=excluded, manifest_rows=rows
        )
        self.assertFalse(leaked_gate.ok, "gate 9 failed to catch a real, injected leak")
        leak_findings = [f for f in leaked_gate.findings if f.gate == "variant_overlap"]
        self.assertTrue(leak_findings, "no variant_overlap finding was raised for the leak")
        self.assertTrue(all(f.blocking for f in leak_findings))


class NoMarkersDocumentIsUnaffected(_IsolatedProjectIndexCase):
    """The purely-additive guarantee, at both layers: ``views.py`` alone, and wired through
    the real ``generator.build()`` seam."""

    def test_has_audience_markers_is_false_and_build_and_gate_views_is_a_clean_noop(self) -> None:
        md = _FIXTURE_ALL_FOUR
        for marker in ("<!-- audience:", "<!-- /audience -->"):
            self.assertIn(marker, md)  # sanity on the OTHER fixture, not this one
        no_markers_md = (
            "---\nid: PLAIN-001\nclassification: public\ntitle: Plain\nsurface: web\n"
            "audience: technical\nowner: doc-system\nstatus: draft\nexport_allowed: true\n"
            "last_reviewed: 2026-09-08\n---\n\nJust an ordinary paragraph, no markers at all.\n"
        )
        self.assertFalse(views.has_audience_markers(views._strip_body(no_markers_md)))
        result = self._build_views(no_markers_md)
        self.assertEqual(result.outputs, {})
        self.assertEqual(result.gate.findings, [])
        self.assertTrue(result.gate.ok)

    def test_generator_build_end_to_end_regression_for_a_no_markers_document(self) -> None:
        """``generator.build()`` itself, unchanged, for a document that predates the views registry --
        reuses the SAME committed fixture (``tools/docgen/sample.md``) the rest of this
        engine's test suite already builds, so this is a true non-regression check rather
        than a new, weaker proxy."""
        out_root = _REPO / ".docgen"
        out_root.mkdir(exist_ok=True)
        out_dir = Path(tempfile.mkdtemp(dir=out_root))
        try:
            result = generator.build(
                _REPO / "tools" / "docgen" / "sample.md", formats=("html",), out_dir=out_dir
            )
            self.assertTrue(result.gate.ok, [f.message for f in result.gate.findings])
            self.assertEqual(set(result.outputs), {"html"})
            for key in result.outputs:
                self.assertFalse(key.startswith("view:"))
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)


class GeneratorBuildWiresAudienceViews(_IsolatedProjectIndexCase):
    """The seam itself: ``generator.build()`` -> ``views.build_and_gate_views`` for a
    document that DOES declare markers, with the real DOC_MANIFEST.md read replaced by a
    controlled fixture row (so this test depends on nothing this session did not create)."""

    def test_generator_build_writes_and_registers_every_view(self) -> None:
        out_root = _REPO / ".docgen"
        out_root.mkdir(exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(dir=out_root))
        try:
            src = work_dir / f"{_FIX_ID}.md"
            src.write_text(_FIXTURE_ALL_FOUR, encoding="utf-8")
            with unittest.mock.patch.object(
                doc_manifest, "read_manifest", lambda path: [_manifest_row_for(_FIX_ID)]
            ):
                result = generator.build(src, formats=("html",), out_dir=work_dir)
            self.assertTrue(result.gate.ok, [f.message for f in result.gate.findings])
            self.assertEqual(
                set(result.outputs),
                {"html", "view:public", "view:github", "view:commercial", "view:internal"},
            )
            public_text = result.outputs["view:public"].read_text(encoding="utf-8")
            self.assertIn(_PUBLIC_INTRO_PHRASE, public_text)
            self.assertNotIn(_INTERNAL_PHRASE, public_text)
            index_data = self.index_file
            self.assertTrue(index_data.is_file(), "generated views were not registered")
            registered = index_data.read_text(encoding="utf-8")
            self.assertIn(f"{_FIX_ID}.public", registered)
            self.assertIn('"derived"', registered)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


class GeneratedViewCannotBeReprocessedAsASource(unittest.TestCase):
    def test_is_generated_view_detectors_recognise_the_stamp_and_the_naming_scheme(self) -> None:
        stamped = views._stamp("SRC-1", "public") + "some filtered body text\n"
        self.assertTrue(views.is_generated_view_text(stamped))
        self.assertFalse(views.is_generated_view_text("# An ordinary document\n"))

        self.assertTrue(views.is_generated_view_path(Path("docs/FOO-002.public.md")))
        self.assertTrue(views.is_generated_view_path(Path("docs/FOO-002.internal.md")))
        self.assertFalse(views.is_generated_view_path(Path("docs/FOO-002.md")))
        self.assertFalse(views.is_generated_view_path(Path("docs/FOO-002.public.html")))

    def test_build_and_gate_views_refuses_an_already_generated_view_as_input(self) -> None:
        already_stamped = views._stamp(_FIX_ID, "public") + "filtered text\n"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(views.AudienceMarkerError) as ctx:
                views.build_and_gate_views(
                    source_stem="whatever",
                    md_text=already_stamped,
                    header=parse_header(_FIXTURE_ALL_FOUR),
                    out_directory=Path(tmp),
                    manifest_rows=[_manifest_row_for(_FIX_ID)],
                )
            self.assertIn("GENERATED", str(ctx.exception))


class ProjectIndexRegistration(_IsolatedProjectIndexCase):
    def test_each_view_is_registered_as_a_derived_artifact(self) -> None:
        self._build_views(_FIXTURE_ALL_FOUR)
        for audience in views.AUDIENCE_LEVELS:
            entries = project_index.list_artifacts(tag="derived")
            ids = {e["id"] for e in entries}
            self.assertIn(f"{_FIX_ID}.{audience}", ids)
        entry = next(e for e in project_index.list_artifacts() if e["id"] == f"{_FIX_ID}.public")
        self.assertEqual(entry["type"], "document")
        self.assertEqual(entry["status"], "generated")
        self.assertIn("view", entry["tags"])
        self.assertIn("public", entry["tags"])


class ViewRegistrationUsesTheIndexDirectoryAsRoot(unittest.TestCase):
    """Fixed 2026-09-24. ``_register_view`` used to relativize a view's registered ``path``
    against ``engine_config.host_root()`` unconditionally, while every READER of the index
    (``verify``, ``list_artifacts``, the dashboard) resolves a registered path against
    ``artifact_index._artifact_root()`` -- the index's OWN directory, which that module's
    docstring says a relocated index carries with it as its frame of reference. The two agree
    only when the index lives exactly at ``host_root()`` -- the default, and the only shape
    every prior test exercised, because none of them patched ``host_root()`` at all (only
    ``_index_path``, so ``host_root()`` kept returning this repo's real checkout root, entirely
    unrelated to the test's own tmpdir -- the OLD code's ``relative_to`` call was ALREADY
    failing there and silently falling back to an absolute path, which happens to still resolve
    correctly since ``Path("/a") / "/b"`` discards the left operand. That accident is exactly
    why this bug went unnoticed).

    The failure needs ``out_path`` to be genuinely INSIDE ``host_root()`` (so the old
    ``relative_to`` call SUCCEEDS, producing a non-absolute, host-root-relative string) while the
    index lives in a DIFFERENT subdirectory of that same host -- exactly the shape a host
    relocating its index to avoid a root-level collision produces (measured live in a downstream host:
    a real ``cli build`` wrote and registered four views, and ``verify()`` reported all four
    ``MISSING`` -- correct data, wrong frame). This case is the first to patch ``host_root()``
    itself (env var + cache-clear, matching ``test_config_resolution.py``'s pattern) so the two
    frames genuinely diverge.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.host = Path(self._tmp.name).resolve()
        (self.host / "docs" / "design" / "doc-system").mkdir(parents=True)
        (self.host / "out").mkdir()
        self.index_file = self.host / "docs" / "design" / "doc-system" / "PROJECT_INDEX.json"
        self.out_dir = self.host / "out"

        self._prev_host_root_env = os.environ.get("ENGINE_HOST_ROOT")
        os.environ["ENGINE_HOST_ROOT"] = str(self.host)
        engine_config.host_root.cache_clear()
        self.addCleanup(self._restore_host_root)

        patcher = unittest.mock.patch.object(project_index, "_index_path", lambda: self.index_file)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _restore_host_root(self) -> None:
        if self._prev_host_root_env is None:
            os.environ.pop("ENGINE_HOST_ROOT", None)
        else:
            os.environ["ENGINE_HOST_ROOT"] = self._prev_host_root_env
        engine_config.host_root.cache_clear()

    def test_a_view_registers_and_verify_finds_it_when_the_index_lives_elsewhere(self) -> None:
        header = parse_header(_FIXTURE_ALL_FOUR)
        result = views.build_and_gate_views(
            source_stem=header.id,
            md_text=_FIXTURE_ALL_FOUR,
            header=header,
            out_directory=self.out_dir,
            manifest_rows=[_manifest_row_for(header.id)],
            may_write=True,
        )
        self.assertTrue(result.gate.ok, [f.message for f in result.gate.findings])
        self.assertIn("view:public", result.outputs)

        entry = next(e for e in project_index.list_artifacts() if e["id"] == f"{header.id}.public")
        # Relative to the INDEX's directory (`docs/design/doc-system/`), climbing back OUT to
        # `out/` -- never a `host_root()`-relative string like `out/<file>` (the bug this proves).
        expected_path = str(
            Path("../../..") / "out" / views.generated_view_filename(header.id, "public")
        )
        self.assertEqual(entry["path"], expected_path)

        report = project_index.verify()
        self.assertEqual(report["missing"], [], report)
        self.assertTrue(report["ok"], report)


if __name__ == "__main__":
    unittest.main()


class RegistrationUnavailableIsBlockingNotSilent(_IsolatedProjectIndexCase):
    """A host where the registry genuinely cannot be imported must be told, loudly.

    **Updated 2026-09-24.** The registry used to live at ``tools/project_index/index.py``,
    so a host owning an unrelated ``tools/project_index`` package (one downstream host's is a
    docs-index gate) shadowed it unconditionally — see ``ViewRegistrationUnavailable``'s docstring
    for that history. It now lives at ``tools.docgen.artifact_index``, inside the package every
    consumer of ``views.py`` already vendors whole, so that specific collision can no longer
    happen (``ViewsRegisterDespiteAnUnrelatedHostProjectIndexPackage`` below proves it). This class
    now shadows ``tools.docgen.artifact_index`` itself — a genuinely broken/partial vendoring of
    ``tools/docgen`` — to prove the fail-closed, loud-not-silent behavior still holds for the
    failure mode that remains possible.
    """

    def test_the_probe_raises_a_named_error_when_the_registry_is_shadowed(self) -> None:
        import builtins

        real_import = builtins.__import__

        def _shadowed(
            name: str,
            globals: Mapping[str, object] | None = None,
            locals: Mapping[str, object] | None = None,
            fromlist: Sequence[str] = (),
            level: int = 0,
        ) -> object:
            # `from tools.docgen import artifact_index` calls `__import__("tools.docgen", ...,
            # fromlist=("artifact_index",), ...)` -- the module NAME is the package, never the
            # submodule; the submodule shows up only in `fromlist`. Matching on `name` alone (the
            # pre-move shape, when the statement was `from tools.project_index import index`) would
            # never fire here.
            if name == "tools.docgen" and fromlist and "artifact_index" in fromlist:
                raise ImportError("cannot import name 'artifact_index' from 'tools.docgen'")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = _shadowed  # type: ignore[assignment]  # stand-in cannot match __import__'s exact signature
        try:
            with self.assertRaises(views.ViewRegistrationUnavailable) as ctx:
                views._load_project_index()
        finally:
            builtins.__import__ = real_import
        self.assertIn("was NOT written", str(ctx.exception))

    def test_a_shadowed_host_blocks_the_build_and_writes_no_view(self) -> None:
        """Not a silent skip: view registration is required, so nothing is written."""
        import builtins

        real_import = builtins.__import__

        def _shadowed(
            name: str,
            globals: Mapping[str, object] | None = None,
            locals: Mapping[str, object] | None = None,
            fromlist: Sequence[str] = (),
            level: int = 0,
        ) -> object:
            if name == "tools.docgen" and fromlist and "artifact_index" in fromlist:
                raise ImportError("shadowed by a broken/partial vendoring of tools/docgen")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = _shadowed  # type: ignore[assignment]  # stand-in cannot match __import__'s exact signature
        try:
            result = self._build_views(_FIXTURE_ALL_FOUR)
        finally:
            builtins.__import__ = real_import
        self.assertFalse(result.gate.ok, "a build that cannot register its views must BLOCK")
        self.assertEqual(result.outputs, {}, "no view may be written when registration is impossible")
        self.assertTrue(
            any("cannot be registered as derived" in f.message for f in result.gate.findings),
            "the blocking finding must name the cause",
        )


class ViewsRegisterDespiteAnUnrelatedHostProjectIndexPackage(_IsolatedProjectIndexCase):
    """THE FIX, falsifiable: a host that owns its own unrelated ``tools/project_index``
    package (one downstream host's shape exactly — a docs-index gate with no ``index`` submodule at
    all) must still be able to register generated views. Before the fix this raised
    ``ViewRegistrationUnavailable`` on every single build in such a host, unconditionally — see
    ``ViewRegistrationUnavailable``'s docstring. The registry moving to
    ``tools.docgen.artifact_index`` is what makes this possible: it no longer depends on
    ``tools/project_index`` being importable at all.

    Simulated by putting a FAKE ``tools.project_index`` package on ``sys.modules`` — one with no
    ``index`` submodule, exactly that host's shape — before probing/building, then removing it
    again. A real second package on disk would need a second temp host tree; faking the shadow at
    the ``sys.modules`` level is the same falsification ``RegistrationUnavailableIsBlockingNotSilent``
    already uses (a fake ``__import__``), just for the ALLOW side instead of the REFUSE side.
    """

    def test_load_project_index_returns_the_registry_despite_the_shadow(self) -> None:
        import sys
        import types

        fake_pkg = types.ModuleType("tools.project_index")
        fake_pkg.__path__ = []  # a package with no `index` submodule -- the downstream host's real shape
        had_real = "tools.project_index" in sys.modules
        real_pkg = sys.modules.get("tools.project_index")
        sys.modules["tools.project_index"] = fake_pkg
        sys.modules.pop("tools.project_index.index", None)
        try:
            with self.assertRaises(ImportError):
                __import__("tools.project_index.index")  # sanity: the shadow is real
            registry = views._load_project_index()
        finally:
            if had_real:
                sys.modules["tools.project_index"] = real_pkg  # type: ignore[assignment]
            else:
                sys.modules.pop("tools.project_index", None)
        self.assertIs(registry, project_index, "must resolve to tools.docgen.artifact_index")

    def test_a_shadowed_host_still_builds_and_registers_a_view(self) -> None:
        import sys
        import types

        fake_pkg = types.ModuleType("tools.project_index")
        fake_pkg.__path__ = []
        had_real = "tools.project_index" in sys.modules
        real_pkg = sys.modules.get("tools.project_index")
        sys.modules["tools.project_index"] = fake_pkg
        sys.modules.pop("tools.project_index.index", None)
        try:
            result = self._build_views(_FIXTURE_ALL_FOUR)
        finally:
            if had_real:
                sys.modules["tools.project_index"] = real_pkg  # type: ignore[assignment]
            else:
                sys.modules.pop("tools.project_index", None)
        self.assertTrue(result.gate.ok, [f.message for f in result.gate.findings])
        self.assertIn("view:public", result.outputs)
        self.assertIn(
            f"{_FIX_ID}.public",
            {e["id"] for e in project_index.list_artifacts(tag="derived")},
            "the view built under the shadow must still be registered",
        )


class FencedCodeBlockMarkersAreNotRealMarkers(_IsolatedProjectIndexCase):
    """A marker comment WRITTEN INSIDE A FENCED CODE BLOCK -- e.g. a
    document illustrating the marker syntax itself, the exact shape this engine's own
    docs use -- must be treated as TEXT, never a real marker. Before the fix,
    ``_TOKEN_RE.finditer`` carried no fence state, so the fenced example below was split
    out as its own (fake) 'internal' segment: it fails SAFE for leaks (excluded content
    never appears where it should not) but CORRUPTS the document, silently stripping the
    illustrated example out of every non-internal view and leaving a mangled empty fence
    -- while the REAL internal marker elsewhere in the same document must keep gating
    correctly throughout.
    """

    def test_fenced_example_marker_is_inert_and_the_real_marker_still_gates(self) -> None:
        header = parse_header(_FIXTURE_FENCED_MARKER_EXAMPLE)
        body = views._strip_body(_FIXTURE_FENCED_MARKER_EXAMPLE)

        self.assertTrue(views.has_audience_markers(body))
        segments = views.parse_body_segments(body, default_audience="public", doc_id=header.id)
        # 3 segments: the public intro, the ONE real internal block, and everything
        # after it -- INCLUDING the fenced illustration, untouched -- as a single
        # trailing unmarked block. A fence-blind tokenizer instead sees 5: the fenced
        # pair carves the illustrated example out as a fourth (fake) marked segment.
        self.assertEqual(
            len(segments), 3,
            "the fenced example marker pair was split out as its own segment -- the "
            "tokenizer is not fence-aware",
        )

        result = self._build_views(_FIXTURE_FENCED_MARKER_EXAMPLE)
        self.assertTrue(result.gate.ok, [f.message for f in result.gate.findings])
        public_text = self.out_dir.joinpath(f"{_FENCE_FIX_ID}.public.md").read_text(encoding="utf-8")

        # The REAL internal marker still gates correctly -- never weakened by this fix.
        self.assertNotIn(_FENCE_REAL_INTERNAL_PHRASE, public_text)
        # The FENCED example marker is documentation text, not a real marker -- it (and
        # its literal marker-comment text) must survive verbatim in the public view.
        self.assertIn(_FENCE_EXAMPLE_PHRASE, public_text)
        self.assertIn("<!-- audience: internal -->", public_text)
        self.assertIn("<!-- /audience -->", public_text)

        internal_text = self.out_dir.joinpath(f"{_FENCE_FIX_ID}.internal.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(_FENCE_REAL_INTERNAL_PHRASE, internal_text)



class ACodeSpanLineIsNotAFenceOpen(_IsolatedProjectIndexCase):
    """A BACKTICK fence's info string may not contain a backtick (CommonMark), so a
    line like ```` ```x``` ```` is a paragraph containing a code SPAN and opens nothing.

    ``_FENCE_OPEN_RE`` matched the leading three backticks and ignored the rest of the
    line, so that line opened a fence that never closed. The range ran to EOF, every real
    marker after it became invisible, and ``build_and_gate_views`` returned ``gate.ok=True``
    with **zero** views written -- a green build that did nothing. Measured at the seam,
    two documents identical but for that one line::

        control              gate.ok=True findings=0 outputs=[public,github,commercial,internal]
        with ```x```         gate.ok=True findings=0 outputs=[]

    Deleting the backtick-in-info-string test from ``_fenced_ranges`` turns
    ``test_the_real_marker_after_a_code_span_line_still_gates`` red.
    """

    def test_a_code_span_line_opens_no_fence(self) -> None:
        self.assertEqual(views._fenced_ranges("a\n```x```\nb\n"), [])

    def test_a_code_span_line_does_not_swallow_the_rest_of_the_document(self) -> None:
        body = "```x```\n<!-- audience: internal -->\nsecret\n<!-- /audience -->\n"
        self.assertEqual(views._fenced_ranges(body), [])
        self.assertTrue(
            views.has_audience_markers(body),
            "the marker after the code-span line was swallowed by a phantom fence",
        )

    def test_an_ordinary_backtick_fence_still_opens_and_closes(self) -> None:
        body = "before\n```python\ncode\n```\nafter\n"
        self.assertEqual(views._fenced_ranges(body), [(7, len(body) - len("after\n"))])

    def test_a_longer_bare_backtick_run_still_opens(self) -> None:
        """```` has an EMPTY info string -- the rule bars backticks in the info, not the fence."""
        body = "````\ncode\n````\n"
        self.assertEqual(views._fenced_ranges(body), [(0, len(body))])

    def test_a_tilde_fence_may_carry_backticks_in_its_info_string(self) -> None:
        """The restriction is backtick-fence-only; narrowing it to all fences would be wrong."""
        body = "~~~`x`\n<!-- audience: internal -->\n~~~\n"
        self.assertEqual(views._fenced_ranges(body), [(0, len(body))])
        self.assertFalse(views.has_audience_markers(body))

    def test_the_real_marker_after_a_code_span_line_still_gates(self) -> None:
        """End-to-end at the ``build_and_gate_views`` seam -- the red proof."""
        result = self._build_views(_FIXTURE_CODE_SPAN_LINE)
        self.assertTrue(result.gate.ok, [f.message for f in result.gate.findings])

        written = sorted(p.name for p in self.out_dir.glob(f"{_SPAN_FIX_ID}.*.md"))
        self.assertEqual(
            len(written), len(views.AUDIENCE_LEVELS),
            f"a green build wrote {len(written)} views, not {len(views.AUDIENCE_LEVELS)}: {written}",
        )

        public_text = self.out_dir.joinpath(f"{_SPAN_FIX_ID}.public.md").read_text(encoding="utf-8")
        self.assertNotIn(_SPAN_INTERNAL_PHRASE, public_text)
        self.assertIn(_SPAN_PUBLIC_PHRASE, public_text)

        internal_text = self.out_dir.joinpath(f"{_SPAN_FIX_ID}.internal.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(_SPAN_INTERNAL_PHRASE, internal_text)

    def test_known_gap_container_shapes_are_still_fence_blind(self) -> None:
        """PIN of a KNOWN GAP, not an endorsement -- see ``_fenced_ranges``'s docstring.

        A fence indented into a list item's content column, a 4-space-indented code block,
        and a fence inside a blockquote are all code in CommonMark, and a marker inside one
        is still scanned as REAL here (the corrupting, leak-safe direction).
        Closing them needs container-block tracking. This test exists so the gap cannot
        change SIZE silently; **when it is closed, invert this test in the same commit.**
        """
        gaps = {
            "list-indented fence": "- item\n\n      ```\n      <!-- audience: internal -->\n      ```\n",
            "4-space indented code": "para\n\n    <!-- audience: internal -->\n",
            "blockquoted fence": "> ```\n> <!-- audience: internal -->\n> ```\n",
        }
        for label, body in gaps.items():
            with self.subTest(shape=label):
                self.assertEqual(views._fenced_ranges(body), [], f"{label}: now recognised")
                self.assertTrue(
                    views.has_audience_markers(body),
                    f"{label}: gap closed -- invert this test",
                )


class StaleViewIsRetiredOnAGateBlockedRebuild(_IsolatedProjectIndexCase):
    """A previously-written, previously-registered view must be RETIRED
    (deregistered AND deleted) the instant a later rebuild for the SAME (stem, audience)
    is gate-blocked. Before the fix, ``build_and_gate_views`` only ever called
    ``register_artifact`` -- gate 9 (or any other gate folded into ``run_gates``) guards
    the WRITE, but nothing guarded RETENTION, so a document that once published a clean
    view and later grows a leak kept serving the OLD, now-wrong view forever while the
    gate correctly reported the rebuild blocked.
    """

    def test_a_gate_blocked_rebuild_removes_the_previous_views_file_and_registration(
        self,
    ) -> None:
        header = parse_header(_FIXTURE_ALL_FOUR)
        rows = [_manifest_row_for(header.id)]

        clean_result = views.build_and_gate_views(
            source_stem=_FIX_ID,
            md_text=_FIXTURE_ALL_FOUR,
            header=header,
            out_directory=self.out_dir,
            manifest_rows=rows,
            may_write=True,
        )
        self.assertTrue(clean_result.gate.ok, [f.message for f in clean_result.gate.findings])
        stale_path = self.out_dir / f"{_FIX_ID}.public.md"
        self.assertTrue(stale_path.is_file(), "setup: the first build did not write the view")
        self.assertIn(
            f"{_FIX_ID}.public",
            {e["id"] for e in project_index.list_artifacts(tag="derived")},
            "setup: the first build did not register the view",
        )

        # Force every per-audience gate to BLOCK on the second build -- simulates the
        # real-world case (the document grew a leak) without needing to hand-craft one,
        # and exercises the retention path for every audience uniformly.
        forced_block = GateResult(
            gate="secret_value",
            findings=[
                Finding(
                    gate="secret_value",
                    message="forced block -- simulates a rebuild that now leaks",
                    severity=Severity.CRIT,
                    blocking=True,
                    evidence="<test>",
                )
            ],
        )
        with unittest.mock.patch.object(export_sanitizer, "run_gates", return_value=forced_block):
            blocked_result = views.build_and_gate_views(
                source_stem=_FIX_ID,
                md_text=_FIXTURE_ALL_FOUR,
                header=header,
                out_directory=self.out_dir,
                manifest_rows=rows,
                may_write=True,
            )
        self.assertFalse(blocked_result.gate.ok)
        self.assertNotIn("view:public", blocked_result.outputs)

        self.assertFalse(
            stale_path.exists(),
            "a gate-blocked rebuild left the PREVIOUS view on disk -- stale views are "
            "never retired",
        )
        self.assertNotIn(
            f"{_FIX_ID}.public",
            {e["id"] for e in project_index.list_artifacts(tag="derived")},
            "a gate-blocked rebuild left the PREVIOUS view's registration in place",
        )


class ShingleFloorBlindSpotIsClosedByAnExactSubstringCheck(unittest.TestCase):
    """``shingle_overlap``'s n=8/n=4 comparison produces ZERO shingles for
    a sibling whose CONTENT token count (after stopword-stripping) falls below the
    shingle floor (``_MIN_SHINGLE_N`` = 4) -- so a short excluded block leaks with
    ``gate.ok = True`` and NO findings, BY CONSTRUCTION, no matter how verbatim the leak
    is. ``_SHORT_LEAK_PHRASE`` reproduces the measured example exactly: 6 raw words, 3
    content tokens once "this"/"is"/"a" are stripped as stopwords.
    """

    def test_a_short_excluded_block_below_the_shingle_floor_still_blocks_on_exact_leak(
        self,
    ) -> None:
        header = views.build_view_header(
            parse_header(_FIXTURE_FOR_SHINGLE_FLOOR_TEST), [_SHORT_LEAK_PHRASE]
        )
        self.assertEqual(len(header.variants), 1)

        # Sanity on the premise itself: the phrase really IS below the shingle floor, so
        # shingle_overlap alone sees NOTHING at either n this gate checks -- if this
        # assertion ever fails, the rest of the test is testing the wrong scenario.
        content_tokens = export_sanitizer._normalize_for_shingle(_SHORT_LEAK_PHRASE)
        self.assertLess(len(content_tokens), export_sanitizer._MIN_SHINGLE_N)
        self.assertEqual(
            export_sanitizer.shingle_overlap(_SHORT_LEAK_PHRASE, _SHORT_LEAK_PHRASE, n=8), []
        )
        self.assertEqual(
            export_sanitizer.shingle_overlap(_SHORT_LEAK_PHRASE, _SHORT_LEAK_PHRASE, n=4), []
        )

        leaked_doc_text = (
            f"Some public paragraph.\n\n{_SHORT_LEAK_PHRASE}\n\nAnother public paragraph.\n"
        )
        rows = [_manifest_row_for(_SHINGLE_FLOOR_FIX_ID)]
        gate = export_sanitizer.run_gates(
            leaked_doc_text, header, siblings=[_SHORT_LEAK_PHRASE], manifest_rows=rows
        )
        self.assertFalse(gate.ok, "a leaked block below the shingle floor did not block the gate")
        overlap_findings = [f for f in gate.findings if f.gate == "variant_overlap"]
        self.assertTrue(
            overlap_findings,
            "gate 9 produced no variant_overlap finding for a leaked block below the "
            "shingle floor -- the exact-substring floor check is missing",
        )
        self.assertTrue(all(f.blocking for f in overlap_findings))


def _doc_with_excluded(block: str, doc_id: str = "SUBFLOOR-001") -> str:
    """A minimal, otherwise-valid document whose ONLY internal block is *block*."""
    return f"""---
id: {doc_id}
classification: public
title: Sub-floor Fixture
surface: web
audience: technical
owner: doc-system
status: draft
export_allowed: true
last_reviewed: 2026-09-08
default_audience: public
---

# Sub-floor Fixture

The public introduction is ordinary prose with nothing excluded about it.

<!-- audience: internal -->
{block}
<!-- /audience -->
"""


class AnExcludedBlockTooShortToGateIsRefusedAtAuthoringTime(_IsolatedProjectIndexCase):
    """Gate 9 falls back to an exact-substring check for blocks below the
    n=4 shingle floor, and at that length the text carries no signal separating a leak from a
    coincidence: measured on the copy's build 1.0.13, 4 of 4 constructed cases were CRIT blocking
    FALSE POSITIVES against ordinary public prose — `Pending` inside "the review is pending
    sign-off", a legitimately reused "See the table below.", `Q4 plan` inside "Q4 planning".

    A word-boundary test alone rescues exactly ONE of those four (the mid-word case) and leaves
    three standing, so the ambiguity is removed at its SOURCE instead: such a block is refused
    when the document is built, and the author is told to widen or move it. The rejected
    alternatives are recorded in `views.build_and_gate_views` — a distinctiveness/boilerplate
    allowlist is a new false-negative surface on a moat, and downgrading the CRIT to a warning
    trades a certain availability loss for an uncertain security one.

    Blast radius when this landed: 0 sub-floor excluded blocks across 80 engine-tracked and 1,384
    host-tracked `.md`, so no existing document needed rewording.
    """

    SUB_FLOOR = ("pending", "See the table below.", "launch date confirmation", "Q4 plan")

    def _authoring_refusals(self, result: views.ViewsBuildResult) -> list[str]:
        return [f.message for f in result.gate.findings if "distinctive content words" in f.message]

    def test_every_sub_floor_block_is_refused_and_no_view_is_written(self) -> None:
        for block in self.SUB_FLOOR:
            with self.subTest(block=block):
                result = self._build_views(_doc_with_excluded(block))
                refusals = self._authoring_refusals(result)
                self.assertEqual(len(refusals), 1, refusals)
                self.assertFalse(result.gate.ok)
                self.assertEqual(result.outputs, {}, "no view may be written on an authoring refusal")
                self.assertIn(block, refusals[0], "the message must name the offending block")

    def test_the_refusal_is_an_authoring_error_not_a_leak_finding(self) -> None:
        """The distinction is the whole point: the author is told to fix the BLOCK, not told
        that their public document leaked something. A `variant_overlap` finding here would be
        the false positive this change exists to remove."""
        result = self._build_views(_doc_with_excluded("pending"))
        gates = {f.gate for f in result.gate.findings}
        self.assertIn("audience_views", gates)
        self.assertNotIn("variant_overlap", gates)

    def test_one_finding_per_block_not_one_per_audience(self) -> None:
        """A block excluded from three views is ONE authoring problem, not three."""
        result = self._build_views(_doc_with_excluded("pending"))
        self.assertEqual(len(self._authoring_refusals(result)), 1)

    def test_a_block_at_the_floor_builds_and_still_gates(self) -> None:
        """The floor is a floor, not a ban: a distinctive block is unaffected."""
        result = self._build_views(_doc_with_excluded("the acme merger terms are final and binding"))
        self.assertEqual(self._authoring_refusals(result), [])
        self.assertTrue(result.gate.ok, [f.message for f in result.gate.findings])
        self.assertEqual(set(result.outputs), {"view:public", "view:github", "view:commercial", "view:internal"})


class TheExactSubstringCheckRespectsWordBoundaries(unittest.TestCase):
    """The half of the sub-floor fix that survives for non-view callers of gate 9.

    `run_gates` is reachable with `header.variants` siblings that never came from an audience
    view, so the exact check still runs on short siblings there and the mid-word false positive
    still mattered. Measured: 1 of 4 constructed false positives rescued, 0 of 2 genuine verbatim
    leaks missed.
    """

    def test_a_mid_word_match_is_no_longer_a_hit(self) -> None:
        self.assertIsNone(
            export_sanitizer._exact_substring_overlap(
                "our Q4 planning meeting is on Tuesday", "Q4 plan"
            )
        )

    def test_a_genuine_verbatim_leak_is_still_a_hit(self) -> None:
        for prose, sibling in (
            ("the Q4 plan is attached", "Q4 plan"),
            ("the acme merger terms are final", "acme merger terms"),
        ):
            with self.subTest(sibling=sibling):
                self.assertIsNotNone(
                    export_sanitizer._exact_substring_overlap(prose, sibling)
                )

    def test_the_floor_predicate_has_one_definition(self) -> None:
        """One definition, not two: `views.py` asks this module where the floor is
        rather than re-spelling `len(_normalize_for_shingle(x)) < _MIN_SHINGLE_N`."""
        self.assertTrue(export_sanitizer.below_shingle_floor("pending"))
        self.assertFalse(
            export_sanitizer.below_shingle_floor("the acme merger terms are final and binding")
        )
        self.assertEqual(export_sanitizer.MIN_SHINGLE_N, export_sanitizer._MIN_SHINGLE_N)


class RetirementNeverRunsOnABuildThatDeclaredItWouldNotWrite(_IsolatedProjectIndexCase):
    """`_retire_stale_view` was called from an `elif not gate.ok:` branch that never
    consulted `may_write`, so a dry-run/preview build DELETED the published view and its
    registration. Both docstrings already promised the opposite, which is the dangerous
    direction: a reader checking the contract was told the truth while the code did the reverse.
    """

    def test_a_may_write_false_build_leaves_a_published_view_alone(self) -> None:
        published = self.out_dir / views.generated_view_filename("RETIRE-001", "public")
        published.write_text("PREVIOUSLY PUBLISHED GOOD VIEW\n", encoding="utf-8")
        result = self._build_views(
            _doc_with_excluded("pending", doc_id="RETIRE-001"), source_stem="RETIRE-001", may_write=False
        )
        self.assertFalse(result.gate.ok, "the fixture must be gate-blocked for this to mean anything")
        self.assertTrue(
            published.exists(),
            "a build with may_write=False deleted a published view",
        )

    def test_a_may_write_true_build_still_retires_a_stale_view(self) -> None:
        """The retention fix itself must survive: this is the behaviour the retention fix added."""
        published = self.out_dir / views.generated_view_filename("RETIRE-002", "public")
        published.write_text("STALE VIEW\n", encoding="utf-8")
        result = self._build_views(
            _doc_with_excluded("pending", doc_id="RETIRE-002"), source_stem="RETIRE-002", may_write=True
        )
        self.assertFalse(result.gate.ok)
        self.assertFalse(published.exists(), "a blocked rebuild must still retire the stale view")

    def test_one_failing_audience_does_not_leave_the_others_published(self) -> None:
        """Second half of the retention fix. `_retire_stale_view` is deliberately loud, and the raise used
        to live INSIDE the audience loop — so the first failure aborted it and the remaining
        audiences kept serving stale, still-registered views. Every audience is attempted now,
        and the error is still raised afterwards: nothing is swallowed, nothing is skipped.
        """
        published = {}
        for audience in views.AUDIENCE_LEVELS:
            path = self.out_dir / views.generated_view_filename("RETIRE-003", audience)
            path.write_text("STALE VIEW\n", encoding="utf-8")
            published[audience] = path

        real_remove = project_index.remove_artifact
        calls: list[str] = []

        def flaky_remove(artifact_id: str) -> object:
            calls.append(artifact_id)
            if len(calls) == 1:
                raise RuntimeError("deregistration exploded for the first audience")
            return real_remove(artifact_id)

        with (
            unittest.mock.patch.object(project_index, "remove_artifact", flaky_remove),
            self.assertRaises(RuntimeError),
        ):
            self._build_views(
                _doc_with_excluded("pending", doc_id="RETIRE-003"), source_stem="RETIRE-003"
            )

        self.assertEqual(len(calls), len(views.AUDIENCE_LEVELS), "every audience must be attempted")
        survived = [a for a, p in published.items() if p.exists()]
        self.assertEqual(
            len(survived), 1,
            f"only the audience whose deregistration raised may survive; survived={survived}",
        )


class AMarkerInsideACodeSpanIsDocumentationNotADirective(unittest.TestCase):
    """The fence handling taught the scanner about fenced BLOCKS and stopped there.

    A marker written in backticks on a prose line is the same thing one construct further down,
    and it was still read as a real directive: four tracked host documents registered as
    marker-using purely through backticked mentions in register rows and reports.

    **The fix belongs in `_real_marker_matches`, not in `has_audience_markers`.** The two callers
    already agreed — they were agreeing on the wrong answer. Teaching only the detector would have
    bought a correct detector at the price of the "can never disagree" invariant that function
    exists to hold, which is the duplicated-decision shape this codebase keeps paying for.

    This states the trade rather than assuming it: a marker inside a code span is documentation
    of the syntax; an author who wants a real one writes it outside backticks. `parse_body_segments`
    stays fail-closed on an unbalanced pair, so a backticked open with a real close REFUSES.
    """

    #: CommonMark, not a backtick count. The naive "two backticks on this line" test is the same
    #: input-grammar mistake that cost four earlier host findings a round each.
    CASES: ClassVar[tuple[tuple[str, str, bool], ...]] = (
        ("equal-length runs pair", "text `<!-- audience: internal -->` text", False),
        ("a double-backtick span", "text ``<!-- audience: internal -->`` text", False),
        ("a span containing a SHORTER run", "text ``a ` <!-- audience: internal --> b`` t", False),
        ("an unterminated run is literal", "text `<!-- audience: internal --> no closer", True),
        ("a span across one line break", "text `<!-- audience:\ninternal -->` text", False),
        ("a span inside a list item", "- item `<!-- audience: internal -->` tail", False),
        ("a span inside a table cell", "| a | `<!-- audience: internal -->` | b |", False),
        ("unequal runs do NOT pair", "text ``<!-- audience: internal -->` more", True),
        # The positive control: the fix must not swallow a REAL marker that shares a line with a
        # documented one. Without this, "exclude anything on a line containing backticks" would
        # pass every other row here and be badly wrong.
        ("a real marker beside a backticked one",
         "see `<!-- audience: internal -->` then <!-- audience: internal -->", True),
        # The blank-line bound, and it is load-bearing rather than pedantic: without it ONE stray
        # backtick pairs with a backtick far below and silently hides every marker in between —
        # a typo would become a leak. A code span is inline content and cannot cross a paragraph.
        ("a stray run cannot swallow a later real marker",
         "a stray ` here\n\n<!-- audience: internal -->\n\nand a ` there", True),
        # A GFM table is ONE paragraph, but each row is parsed on its own, so a span cannot cross
        # a row. Measured on a host's findings register: 28 rows end on a truncated,
        # unbalanced run, and one of them flipped the pairing of every row below it.
        ("a stray run in an earlier table row does not flip a later row",
         "| h | h |\n|---|---|\n| a | stray ` here |\n| b | `<!-- audience: internal -->` |", False),
        # The leak direction of the same bug: without the row bound, the stray run pairs with a
        # run in the next row and HIDES the real marker between them.
        ("a table-row span cannot reach into the next row to hide a real marker",
         "| h | h |\n|---|---|\n| a | `open |\n| b | <!-- audience: internal --> ` |", True),
        # Found in a code review of the copy: a leading pipe alone is not a table. Without a delimiter row this is an
        # ordinary paragraph, where the span crosses the soft break and the marker is code.
        ("pipe-prefixed prose is a paragraph, not a table",
         "| ordinary prose `example\n<!-- audience: internal --> remains code`", False),
    )

    def test_every_commonmark_span_shape_is_classified_correctly(self) -> None:
        for label, body, expected in self.CASES:
            with self.subTest(shape=label):
                self.assertEqual(
                    views.has_audience_markers(body), expected,
                    f"{label}: a code span is documentation, an unpaired run is literal text, "
                    "and a real marker outside backticks is still a directive",
                )

    def test_a_run_alone_on_its_line_is_left_to_the_fence_scanner(self) -> None:
        """Scope discipline. A backtick run that occupies its whole line is a FENCE-OPEN shape.

        Pairing those here closes two gaps `_fenced_ranges` deliberately pins (a fence indented
        into a list item, a blockquoted fence) — and closes them INCONSISTENTLY, since a blank line
        inside the block re-opens them. `test_known_gap_container_shapes_are_still_fence_blind`
        caught exactly that while this was being written; the gaps stay honestly pinned instead.
        """
        body = "- ```\n  <!-- audience: internal -->\n  ```\n"
        self.assertTrue(
            views.has_audience_markers(body),
            "the list-indented fence gap must stay pinned, not be closed by accident",
        )

    def test_the_detector_and_the_segmenter_still_cannot_disagree(self) -> None:
        """The invariant the fix was placed to protect, asserted directly."""
        for label, body, expected in self.CASES:
            with self.subTest(shape=label):
                self.assertEqual(
                    bool(views._real_marker_matches(body)), expected,
                    f"{label}: the shared primitive and the detector must give one answer",
                )

    def test_the_four_tracked_documents_no_longer_register_as_marker_using(self) -> None:
        """The measured population this row was filed for: a host's real documents, named by the environment.

        ``ENGINE_TEST_HOST_ROOT`` is a host checkout and ``ENGINE_TEST_HOST_DOCS`` the documents to test, as paths relative to that
        root separated by ``os.pathsep``. Skipped, with that cause, when either is unset: the documents belong to a host, not to
        the engine, and the table above (``CASES``) carries the shapes that made them register.
        """
        root_env = os.environ.get("ENGINE_TEST_HOST_ROOT")
        docs_env = os.environ.get("ENGINE_TEST_HOST_DOCS")
        if not root_env or not docs_env:
            self.skipTest("set ENGINE_TEST_HOST_ROOT and ENGINE_TEST_HOST_DOCS to run this against a host's real documents")
        root = Path(root_env)
        present = [root / d for d in docs_env.split(os.pathsep) if d and (root / d).is_file()]
        if not present:
            self.skipTest("none of the named documents exists under ENGINE_TEST_HOST_ROOT")
        for path in present:
            with self.subTest(doc=path.name):
                body = views._strip_body(path.read_text(encoding="utf-8", errors="replace"))
                self.assertFalse(
                    views.has_audience_markers(body),
                    f"{path.name} registers as marker-using through a backticked mention",
                )
