"""Counter-examples for the doc-system header parser and the L14 placement decision.

Every case here was a real defect found by an adversarial verifier, not a hypothetical.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from collections.abc import Callable

from tools.docgen import classification
from tools.docgen.classification import _FRONT_MATTER_RE, parse_header
from tools.docgen.hooks.staged_content_scanner import classify_file
from tools.docgen.models import Tier

_YAML = (
    "---\n"
    "id: TST-001\ntitle: t\nclassification: {tier}\nsurface: {surface}\n"
    "audience: a\nowner: o\nstatus: draft\nlast_reviewed: 2026-08-21\n"
    "---\n\n# body\n"
)


def _doc(tier: str = "secret", surface: str = "none", prefix: str = "") -> str:
    return prefix + _YAML.format(tier=tier, surface=surface)


def _repo(case: unittest.TestCase, *, vault_ignored: bool) -> pathlib.Path:
    """A throwaway git repository whose vault is (or is not) actually git-ignored.

    ``classify_file`` needs a repository because the `OG-167` vault anchor is git's ignore rules —
    and since the F5 fix it needs the repository it was *given*, not one derived from the CWD. So
    the placement cases below name their repository explicitly instead of inheriting the test
    runner's working directory, which is what let the anchor and the scanned blobs disagree.
    """
    root = pathlib.Path(tempfile.mkdtemp(prefix="classify_repo_"))
    case.addCleanup(shutil.rmtree, root, True)
    subprocess.run(("git", "init", "-q", "."), cwd=root, check=True)
    if vault_ignored:
        (root / ".gitignore").write_text("docs/confidential/\n", encoding="utf-8")
    return root


class FrontMatterAnchoring(unittest.TestCase):
    """The fence must be found behind the things that really precede it in this tree.

    The pattern was anchored at byte 0 without ``re.MULTILINE``, so a single leading HTML comment —
    the house style of every process document here — made a document parse as HEADER-LESS and the
    placement gate skipped it entirely.
    """

    def test_plain_front_matter_is_found(self) -> None:
        self.assertIsNotNone(_FRONT_MATTER_RE.search(_doc()))

    def test_found_behind_one_leading_html_comment(self) -> None:
        self.assertIsNotNone(_FRONT_MATTER_RE.search(_doc(prefix="<!-- title: X -->\n")))

    def test_found_behind_several_leading_comments(self) -> None:
        self.assertIsNotNone(_FRONT_MATTER_RE.search(_doc(prefix="<!-- a -->\n<!-- b -->\n")))

    def test_found_behind_a_utf8_bom(self) -> None:
        self.assertIsNotNone(_FRONT_MATTER_RE.search(_doc(prefix="﻿")))

    def test_absent_when_there_is_no_fence(self) -> None:
        self.assertIsNone(_FRONT_MATTER_RE.search("# just a readme\n"))


class FrontMatterAnchoringIsNotRedosVulnerable(unittest.TestCase):
    """Regression for CodeQL ``py/redos``.

    ``(?:[ \\t]*<!--.*?-->[ \\t]*\\r?\\n(?:[ \\t]*\\r?\\n)*)*`` nested a lazy ``.*?`` (DOTALL, so it
    spans newlines) inside an outer ``*``-repeated group. A run of many ``<!--...-->`` blocks with
    no terminating ``---`` fence gave the backtracker exponentially many equivalent ways to carve
    up the input before concluding failure — confirmed by hand: the pre-fix pattern took >8s on
    fewer than 40 repetitions of ``<!-- x -->\\n``. The fix replaces the inner ``.*?`` with a
    tempered-dot token ``(?:(?!-->).)*``, which matches the identical shortest span up to the first
    ``-->`` but cannot backtrack across iteration boundaries. Every case in ``FrontMatterAnchoring``
    above still passes unchanged; this class only adds the adversarial-performance guarantee.
    """

    def test_many_unterminated_comments_do_not_hang(self) -> None:
        evil = "<!-- x -->\n" * 3000
        start = time.monotonic()
        matched = _FRONT_MATTER_RE.search(evil)
        elapsed = time.monotonic() - start
        self.assertIsNone(matched)
        self.assertLess(elapsed, 0.5, f"took {elapsed:.3f}s — regex may have regressed to O(2^n)")

    def test_50kb_adversarial_input_is_linear_time(self) -> None:
        evil = ("<!-- x -->\n" * 2000) + ("a" * 50_000)
        start = time.monotonic()
        matched = _FRONT_MATTER_RE.search(evil)
        elapsed = time.monotonic() - start
        self.assertIsNone(matched)
        self.assertLess(elapsed, 0.5, f"took {elapsed:.3f}s on a 50KB adversarial input")

    def test_legitimate_large_document_still_matches_fast(self) -> None:
        # A realistic case: many real (well-formed) leading comments, then a real fence. Must
        # still match, and must still be fast — the fix must not have narrowed the language.
        prefix = "<!-- note -->\n" * 500
        text = prefix + _doc()
        start = time.monotonic()
        matched = _FRONT_MATTER_RE.search(text)
        elapsed = time.monotonic() - start
        self.assertIsNotNone(matched)
        self.assertLess(elapsed, 0.5, f"took {elapsed:.3f}s on 500 legitimate leading comments")


class AbruptClosingCommentsCannotBypassThePlacementGate(unittest.TestCase):
    """Regression for an independent verifier's findings (round 2 of the CodeQL ``py/redos`` fix).

    The first ReDoS fix for ``_FRONT_MATTER_RE`` replaced the lazy ``<!--.*?-->`` with a tempered
    dot ``<!--(?:(?!-->).)*-->``. That token is NOT equivalent: lazy ``.*?`` can backtrack past a
    ``-->`` it already tried, to a LATER one, if the rest of the pattern then fails; the tempered
    dot commits to the FIRST ``-->`` with no way back. HTML's degenerate "abrupt-closing" comment
    forms — ``<!-->`` (4 chars) and ``<!--->`` (5 chars) — share dashes between their own open and
    close, so a run of them needs exactly that backtracking to parse as separate comments. Measured
    (round 1 verifier, 9,050 inputs): 24 real narrowings, all on these two forms, split evenly,
    for every ODD count >= 3 of ``<!--->`` (and its ``<!-->`` twin) preceding a real fence — EVEN
    counts and single occurrences of the WELL-FORMED ``<!-- ... -->`` were never affected.

    Consequence: `classify_file` on a `classification: secret` document prefixed with e.g. three
    ``<!--->`` returned a blocking Finding at base ``1.0.12`` (front matter WAS found) but ``None``
    — a silent, complete bypass of the vault-placement gate — at the first fix commit
    ``66e71ff0``. `classify_file`'s own fail-open contract (`if not _has_doc_header(text): return
    None`) makes a missed header equivalent to "nothing here to protect".

    The fix (round 2): ``<!--(?:-?>|(?!-?>)(?:(?!-->).)*-->)`` — the abrupt-closing forms
    get their OWN alternative branch, matched in one deterministic step, so the general tempered-dot
    branch is only ever tried on genuinely well-formed comments (guarded by ``(?!-?>)`` so the two
    branches never both apply — that mutual exclusion is what keeps it linear; two "simplified"
    variants without it were measured to reintroduce catastrophic backtracking, >6s at 200 reps).
    As a side effect this ALSO closes two holes that existed at base 1.0.12 already: a
    SINGLE ``<!--->`` or ``<!-->`` before a secret header committed clean even before this branch's
    own history began — differential testing over 17,888 synthetic + 241 real repo documents found
    zero base matches lost, 24 gained (all instances of exactly these two pre-existing holes), zero
    divergent captures on any mutual hit.
    """

    def setUp(self) -> None:
        self.repo = _repo(self, vault_ignored=True)

    def _assert_refused(self, text: str, label: str) -> None:
        found = classify_file("docs/x.md", text, self.repo)
        self.assertIsNotNone(found, f"{label}: classified document committed CLEAN (bypass)")
        assert found is not None
        self.assertTrue(found.blocking, f"{label}: finding was not blocking")

    def test_five_char_abrupt_comment_n_1_to_4(self) -> None:
        for n in (1, 2, 3, 4):
            with self.subTest(n=n):
                text = "<!--->\n" * n + _doc(tier="secret")
                self._assert_refused(text, f"N={n} x <!--->")

    def test_four_char_abrupt_comment_n_1_to_4(self) -> None:
        for n in (1, 2, 3, 4):
            with self.subTest(n=n):
                text = "<!-->\n" * n + _doc(tier="secret")
                self._assert_refused(text, f"N={n} x <!-->")

    def test_mixed_abrupt_and_well_formed_comments(self) -> None:
        text = "<!-- x -->\n<!--->\n<!-->\n<!--->\n" + _doc(tier="secret")
        self._assert_refused(text, "mixed <!-- x -->/<!--->/<!-->")

    def test_leading_whitespace_before_the_legacy_marker_is_pinned(self) -> None:
        """Not this branch's regression (the `_LEGACY_` hoist fixed it, round 1) — pinned here so a
        future change to either regex cannot silently reopen it. Commits clean at base 1.0.12;
        refused from the round-1 `_LEGACY_CLASSIFICATION_RE` fix onward.
        """
        text = "  <!-- classification: secret -->\n"
        self._assert_refused(text, "leading-whitespace legacy marker")

    def test_new_comment_token_adversarial_timing(self) -> None:
        evil = "<!--->\n" * 2000
        start = time.monotonic()
        matched = _FRONT_MATTER_RE.search(evil)
        elapsed = time.monotonic() - start
        self.assertIsNone(matched)
        self.assertLess(
            elapsed, 0.05, f"took {elapsed:.4f}s on 2000x <!---> — mutual-exclusion guard lost?"
        )


class TierCoercion(unittest.TestCase):
    def test_unparseable_tier_degrades_to_secret_not_public(self) -> None:
        self.assertIs(parse_header(_doc(tier="nonsense-tier")).classification, Tier.SECRET)

    def test_headerless_document_parses_as_secret(self) -> None:
        """Fail-closed for the RENDER gate. The placement gate must NOT block on it — see below."""
        self.assertIs(parse_header("# ordinary readme\n").classification, Tier.SECRET)

    def test_yaml_wins_over_a_legacy_comment_that_disagrees(self) -> None:
        """A leading ``<!-- classification: public -->`` over YAML saying ``secret`` used to pass
        on the COMMENT's word, because the comment made the YAML invisible."""
        text = _doc(tier="secret", prefix="<!-- classification: public -->\n")
        self.assertIs(parse_header(text).classification, Tier.SECRET)


class PlacementDecision(unittest.TestCase):
    """``classify_file`` is the single decision behind BOTH the commit-time and push-time gates."""

    def setUp(self) -> None:
        # The ordinary shape: a repository that really does keep its vault out of git.
        self.repo = _repo(self, vault_ignored=True)

    def test_public_document_outside_the_vault_is_allowed(self) -> None:
        self.assertIsNone(
            classify_file("docs/x.md", _doc(tier="public", surface="web"), self.repo)
        )

    def test_secret_document_outside_the_vault_is_blocked(self) -> None:
        found = classify_file("docs/x.md", _doc(tier="secret"), self.repo)
        self.assertIsNotNone(found)
        assert found is not None
        self.assertTrue(found.blocking)

    def test_headerless_readme_outside_the_vault_is_allowed(self) -> None:
        """The render gate reads header-less input as secret; the PLACEMENT gate must not, or every
        ordinary README in the tree becomes a blocking finding."""
        self.assertIsNone(classify_file("README.md", "# ordinary readme\n", self.repo))

    def test_legacy_comment_saying_public_is_allowed(self) -> None:
        self.assertIsNone(
            classify_file("x.md", "<!-- classification: public -->\n\n# x\n", self.repo)
        )

    def test_legacy_comment_with_a_foreign_vocabulary_is_refused(self) -> None:
        """``INTERNAL``/``GITHUB`` come from the project this engine was extracted from and are not
        tiers here. Refusing beats guessing: an author writing ``secret`` in this syntax believed
        they were protected and were not."""
        for value in ("secret", "INTERNAL", "GITHUB", "confidential"):
            with self.subTest(value=value):
                found = classify_file(
                    "x.md", f"<!-- classification: {value} -->\n\n# x\n", self.repo
                )
                self.assertIsNotNone(found, f"{value!r} must not be treated as public")

    def test_secret_document_INSIDE_the_vault_is_allowed(self) -> None:
        self.assertIsNone(classify_file("docs/confidential/x.md", _doc(tier="secret"), self.repo))

    def test_the_vault_is_read_from_the_repository_the_caller_NAMED(self) -> None:
        """F5 at the decision level: the SAME path, the SAME bytes, two repositories, two verdicts.

        `is_inside_confidential_dir` used to consult ``_repo_root_default()`` — the CWD's git root —
        so this pair was decided by where the process happened to be standing rather than by the
        repository whose blobs were being read. Before the fix both of these returned ``None``
        whenever the test runner's own CWD had a git-ignored vault, which it does.
        """
        committed_vault = _repo(self, vault_ignored=False)
        found = classify_file("docs/confidential/x.md", _doc(tier="secret"), committed_vault)
        self.assertIsNotNone(
            found,
            "a 'vault' that git would happily commit is not a vault (OG-167) — and the answer must "
            "come from the repository passed in, not from the process's working directory",
        )
        # Control, in the same test, so a fix that simply refuses everything cannot pass it.
        self.assertIsNone(classify_file("docs/confidential/x.md", _doc(tier="secret"), self.repo))


class BothPlacementScanPathsShareOneDecoder(unittest.TestCase):
    """`OG-84` — the defect was never "UTF-16 is unreadable". It was **two decoders**.

    `materialise.normalise_for_scanning` already existed and was wired into the *secret* path of
    the same hook, reading the same blobs, and `OPEN_GATES.md` recorded the class as "closed at the
    ROOT". It was closed for one of two consumers: both placement scan paths still did a bare
    `data.decode("utf-8")` inside a `try` whose `except UnicodeDecodeError` body was `continue`, so
    a `classification: secret` document written as UTF-16 decoded to nothing, was skipped, and
    committed and pushed clean.

    A probe that exercises one call site cannot see that. This one asserts the STRUCTURAL property
    the fix established — every scan path routes through the one decoder — derived from the source,
    so a third scan path added later is covered the day it is written.
    """

    def test_no_scan_path_decodes_bytes_on_its_own(self) -> None:
        import inspect
        from typing import Any

        from tools.docgen.hooks import staged_content_scanner

        paths: list[Callable[..., Any]] = [
            staged_content_scanner.scan_manifest,
            staged_content_scanner.scan_staged,
        ]
        for fn in paths:
            with self.subTest(scan_path=fn.__name__):
                source = inspect.getsource(fn)
                self.assertIn(
                    "_decode_for_scanning", source,
                    f"{fn.__name__} does not route through the shared decoder",
                )
                self.assertNotIn(
                    '.decode("utf-8")', source,
                    f"{fn.__name__} decodes bytes itself — that is the second decoder OG-84 was "
                    "about, reintroduced",
                )

    def test_every_scan_path_in_the_module_is_covered_by_the_probe_above(self) -> None:
        """Derived, so a third scan path cannot be added without this test noticing.

        The probe above names two functions. If the module grows a third `scan_*`, naming two would
        quietly stop being "every scan path" — the exact shape of the original defect, applied to
        its own counter-example.
        """
        from tools.docgen.hooks import staged_content_scanner

        found = sorted(
            name for name in dir(staged_content_scanner)
            if name.startswith("scan_") and callable(getattr(staged_content_scanner, name))
        )
        self.assertEqual(
            found, ["scan_manifest", "scan_staged"],
            f"the module's scan paths changed to {found}; update "
            "test_no_scan_path_decodes_bytes_on_its_own to cover all of them",
        )

class PlacementScopeIsNotFilenameOnly(unittest.TestCase):
    """`OG-213` — the placement filter is a DENYLIST, not an allowlist, and the direction is the fix.

    Authority is the header, not the filename. The old allowlist skipped anything but nine document
    suffixes, so a `classification: secret` document saved as `notes.mkd` (a standard Markdown alias)
    or with no extension reached the remote through both gates. Now content decides for every file
    except the structured-data formats a prose document is never written in (`OG-41`).
    """

    def test_documents_and_the_aliases_the_allowlist_missed_are_in_scope(self) -> None:
        from tools.docgen.hooks.staged_content_scanner import (
            _might_carry_classification,
        )

        # The old allowlist covered the first row; BREACH #1 was the second and third.
        in_scope = (
            ".md", ".markdown", ".txt", ".rst", ".adoc", ".mdx", ".org", ".html",
            ".mkd", ".mdown", ".mkdn", ".mdwn", ".mkdown", ".litcoffee", ".text",  # Markdown aliases
        )
        for ext in in_scope:
            with self.subTest(ext=ext):
                self.assertTrue(_might_carry_classification(f"notes{ext}"), f"{ext} must be in scope")
        # A no-extension file is the sharpest case — no suffix at all, and it was invisible.
        self.assertTrue(_might_carry_classification("architecture-notes"))
        self.assertTrue(_might_carry_classification("README"))

    def test_structured_data_formats_stay_out_of_scope(self) -> None:
        """`OG-41`'s decision, preserved: a `.yaml`/`.json`/`.csv` opens with `---`/`key: value` and
        is not a prose document. It is the ONE thing the denylist spares — everything else is read,
        and a binary is rejected downstream by content, not by its suffix."""
        from tools.docgen.hooks.staged_content_scanner import (
            _might_carry_classification,
        )

        for ext in (".yaml", ".yml", ".json", ".csv", ".tsv", ".toml", ".ini", ".cfg", ".lock"):
            with self.subTest(ext=ext):
                self.assertFalse(_might_carry_classification(f"data{ext}"))
        # A binary is NOT excluded by suffix any more — the content decoder rejects it (cheaply). The
        # end-to-end proof that a `.png` produces no finding is in test_staged_scanner.py's breach
        # class; here we only assert the suffix filter no longer pretends to know a file is binary.
        for ext in (".png", ".woff2", ".zip", ".pyc"):
            with self.subTest(ext=ext):
                self.assertTrue(_might_carry_classification(f"asset{ext}"))


class PlacementGateIsEncodingBlind(unittest.TestCase):
    """`OG-84` — a UTF-16 classified document must be refused exactly like its UTF-8 twin.

    **The defect:** both scan paths in `staged_content_scanner` did a bare `decode("utf-8")` inside
    a `try` whose `except UnicodeDecodeError` body was `continue`, so a `classification: secret`
    document written as UTF-16 (Notepad "Unicode", PowerShell redirection) decoded to nothing, was
    skipped, and **committed and pushed clean**. The root fix already existed —
    `materialise.normalise_for_scanning` — and had been wired into the *secret* path in the same
    hook, reading the same blobs, while `OG-56` recorded the class as "closed at the ROOT".

    Two-sided and encoding-parametrised, because the whole defect was a fix applied to one consumer
    of a shared root: the SAME document text must be refused in every encoding a real author emits.
    """

    _DOC = (
        "---\nid: SPEC-900\nclassification: secret\ntitle: leak\nsurface: none\n"
        "audience: internal\nowner: x\nstatus: draft\nexport_allowed: false\n"
        "last_reviewed: 2026-08-22\n---\n\n# leak\n\nbody\n"
    )

    # **WIRE FORMS, not codec names — and the distinction is the entire finding.**
    #
    # The previous version parametrised over `("utf-8","utf-16","utf-16-le","utf-16-be","utf-32")`
    # and called that "the class, not the instance". It was not: Python's `"utf-16"` and `"utf-32"`
    # codecs EMIT A BOM, so every multi-byte case it tested was a BOM-carrying one — and the
    # BOM-less UTF-32 shape, the one that actually walked a `classification: secret` document AND an
    # AWS-key-shaped credential into history, was never exercised at all. Four Pass-7 agents found
    # it independently (`OG-95`).
    #
    # A wire form is what a real editor writes to disk. BOM-less is spelled out explicitly so it
    # cannot silently disappear again.
    _WIRE_FORMS: tuple[tuple[str, Callable[[str], bytes]], ...] = (
        ("utf-8", lambda d: d.encode("utf-8")),
        ("utf-8 with BOM", lambda d: b"\xef\xbb\xbf" + d.encode("utf-8")),
        ("utf-16-le with BOM", lambda d: d.encode("utf-16")),
        ("utf-16-le NO BOM", lambda d: d.encode("utf-16-le")),
        ("utf-16-be NO BOM", lambda d: d.encode("utf-16-be")),
        ("utf-32-le with BOM", lambda d: d.encode("utf-32")),
        ("utf-32-le NO BOM", lambda d: d.encode("utf-32-le")),
        ("utf-32-be NO BOM", lambda d: d.encode("utf-32-be")),
        ("cp1252 stray byte", lambda d: d.encode("utf-8") + b"quote\x92s\n"),
        ("latin-1 nbsp", lambda d: d.encode("utf-8") + b"\xa0more\n"),
        ("stray 0xFF", lambda d: d.encode("utf-8") + b"\xff\n"),
    )

    def test_every_WIRE_FORM_of_the_same_classified_document_stays_readable(self) -> None:
        """`_decode_for_scanning` feeds the PLACEMENT gate, whose front-matter regex is `\\A`-anchored,
        so a wide-encoded document's header must survive decoding **at the start**.

        The two moat decoders now DIFFER by design for wide encodings (`OG-213`): the additive buffer
        `normalise_for_scanning` returns is right for the SECRET grep — a position-blind union — but
        it puts the header AFTER the raw wide bytes' mojibake, where the `\\A`-anchored placement gate
        cannot see it, which is exactly the residual a verifier walked a UTF-16 `classification:
        secret` document through. So `_decode_for_scanning` decodes a wide blob CLEANLY, and this
        probe asserts the header is reachable by the placement gate (`_has_doc_header`), not that the
        two decoders produce identical bytes. The secret path's union is checked separately in
        `test_a_secret_stays_visible_in_every_wire_form`.
        """
        from tools.docgen.hooks.staged_content_scanner import (
            _decode_for_scanning,
            _has_doc_header,
        )

        for label, encode in self._WIRE_FORMS:
            with self.subTest(wire_form=label):
                raw = encode(self._DOC)
                text = _decode_for_scanning(raw)
                self.assertIsNotNone(text, f"{label}: decoded to nothing — the gate would skip it")
                assert text is not None
                self.assertIn(
                    "classification: secret", text,
                    f"{label}: the header the gate matches on did not survive decoding",
                )
                self.assertTrue(
                    _has_doc_header(text),
                    f"{label}: the front-matter header is not at the START of the placement decode, "
                    "so the `\\A`-anchored placement gate would read it as a header-less README "
                    "(`OG-213`: the additive buffer's mojibake prefix was the hole)",
                )

    def test_a_secret_stays_visible_in_every_wire_form(self) -> None:
        """The other moat scanner reads the same bytes, and BOM-less UTF-32 defeated it too.

        A live-shaped AWS key entered history in a Pass-7 lab under the hook's own affirmative
        message *"transcoded for scanning … (utf-16-le)"* — a **false affirmative**, which is worse
        than a silent miss because an auditor reads it as the defence working.
        """
        from tools.docgen.hooks.materialise import normalise_for_scanning

        # Split exactly as `test_materialise.py` does, so this file is not itself a
        # scannable secret — the repository's own pre-commit gate refuses the literal,
        # which is the gate working. AWS's published documentation example key.
        key = "AKIA" + "IOSFODNN7EXAMPLE"
        secret = f"aws_access_key_id = {key}\n" * 3
        for label, encode in self._WIRE_FORMS:
            with self.subTest(wire_form=label):
                readable = normalise_for_scanning(encode(secret))[0]
                self.assertIn(b"AKIA", readable, f"{label}: the secret is invisible to a scanner")

    def test_the_detector_names_the_encoding_it_actually_transcoded(self) -> None:
        """`OG-95`: a BOM-less UTF-32 blob was reported as `utf-16-le` on the hook's own stderr."""
        from tools.docgen.hooks.materialise import looks_utf16_or_32

        for label, codec in (("utf-32-le NO BOM", "utf-32-le"), ("utf-32-be NO BOM", "utf-32-be")):
            with self.subTest(wire_form=label):
                self.assertEqual(looks_utf16_or_32(self._DOC.encode(codec)), codec)


    def test_genuinely_binary_content_is_still_skipped(self) -> None:
        """The other side: a PNG is not a document, and must not become a finding."""
        from tools.docgen.hooks.staged_content_scanner import _decode_for_scanning

        png = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4
        self.assertIsNone(_decode_for_scanning(png))


# --- the header CONTRACT: required fields, and the types they must have -------------------------

_COMPLETE_HEADER: dict[str, object] = {
    "id": "TST-001",
    "classification": "public",
    "title": "t",
    "audience": "a",
    "owner": "o",
    "status": "draft",
    "export_allowed": True,
    "surface": "web",
    "last_reviewed": "2026-08-21",
}


def _yaml_scalar(value: object) -> str:
    """Render one value the way an author would write it, so its TYPE survives the round trip.

    Strings are QUOTED (so ``"true"`` stays a string rather than becoming a bool — the whole point
    of the P8-094 cases below), bools and ints are bare, and a ``datetime.date`` is written bare
    so YAML parses it back into a date, which is how a correctly-authored ``last_reviewed`` looks.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, datetime.date)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_yaml_scalar(item) for item in value) + "]"
    return json.dumps(str(value))


def _header_doc(fields: dict[str, object]) -> str:
    """Serialise ``fields`` as front matter — never a hand-built string per test, so every case
    below differs from the control in exactly the one field it names."""
    body = "".join(f"{key}: {_yaml_scalar(value)}\n" for key, value in fields.items())
    return "---\n" + body + "---\n\n# body\n"


class EveryRequiredFieldIsActuallyRequired(unittest.TestCase):
    """`P8-096`. ``_REQUIRED_FIELDS`` had exactly one consumer and no test: emptying it to ``()``
    left ``python3 -m unittest tools.tests.test_classification`` green. Worse, three of the nine
    could not be enforced even with the list intact — ``classification``, ``surface`` and
    ``export_allowed`` have fail-closed placeholders (``SECRET`` / ``NONE`` / ``False``) whose
    TYPE is valid, so ``_field_present`` answered "present" for a field the author never wrote.

    The list is iterated at run time rather than restated here: a test that hardcodes the nine
    names is a second copy of the thing it is checking (docs/process/RULES.md Rule 2).
    """

    def test_the_required_list_is_populated(self) -> None:
        """Vacuity guard — this is the exact mutation that went undetected."""
        self.assertGreaterEqual(len(classification._REQUIRED_FIELDS), 5)

    def test_the_required_set_covers_every_field_the_locked_law_names(self) -> None:
        """The edge the vacuity guard alone leaves open: emptying the tuple is caught, but
        *narrowing* it from nine names to six is not — the loop below would then iterate six and
        pass. So the floor is derived from an INDEPENDENT source: ``CLASSIFICATION.md``'s own
        "Required fields:" sentence, in a file inside ``VERSION.json``'s hash-locked set, which
        cannot be edited to match without the L9 two-step.

        (``export_allowed`` is deliberately NOT asserted here: the law's sentence omits it while
        the code requires it. The code is the stricter of the two, so this test asserts the law as
        a FLOOR, not as an equality — and the discrepancy is stated rather than papered over.)
        """
        law = pathlib.Path(__file__).resolve().parents[2] / "docs" / "design" / "doc-system"
        text = (law / "CLASSIFICATION.md").read_text(encoding="utf-8")
        # up to the first sentence end: the list itself contains no periods, and the prose
        # that follows it mentions `header`, which would otherwise read as a tenth field name.
        match = re.search(r"\*\*Required fields:\*\*([^.]*)", text)
        self.assertIsNotNone(match, "CLASSIFICATION.md no longer names its required fields")
        sentence = match.group(1) if match else ""
        named = re.findall(r"`([a-z_]+)`", sentence)
        self.assertGreaterEqual(len(named), 8, f"vacuity guard: parsed {named!r}")
        self.assertEqual(sorted(set(named) - set(classification._REQUIRED_FIELDS)), [])

    def test_a_complete_header_is_accepted(self) -> None:
        """The positive control. Without it, a validator that blocked everything would pass every
        assertion below."""
        doc = _header_doc(_COMPLETE_HEADER)
        findings = classification.validate_header(classification.parse_header(doc), source=doc)
        self.assertEqual([f.message for f in findings], [])

    def test_removing_any_single_required_field_blocks_and_names_it(self) -> None:
        for field in classification._REQUIRED_FIELDS:
            with self.subTest(field=field):
                doc = _header_doc({k: v for k, v in _COMPLETE_HEADER.items() if k != field})
                findings = classification.validate_header(
                    classification.parse_header(doc), source=doc
                )
                naming = [f for f in findings if f.blocking and field in f.message]
                self.assertTrue(naming, f"dropping {field!r} produced no blocking finding: "
                                        f"{[f.message for f in findings]}")

    def test_an_empty_string_is_not_a_present_field(self) -> None:
        """The edge after narrowing: the check is "present AND non-empty", so blanking a field
        must not be a way to satisfy it."""
        doc = _header_doc({**_COMPLETE_HEADER, "owner": ""})
        findings = classification.validate_header(classification.parse_header(doc), source=doc)
        self.assertTrue([f for f in findings if f.blocking and "owner" in f.message])


class WrongTypedHeaderFieldsAreNotSilentlyCoerced(unittest.TestCase):
    """`P8-094`. ``parse_header`` coerces every wrong-typed value to a safe placeholder — right,
    and deliberately fail-closed — but did it in SILENCE, and ``_raw_front_matter_fields``, the
    function written for exactly this check, had no caller at all.

    Measured: ``export_allowed: "true"`` (quoted — the ordinary YAML mistake) parsed to ``False``
    and ``validate_header`` returned ZERO findings. A document declaring itself exportable was
    marked non-exportable with nothing anywhere saying the word ``export_allowed``.
    """

    def _findings(self, **overrides: object) -> list[str]:
        doc = _header_doc({**_COMPLETE_HEADER, **overrides})
        return [f.message for f in classification.validate_header(
            classification.parse_header(doc), source=doc) if f.blocking]

    def test_the_control_still_passes(self) -> None:
        self.assertEqual(self._findings(), [])

    def test_a_quoted_boolean_export_allowed_is_reported(self) -> None:
        parsed = classification.parse_header(
            _header_doc({**_COMPLETE_HEADER, "export_allowed": "true"})
        )
        self.assertFalse(parsed.export_allowed, "the coercion itself must stay fail-closed")
        self.assertTrue([m for m in self._findings(export_allowed="true")
                         if "export_allowed" in m])

    def test_an_integer_export_allowed_is_reported(self) -> None:
        """``bool`` is a subclass of ``int``, not the reverse, so ``1`` is not a bool — the edge a
        naive ``isinstance(value, (bool, int))`` would have let through."""
        self.assertTrue([m for m in self._findings(export_allowed=1) if "export_allowed" in m])

    def test_a_wrong_typed_surface_is_reported(self) -> None:
        self.assertTrue([m for m in self._findings(surface=["web"]) if "surface" in m])

    def test_a_wrong_typed_classification_is_reported(self) -> None:
        """The widest input of the class: ``classification`` coerces to SECRET, so the document
        still fails closed — but it fails while naming a tier the author never wrote."""
        self.assertTrue([m for m in self._findings(classification=7) if "classification" in m])

    def test_a_wrong_typed_variants_list_is_reported(self) -> None:
        """``variants`` feeds the cross-tier overlap gate; a string silently becomes ``[]``."""
        self.assertTrue([m for m in self._findings(variants="commercial") if "variants" in m])

    def test_an_unquoted_iso_date_is_not_a_finding(self) -> None:
        """Two-sided, and the false positive that would have made this gate unusable: YAML parses
        an unquoted ISO date into ``datetime.date``, which ``_str_field`` converts back to ISO
        text ON PURPOSE. Flagging it would be flagging correct authoring."""
        self.assertEqual(self._findings(last_reviewed=datetime.date(2026, 8, 21)), [])

    def test_without_the_source_the_checks_are_simply_absent(self) -> None:
        """The contract of the keyword: callers that do not have the raw document keep working,
        they just do not get these findings. Documenting it in a test keeps it from being read as
        a bug later."""
        doc = _header_doc({**_COMPLETE_HEADER, "export_allowed": "true"})
        self.assertEqual(classification.validate_header(classification.parse_header(doc)), [])

    def test_the_build_gate_passes_the_source(self) -> None:
        """A check nothing calls is not a check. ``generator.build`` is the export path, so it is
        the caller that has to be wired — asserted with ``ast`` rather than a substring scan,
        which would match this docstring."""
        import ast

        from tools.docgen import generator

        tree = ast.parse(pathlib.Path(generator.__file__).read_text(encoding="utf-8"))
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "validate_header"
            and any(kw.arg == "source" for kw in node.keywords)
        ]
        self.assertTrue(calls, "generator.build must call validate_header(..., source=...)")

    def test_the_live_corpus_gains_no_findings(self) -> None:
        """The cost of the new check, measured on the real tree rather than assumed. Every
        document the doc-system governs must be unaffected."""
        import subprocess

        repo = pathlib.Path(__file__).resolve().parents[2]
        tracked = subprocess.run(["git", "-C", str(repo), "ls-files", "*.md"],
                                 capture_output=True, text=True, check=True).stdout.split()
        self.assertTrue(tracked, "vacuity guard: no tracked markdown found")
        governed = 0
        for name in tracked:
            text = (repo / name).read_text(encoding="utf-8", errors="replace")
            header = classification.parse_header(text)
            if header.id == "UNKNOWN":
                continue
            governed += 1
            with self.subTest(document=name):
                self.assertEqual(
                    [f.message for f in classification.validate_header(header, source=text)
                     if f.blocking],
                    [f.message for f in classification.validate_header(header) if f.blocking],
                )
        self.assertGreaterEqual(governed, 4, "vacuity guard: no governed document was checked")


class TaxonomyPrefixColumnAliasing(unittest.TestCase):
    """``load_taxonomy_prefixes`` located the TAXONOMY.md id-prefix column by matching
    a header cell EXACTLY EQUAL to ``"prefix"``. A host project's own ``TAXONOMY.md`` spells that column
    ``id-prefix``, so the match never fired, ``prefix_col`` stayed ``None``, and the function
    returned an EMPTY set — which ``check_taxonomy_prefix`` treats as fail-closed and blocks every
    document the gate touches.

    ``_PREFIX_COLUMN_HEADERS`` is the fix: a named, general set of accepted spellings, matched
    whitespace-tolerantly and case-insensitively against the WHOLE cell (never a substring), so the
    capability stays general-purpose rather than growing a per-project carve-out.
    """

    def _taxonomy(self, body: str) -> pathlib.Path:
        """Write ``body`` to a throwaway ``TAXONOMY.md`` and return its path."""
        tmp = tempfile.TemporaryDirectory(prefix="taxonomy-alias-")
        self.addCleanup(tmp.cleanup)
        path = pathlib.Path(tmp.name) / "TAXONOMY.md"
        path.write_text(body, encoding="utf-8")
        return path

    def test_the_id_prefix_spelling_is_accepted(self) -> None:
        """(a) A host project's own spelling — the exact shape of the original defect."""
        path = self._taxonomy(
            "# TAXONOMY.md\n\nSome narrative prose before the table.\n\n"
            "| id-prefix | type | description | default tier(s) |\n"
            "|-----------|------|-------------|------------------|\n"
            "| ADR | Architecture decision record | one decision | internal |\n"
            "| SPEC | Specification | a normative contract | internal |\n"
        )
        self.assertEqual(classification.load_taxonomy_prefixes(path), {"ADR", "SPEC"})

    def test_the_original_prefix_spelling_still_works(self) -> None:
        """(b) No regression: the bundled engine spelling must keep working unchanged."""
        path = self._taxonomy(
            "# TAXONOMY.md\n\n"
            "| prefix | name | covers |\n"
            "|--------|------|--------|\n"
            "| ADR | Architecture decision record | one decision |\n"
        )
        self.assertEqual(classification.load_taxonomy_prefixes(path), {"ADR"})

    def test_case_and_whitespace_variants_are_accepted(self) -> None:
        """(c) ``  ID-Prefix  `` — mixed case, padded with whitespace — still matches."""
        path = self._taxonomy(
            "|   ID-Prefix   | type |\n"
            "|----------------|------|\n"
            "| WF | Workflow |\n"
        )
        self.assertEqual(classification.load_taxonomy_prefixes(path), {"WF"})

    def test_a_near_miss_header_does_not_match(self) -> None:
        """(d) Anchored to the WHOLE cell, never a substring: a column called ``prefix-notes`` is
        not the id-prefix column and must fail closed exactly like a genuinely absent table — the
        loose ``"prefix" in cell`` test this guards against would wrongly accept it."""
        path = self._taxonomy(
            "| prefix-notes | comment |\n"
            "|--------------|---------|\n"
            "| ADR | some note |\n"
        )
        self.assertEqual(classification.load_taxonomy_prefixes(path), set())

    def test_a_matching_header_with_zero_data_rows_stays_fail_closed(self) -> None:
        """(e) Fail-closed must SURVIVE UNCHANGED: a correctly-named header plus separator row but
        NO data rows must still return EMPTY, exactly as it did before this change — the aliasing
        fix must not accidentally make an empty table "pass" by returning a non-empty set."""
        path = self._taxonomy(
            "| prefix | type |\n"
            "|--------|------|\n"
        )
        self.assertEqual(classification.load_taxonomy_prefixes(path), set())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
