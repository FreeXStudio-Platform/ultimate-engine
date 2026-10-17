"""Counter-examples for the gate spine, the L9 hash gate, and the incremental build cache."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.docgen import build_cache
from tools.docgen.export_sanitizer import (
    NO_CONTRADICTION_MAPPING,
    PRECEDENCE,
    SPINE_CLASSES,
    check_precedence_spine,
)

_REPO = Path(__file__).resolve().parents[2]


class EveryEmittedGateHasAPrecedencePosition(unittest.TestCase):
    """An unlisted gate sorts LAST, below every advisory — so a BLOCKING build failure ranked
    beneath a non-blocking LOW note. Eight labels were emitted and unlisted when this was first
    derived from source rather than from ``PRECEDENCE`` itself."""

    # ⚠ **The dot belongs in both character classes** (`OG-191`). This probe carried the SAME
    # narrow pattern as `tools/health` CONS-04 — one root, two consumers, neither guarded — so it
    # was blind to `geomap.source`, `chart.rule`, `visual.collision` and thirteen more in exactly
    # the way the check it mirrors was. Widening CONS-04 alone would have left this test asserting
    # the property over a universe that excluded every gate the widening exposed.
    _LABEL_RE = re.compile(r'gate\s*=\s*"([a-z0-9_.-]+)"')
    _CONST_RE = re.compile(r'^_GATE\s*=\s*"([a-z0-9_.-]+)"', re.MULTILINE)

    def _emitted(self) -> set[str]:
        """The gate universe, derived the SAME way CONS-04 derives it (`OG-195`).

        This helper has now been the second consumer of a shared root twice. First it carried the
        same dot-blind regex CONS-04 carried, and was widened alongside it. Then CONS-04 moved to
        `ast` resolution to see `gate=GATE` against a module constant — and this stayed on regexes,
        so `identity` read as a dead `PRECEDENCE` entry here while CONS-04 correctly saw it
        emitted. Two implementations of one question disagree the moment one of them improves,
        which is `RULES.md` Rule 1 in miniature, so the AST resolver is now IMPORTED rather than
        reimplemented. The regexes stay as an extra widening net; the union is what is asserted.
        """
        from tools.health.checks import _gate_labels_via_ast

        found: set[str] = set()
        for py in (_REPO / "tools" / "docgen").rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            text = py.read_text(encoding="utf-8", errors="replace")
            found.update(self._LABEL_RE.findall(text))
            found.update(self._CONST_RE.findall(text))
            found.update(_gate_labels_via_ast(text))
        return found

    def test_the_ast_resolver_sees_a_constant_named_gate(self) -> None:
        """`OG-195`'s counter-example: a label bound to a module constant must be found.

        `identity.py` writes `Finding(gate=GATE, ...)` with `GATE = "identity"` at module level.
        A regex looking for a string literal after `gate=`, or for a constant spelled `_GATE`,
        finds nothing — and the gate sat unranked while the coverage check reported full coverage.
        Both spellings are asserted, so narrowing the resolver back to either one goes red.
        """
        from tools.health.checks import _gate_labels_via_ast

        for const in ("GATE", "_GATE", "SOME_OTHER_NAME"):
            with self.subTest(constant=const):
                src = f'{const} = "planted.kind"\nx = Finding(gate={const}, message="m")\n'
                self.assertIn("planted.kind", _gate_labels_via_ast(src))
        self.assertIn("identity", self._emitted())

    def test_the_scan_finds_something(self) -> None:
        """Guard against the vacuous pass: an empty universe would make every assertion below
        trivially true (LESSONS.md L-19)."""
        self.assertGreater(len(self._emitted()), 5)

    def test_every_emitted_label_is_in_precedence(self) -> None:
        self.assertEqual(sorted(self._emitted() - set(PRECEDENCE)), [])

    def test_precedence_holds_no_dead_entries(self) -> None:
        self.assertEqual(sorted(set(PRECEDENCE) - self._emitted()), [])

    def test_a_dotted_label_is_visible_to_this_scan(self) -> None:
        """`OG-191`'s counter-example: the scan must SEE names containing a dot.

        Derived, not pinned — the assertion is that dotted labels exist in the tree and that the
        pattern reads them, so it holds however many there are. Narrow the character class back to
        `[a-z0-9_-]+` and this goes red immediately, which is the whole point: the defect was
        sixteen real gates being invisible to a check that reported full coverage over them.
        """
        dotted = {label for label in self._emitted() if "." in label}
        self.assertTrue(dotted, "no dotted gate label was found — has the pattern been narrowed?")
        self.assertEqual(sorted(dotted - set(PRECEDENCE)), [],
                         "a dotted gate label is emitted but has no precedence position")

    def test_a_dotted_label_absent_from_precedence_is_caught(self) -> None:
        """Falsified the other way: plant one and prove the assertion above would fail.

        Without this, `test_a_dotted_label_is_visible_to_this_scan` passing tells you the corpus is
        currently clean but nothing about whether the check can fail.
        """
        planted = self._LABEL_RE.findall('Finding(gate="newkind.rule", message="x")')
        self.assertEqual(planted, ["newkind.rule"], "the pattern cannot read a dotted label")
        self.assertNotIn("newkind.rule", set(PRECEDENCE))
        self.assertNotEqual(sorted({*self._emitted(), "newkind.rule"} - set(PRECEDENCE)), [])

    def test_exempt_set_is_a_subset_of_what_is_emitted(self) -> None:
        self.assertEqual(sorted(NO_CONTRADICTION_MAPPING - self._emitted()), [])


class PrecedenceEncodesTheL1SpineNotJustTheGateNames(unittest.TestCase):
    """`P8-088`. ``PRECEDENCE``'s own comment says the gate names "are ordered to match that
    spine", and nothing checked the ORDER. CONS-04 (health's gate-token coverage) checks
    membership and mapping only, so moving ``"tier"`` — Gate 1, the classification boundary that
    decides what may leave the vault — from position 3 to the very END of the tuple, below
    ``build``/``pdf``/``run_gates``, left CONS-04 reporting
    ``PASS  all 17 gate(s) ... have a precedence position``. A blocking tier violation would then
    have sorted BELOW every advisory in the list a human reads top-down.
    """

    def test_the_live_spine_holds(self) -> None:
        self.assertEqual(check_precedence_spine(), [])

    def test_the_classes_are_populated_and_disjoint(self) -> None:
        """Vacuity guard: empty classes make every ordering assertion trivially true, and a gate
        in two classes makes "class order" meaningless."""
        seen: set[str] = set()
        for name, members in SPINE_CLASSES:
            self.assertTrue(members, f"class {name} is empty")
            self.assertEqual(seen & members, set(), f"class {name} overlaps an earlier class")
            seen |= members
        self.assertGreater(len(seen), 10)

    def test_demoting_the_classification_gate_to_the_end_is_rejected(self) -> None:
        """The mutation an actual reordering performs — not "the tuple is non-empty"."""
        demoted = tuple(g for g in PRECEDENCE if g != "tier") + ("tier",)
        problems = check_precedence_spine(demoted)
        self.assertTrue(problems)
        self.assertTrue(any("tier" in p for p in problems), problems)

    def test_deleting_the_classification_gate_is_rejected_too(self) -> None:
        """The WIDER input: an unlisted gate gets ``len(PRECEDENCE)`` from ``_precedence_rank``,
        so deleting ``"tier"`` demotes it exactly as far as moving it to the end does. A check
        that only caught reordering would be satisfied by deletion."""
        problems = check_precedence_spine(tuple(g for g in PRECEDENCE if g != "tier"))
        self.assertTrue(any("tier" in p for p in problems), problems)

    def test_slipping_a_security_gate_below_the_registries_is_rejected(self) -> None:
        """The edge AFTER narrowing: a reorder does not have to go all the way to the end. Moving
        ``"secret_value"`` one class down — below ``manifest_drift`` — is still an inversion of
        RULEBOOK L1's security > registries ordering."""
        moved = []
        for gate in PRECEDENCE:
            if gate == "secret_value":
                continue
            moved.append(gate)
            if gate == "manifest_drift":
                moved.append("secret_value")
        problems = check_precedence_spine(tuple(moved))
        self.assertTrue(any("secret_value" in p for p in problems), problems)

    def test_an_unclassified_gate_is_rejected(self) -> None:
        """A new gate added to PRECEDENCE but not to SPINE_CLASSES is a position nobody reviewed."""
        problems = check_precedence_spine((*PRECEDENCE, "brand_new_gate"))
        self.assertTrue(any("brand_new_gate" in p for p in problems), problems)

    def test_a_correct_reordering_within_one_class_is_allowed(self) -> None:
        """Two-sided: the check must not forbid what L1 does not order. Swapping two gates of the
        same class changes nothing about security-vs-advisory ranking."""
        swapped = list(PRECEDENCE)
        i, j = swapped.index("secret_value"), swapped.index("pii_path_internal")
        swapped[i], swapped[j] = swapped[j], swapped[i]
        self.assertEqual(check_precedence_spine(tuple(swapped)), [])

    def test_the_exempt_set_never_names_a_tie_bearing_gate(self) -> None:
        """A gate may declare it needs no L11 tie-breaker only where no tie exists.

        **Rewritten 2026-08-24 (`OG-191`), and the reason matters more than the change.** The
        second assertion here used to be ``NO_CONTRADICTION_MAPPING - (advisory | run-state) ==
        []`` — "only advisory and run-state gates may be exempt". That was a PROXY, true only
        because the exempt set happened to contain nothing else at the time. It is not the
        property: exemption is about whether two laws contend, not about which spine class a gate
        sits in. Seven figure gates (`chart.rule`, `geomap.rule`, `iso3d.bounds`, …) are content
        rules in `visual-rules`, and they emit *"bar chart has no items"*, *"lon outside
        [-180, 180]"*, *"matrix shape must be 3x4"*. No second law wants those accepted, so a
        contradiction row for them could never fire — which `LESSONS.md` L-03 names as a defect,
        not a fix.

        So `visual-rules` is now a MIXED class by evidence, and the proxy is replaced by the two
        assertions that actually carry weight.
        """
        # 1. The classes where a tie ALWAYS exists. `registries` joins the original two here:
        #    `manifest_drift` is a genuine header-vs-registry conflict (row 5), and the old
        #    wording protected it only as a side effect of the proxy it is replacing.
        tie_bearing = (
            dict(SPINE_CLASSES)["source-of-truth"]
            | dict(SPINE_CLASSES)["security"]
            | dict(SPINE_CLASSES)["registries"]
        )
        self.assertEqual(sorted(NO_CONTRADICTION_MAPPING & tie_bearing), [])

        # 2. Stronger than the class proxy, and mechanical: a gate cannot BOTH carry a
        #    contradiction mapping and declare it needs none. This is what actually stops
        #    `figure_provenance` or `wcag_contrast` being quietly exempted out of row 8 or row 9 —
        #    the class proxy never checked that, it only checked where they sat.
        from tools.docgen.adjudication import gate_contradiction_tokens

        mapped = set(gate_contradiction_tokens())
        self.assertEqual(
            sorted(NO_CONTRADICTION_MAPPING & mapped), [],
            "a gate is both mapped to a contradiction row and declared exempt from needing one",
        )

    def test_a_general_visual_rule_gate_can_never_be_exempted(self) -> None:
        """Closes a regression an independent verifier demonstrated (`OG-195`).

        The assertion this class replaced — *only advisory and run-state gates may be exempt* — was
        a blunt allowlist, and replacing it dropped `visual-rules` from the classes that can never
        be silently exempted. A verifier then built the exact counter-example: add
        `figure_provenance` to `NO_CONTRADICTION_MAPPING` **and** delete its entry from
        `gate_contradiction_tokens()` in the same change. The old assertion rejected that; the two
        replacements accepted it, because one checks classes the gate is not in and the other only
        compares the two structures against each other, so a coordinated edit keeps them
        consistent while making CONTRADICTION row 8 permanently unreachable again.

        The property that actually holds: a `visual-rules` gate whose name carries **no dot** is a
        GENERAL rule — `wcag_contrast`, `figure_provenance` — and every general rule has a real tie
        and a real row. A dotted one is scoped to a single figure kind and may legitimately be
        exempt when its messages are pure well-formedness. Derived from the names, so a general
        visual gate added later is covered without editing this test.
        """
        from tools.docgen.adjudication import gate_contradiction_tokens

        general = {g for g in dict(SPINE_CLASSES)["visual-rules"] if "." not in g}
        self.assertTrue(general, "no general visual-rules gate found — has the class been emptied?")
        self.assertEqual(
            sorted(general & NO_CONTRADICTION_MAPPING), [],
            "a general visual rule gate is declared exempt from needing a contradiction row",
        )
        self.assertEqual(
            sorted(general - set(gate_contradiction_tokens())), [],
            "a general visual rule gate has no contradiction mapping, so its row can never fire",
        )

    def test_the_exempt_set_is_not_empty(self) -> None:
        """Vacuity guard: an empty exempt set makes every assertion above trivially true."""
        self.assertTrue(NO_CONTRADICTION_MAPPING)


class HashGateRefusesToVerifyNothing(unittest.TestCase):
    """``rulebook_sha256: PENDING`` means the locked set is UNLOCKED and the gate is comparing
    against nothing. It used to return a non-blocking INFO, so health printed
    ``hash-gate holds — no undeclared rulebook drift`` — a line that was literally false — over a
    rulebook rewritten to carry any rule at all."""

    def test_pending_blocks_when_merely_checking(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            # The WORKING TREE, not `HEAD`. A gate exists to vet what is ABOUT to be committed;
            # a lab built from the last commit cannot see the change under test, so any edit
            # spanning both a checker and its subject failed until it was already committed —
            # backwards, and it cost a debugging pass on 2026-08-23 when the theme writer and
            # its verifier were changed together. `stash create` snapshots the worktree into a
            # dangling object WITHOUT touching the index, the worktree or the stash ref; it
            # returns empty when there is nothing to snapshot, hence the `or "HEAD"`.
            _snap = subprocess.run(["git", "-C", str(_REPO), "stash", "create"],
                                   capture_output=True, text=True, check=False,
                                   timeout=120).stdout.strip()
            tar = subprocess.run(["git", "-C", str(_REPO), "archive", _snap or "HEAD"],
                                 check=True, capture_output=True).stdout
            subprocess.run(["tar", "-x", "-C", str(work)], input=tar, check=True)
            vj = work / "docs" / "design" / "doc-system" / "VERSION.json"
            data = json.loads(vj.read_text(encoding="utf-8"))
            data["rulebook_sha256"] = "PENDING"
            vj.write_text(json.dumps(data, indent=2), encoding="utf-8")
            proc = subprocess.run(
                ["python3", "-m", "tools.docgen.validate_doc_system"],
                cwd=work, capture_output=True, text=True, timeout=120, check=False,
            )
            self.assertNotEqual(proc.returncode, 0,
                                "a PENDING sentinel must BLOCK on a plain check")
            self.assertIn("PENDING", proc.stdout + proc.stderr)


class CacheKeyIsSensitiveToEveryInputThatChangesOutput(unittest.TestCase):
    """A cache hit synthesises a PASSING result and skips the build, so anything outside the key is
    free to change without invalidating anything. Five wrong-hit classes were proven under v1 and
    four more under v3."""

    def _key(self, **over: object) -> str:
        base: dict[str, object] = {
            "formats": ("html",),
            "local_preview": False,
            "engine_fingerprint": "E",
            "rule_layer_fingerprint": "R",
            "out_dir": None,
        }
        base.update(over)
        return build_cache.compute_key(_REPO / "tools" / "docgen" / "sample.md", **base)  # type: ignore[arg-type]

    def test_baseline_is_stable(self) -> None:
        self.assertEqual(self._key(), self._key())

    def test_engine_fingerprint_changes_the_key(self) -> None:
        self.assertNotEqual(self._key(), self._key(engine_fingerprint="E2"))

    def test_rule_layer_fingerprint_changes_the_key(self) -> None:
        """The rule layer was OUTSIDE the key: editing DOC_MANIFEST.md to make a document illegal
        left it building green from cache."""
        self.assertNotEqual(self._key(), self._key(rule_layer_fingerprint="R2"))

    def test_out_dir_changes_the_key(self) -> None:
        """Building the same source into a different ``-o`` with a shared cache reported a
        successful skip and wrote NOTHING to the requested directory."""
        self.assertNotEqual(self._key(), self._key(out_dir=_REPO / ".docgen" / "elsewhere"))

    def test_formats_change_the_key(self) -> None:
        self.assertNotEqual(self._key(), self._key(formats=("html", "json")))

    def test_local_preview_changes_the_key(self) -> None:
        self.assertNotEqual(self._key(), self._key(local_preview=True))

    def test_renderer_fingerprint_covers_the_out_of_tree_engines(self) -> None:
        """mermaid and ECharts figures render OUTSIDE tools/docgen. Editing either changed the built
        bytes but not the key, so ``--cached`` served a stale artifact under a success message."""
        fp = build_cache._renderer_fingerprint()
        self.assertRegex(fp, r"^[0-9a-f]{64}$")
        self.assertEqual(fp, build_cache._renderer_fingerprint(), "must be deterministic")


class CacheKeyCoversTheINPUTSNotJustTheFlags(unittest.TestCase):
    """`P8-046`. The class above tests six inputs through a ``_key()`` helper that hardcodes five
    fields — and ``compute_key`` composes EIGHT. The three it never touched are the three that
    actually change the built bytes: the ``_CACHE_FORMAT`` tag, the **source markdown's own
    bytes**, and the **sibling ``_spec.json``**. Measured: severing
    ``hasher.update(md_path.read_bytes())`` to a no-op left the whole class green — ``Ran 7 tests
    ... OK`` — with the document's content contributing nothing to its own cache key.

    These call ``compute_key`` directly against real files on disk, because the defect lives in
    what the function READS, which a helper that passes only keyword flags can never reach.
    """

    def _fixture(self, tmp: Path, *, body: str = "# doc\n", spec: str | None = None) -> Path:
        md = tmp / "doc.md"
        md.write_text(body, encoding="utf-8")
        if spec is not None:
            (tmp / "doc_spec.json").write_text(spec, encoding="utf-8")
        return md

    def _key(self, md: Path) -> str:
        return build_cache.compute_key(
            md, formats=("html",), local_preview=False,
            engine_fingerprint="E", rule_layer_fingerprint="R", out_dir=None,
        )

    def test_the_same_file_keys_the_same_twice(self) -> None:
        """Vacuity guard: a key that changed on every call would satisfy every assertion below."""
        with tempfile.TemporaryDirectory() as td:
            md = self._fixture(Path(td))
            self.assertEqual(self._key(md), self._key(md))

    def test_editing_the_source_changes_the_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            md = self._fixture(Path(td), body="# doc\noriginal\n")
            before = self._key(md)
            md.write_text("# doc\nrewritten\n", encoding="utf-8")
            self.assertNotEqual(before, self._key(md))

    def test_a_whitespace_only_source_edit_changes_the_key(self) -> None:
        """The edge after narrowing: the key hashes RAW BYTES, so there is no normalisation step
        in which a "cosmetic" edit could slip past."""
        with tempfile.TemporaryDirectory() as td:
            md = self._fixture(Path(td), body="# doc\ntext\n")
            before = self._key(md)
            md.write_text("# doc\ntext \n", encoding="utf-8")
            self.assertNotEqual(before, self._key(md))

    def test_editing_the_sibling_spec_sidecar_changes_the_key(self) -> None:
        """A figure's geometry lives entirely in the sidecar. Outside the key, editing it left
        ``--cached`` serving the previous diagram under a success message."""
        with tempfile.TemporaryDirectory() as td:
            md = self._fixture(Path(td), spec='{"id": "F1", "title": "a"}')
            before = self._key(md)
            (Path(td) / "doc_spec.json").write_text('{"id": "F1", "title": "b"}', encoding="utf-8")
            self.assertNotEqual(before, self._key(md))

    def test_adding_a_sidecar_where_there_was_none_changes_the_key(self) -> None:
        """The other half of the sidecar edge: absent-vs-present must not hash the same, or a
        document that GAINS figures rebuilds from a cache entry that has none."""
        with tempfile.TemporaryDirectory() as td:
            md = self._fixture(Path(td))
            before = self._key(md)
            (Path(td) / "doc_spec.json").write_text('{"id": "F1"}', encoding="utf-8")
            self.assertNotEqual(before, self._key(md))

    def test_the_cache_format_tag_is_in_the_key(self) -> None:
        """The tag is how a cache-layout change invalidates every pre-existing entry. Outside the
        key, a v3 reader would happily serve a v2 entry it cannot interpret."""
        with tempfile.TemporaryDirectory() as td:
            md = self._fixture(Path(td))
            before = self._key(md)
            original = build_cache._CACHE_FORMAT
            try:
                build_cache._CACHE_FORMAT = "docgen-build-cache/v-probe"
                self.assertNotEqual(before, self._key(md))
            finally:
                build_cache._CACHE_FORMAT = original
            self.assertEqual(before, self._key(md), "the probe must leave no residue")

    def test_every_field_compute_key_hashes_is_exercised_by_this_file(self) -> None:
        """The reason P8-046 existed: the suite tested five of eight inputs and nothing measured
        the gap. Derived from the source with ``ast`` — a substring scan of ``compute_key``'s body
        would match its own parameter list (LESSONS.md L-24)."""
        tree = ast.parse(Path(build_cache.__file__).read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "compute_key")
        hashed = [
            ast.unparse(node.value.args[0])
            for node in ast.walk(fn)
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and ast.unparse(node.value.func) == "hasher.update"
            and ast.unparse(node.value.args[0]) != "b'\\x00'"
        ]
        self.assertGreaterEqual(len(hashed), 8, hashed)
        source = Path(__file__).read_text(encoding="utf-8")
        for probe in ("_CACHE_FORMAT", "read_bytes", "_spec.json", "formats",
                      "local_preview", "out_dir", "engine_fingerprint",
                      "rule_layer_fingerprint"):
            self.assertIn(probe, source, f"no test in this file exercises {probe}")


class CacheVerifiesWhatItWroteNotJustWhere(unittest.TestCase):
    """The entry recorded WHERE a build wrote, never WHAT it wrote.

    Any out-of-band change to a built artifact — an edit, a truncation, another tool writing to the
    same path — survived a cached run reported as success, with the export sanitizer never re-run
    over the bytes actually on disk.
    """

    def test_a_fresh_entry_carries_a_digest_per_output(self) -> None:
        entry = build_cache.CacheEntry(key="k", outputs={"html": "a.html"}, digests={"html": "d"})
        self.assertEqual(entry.digests["html"], "d")

    def test_an_entry_without_digests_is_never_fresh(self) -> None:
        """Entries written before digests existed must degrade to a MISS, not to a false hit."""
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "a.html"
            out.write_text("x", encoding="utf-8")
            rel = str(out)
            legacy = build_cache.CacheEntry(key="k", outputs={"html": rel})
            self.assertFalse(build_cache._entry_is_fresh(legacy, "k"))

    def test_a_tampered_output_is_not_fresh(self) -> None:
        import hashlib

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "a.html"
            out.write_text("original", encoding="utf-8")
            digest = hashlib.sha256(out.read_bytes()).hexdigest()
            entry = build_cache.CacheEntry(key="k", outputs={"html": str(out)},
                                           digests={"html": digest})
            self.assertTrue(build_cache._entry_is_fresh(entry, "k"), "baseline must be fresh")
            out.write_text("tampered", encoding="utf-8")
            self.assertFalse(build_cache._entry_is_fresh(entry, "k"))

    def test_a_deleted_output_is_not_fresh(self) -> None:
        entry = build_cache.CacheEntry(key="k", outputs={"html": "/nonexistent/a.html"},
                                       digests={"html": "d"})
        self.assertFalse(build_cache._entry_is_fresh(entry, "k"))

if __name__ == "__main__":  # pragma: no cover
    unittest.main()
