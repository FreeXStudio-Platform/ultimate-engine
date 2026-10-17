"""Every front-matter reader must agree about what "a leading HTML comment" is.

Four modules decide whether a markdown file is *governed*
by looking for front matter behind a run of leading HTML comments. They held four COPIES of the
comment sub-pattern under a comment asserting they were identical, and a one-file fix to that
pattern (round 2 of the CodeQL pass) reached one of the four. These are the retained falsifications
for all three defects that fell out of it, each exercised at its own real entry point rather than
against a regex object:

* **Four copies** — ``CONS-09``/``BUILD-02``'s inline patterns and ``archive._FM_FENCE_RE`` kept
  round 1's tempered dot, which cannot see HTML's abrupt-closing comment forms ``<!-->`` and
  ``<!--->``.
* **Catastrophic backtracking** — ``corpus.py`` kept the base lazy ``<!--.*?-->``, catastrophic on
  leading comments with no closing fence: 8.3 s on 26 comments, unbounded at the caller's own
  4,000-char cap.
* **The placement-gate bypass**, and the reason this file exists at all. Every
  version of the run pattern from base ``1.0.12`` through ``07a287b2`` allowed exactly ONE comment
  per line. That was harmless while the token backtracked and became a bypass the moment round 1
  made it commit to the first ``-->``: a line reading ``<!-- a --><!-- b -->`` matched nothing, so
  a ``classification: secret`` document committed clean OUTSIDE the vault. Base ``1.0.12``
  REFUSED it; ``66e71ff0`` and ``07a287b2`` do not.

**Two-sided throughout** (`docs/process/RULES.md` Rule 1): each guard is asserted to refuse the
planted defect AND to leave ordinary documents alone, because a guard that refuses everything
passes the first half vacuously.
"""

from __future__ import annotations

import ast
import functools
import json
import pathlib
import random
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from collections.abc import Callable
from typing import ClassVar

from tools.corpus_check.corpus import _FRONT_MATTER_RE as CORPUS_RE
from tools.corpus_check.guards.rendered_output import _strip_html_comments
from tools.docgen.archive import _FM_FENCE_RE, _write_header_version
from tools.docgen.classification import _FRONT_MATTER_RE as CLASSIFICATION_RE
from tools.docgen.hooks.staged_content_scanner import _has_doc_header, classify_file
from tools.health.checks import _GOVERNED_FRONT_MATTER_RE
from tools.lib.front_matter import (
    _REACHABLE_FENCE_RE,
    HTML_COMMENT,
    LEADING_COMMENT_LINES,
    unparseable_leading_block,
)
from tools.tests import front_matter_inputs as fmi
from tools.tests.front_matter_inputs import (
    TIMING_UNITS,
    adversarial_prefixes,
    generate,
)

_REPO = pathlib.Path(__file__).resolve().parents[2]

#: The ONE literal outside `tools/lib` that legitimately spells a comment RUN of its own, keyed by
#: file and pinned by a distinguishing fragment of the pattern itself.
#:
#: This was a set of FILE paths, which exempted
#: `tools/docgen/hooks/staged_content_scanner.py` — the module that owns the placement gate — in
#: full: a second, hand-written run added anywhere in it would have been invisible to the guard
#: that exists to find exactly that. An allowlist entry should buy one pattern a pass, never a
#: file. `tools/corpus_check/guards/rendered_output.py` was also listed and its entry was STALE:
#: A later round replaced that regex with a forward `str.find` scan, so the file has held no comment
#: pattern since, and the reason attached to it described code that no longer exists.
_ALLOWED_RUN_LITERALS: dict[str, tuple[str, ...]] = {
    # `_LEGACY_CLASSIFICATION_RE` answers a DIFFERENT question: it recognises the FOREIGN
    # `<!-- classification: X -->` header syntax inherited from the project this engine was
    # extracted from, whose tier vocabulary this engine does not implement. Its `[^>]*` cannot
    # cross a `>` — deliberately, because a legacy header is a single well-formed comment, never a
    # run — so folding it into HTML_COMMENT would widen what counts as a legacy header. Unchanged
    # from base 1.0.12 apart from round 1's `\s*` hoist.
    "tools/docgen/hooks/staged_content_scanner.py": ("<!--\\s*classification:",),
}

#: A regex repetition applied to a group: `)*`, `)+`, `)*?`, `)+?` and — the forms the round-5
#: heuristic could not see — `){2,}` and friends.
_REPETITION_AFTER_GROUP = re.compile(r"\)(?:[*+]\??|\{\d)")

_GOVERNED_BODY = "---\nclassification: secret\nid: TOKENTEST-001\n---\n\nbody\n"


def _verdict(text: str) -> str | None:
    """``unparseable_leading_block`` with the gate's OWN header predicate injected.

    The verdict takes ``declares_classification`` rather than importing one, so every
    test must supply it — and supplying a different one here than ``classify_file`` uses would make
    these tests agree with a gate that does not exist. One spelling, one predicate.
    """
    return unparseable_leading_block(text, declares_classification=_has_doc_header)


def _governed(prefix: str = "") -> str:
    return prefix + _GOVERNED_BODY


#: The `re` entry points a pattern can be written through.
_RE_ENTRY_POINTS = frozenset({"compile", "match", "search", "fullmatch", "finditer", "sub"})


def _re_module_aliases(tree: ast.Module) -> tuple[frozenset[str], frozenset[str]]:
    """Names bound to the ``re`` MODULE, and names bound to ``re``'s own functions, in *tree*.

    ``_is_re_call`` used to require the literal name ``re``, so the identical
    two-fragment run written as ``import re as _rx`` … ``_rx.compile(rf"…")`` was invisible to the
    guard — the f-string's constants split ``<!--`` from the ``)*`` across two nodes AND the call
    was not recognised, so neither path could see it. That is the same defect the earlier
    spelling-based and constant-based guards exist for, one level up: the hand-written list had
    become a list of IMPORT
    spellings instead of pattern spellings. It is derived from the module's own imports now.
    """
    modules = {"re"}
    funcs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "re":
                    modules.add(alias.asname or "re")
        elif isinstance(node, ast.ImportFrom) and node.module == "re":
            for alias in node.names:
                if alias.name in _RE_ENTRY_POINTS:
                    funcs.add(alias.asname or alias.name)

    # Imports were the only binding this looked at, so an ASSIGNED alias —
    # ``_r = re`` then ``_r.compile(rf"…")`` — was invisible and a real duplicate comment run
    # behind one passed the guard (measured at the copy's build 1.0.13). An earlier round fixed the
    # import spelling and left the assignment spelling, which is the same hand-written-list shape
    # one level further down: the list had become a list of BINDING FORMS. Module-valued names are
    # resolved here exactly the way `_candidate_patterns` already resolves string-valued ones.
    #
    # Iterated to a fixpoint because assignments need not be in dependency order: ``_r2 = _r``
    # can be written above ``_r = re``, and a single pass would see only one of the two.
    while True:
        grew = False
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
            if isinstance(value, ast.Name) and value.id in modules:
                grew |= not modules.issuperset(targets)
                modules.update(targets)
            elif (
                isinstance(value, ast.Attribute)
                and isinstance(value.value, ast.Name)
                and value.value.id in modules
                and value.attr in _RE_ENTRY_POINTS
            ):
                # `_c = re.compile` — the entry point itself bound to a name, the assignment
                # twin of `from re import compile as _c`.
                grew |= not funcs.issuperset(targets)
                funcs.update(targets)
        if not grew:
            break
    return frozenset(modules), frozenset(funcs)


def _is_re_call(node: ast.Call, modules: frozenset[str], funcs: frozenset[str]) -> bool:
    """``<re-alias>.compile(...)`` / ``.match`` / ``.search`` …, or a from-imported entry point."""
    func = node.func
    if (
        isinstance(func, ast.Attribute)
        and func.attr in _RE_ENTRY_POINTS
        and isinstance(func.value, ast.Name)
        and func.value.id in modules
    ):
        return True
    return isinstance(func, ast.Name) and func.id in funcs


def _assigns_to(tree: ast.Module, call: ast.Call, name: str) -> bool:
    """True iff *call* is the value of a module-level assignment to *name*."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and node.value is call:
            return any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
    return False


def _candidate_patterns(tree: ast.Module) -> list[tuple[ast.expr, str, bool]]:
    """Every regex-ish string in *tree* as ``(node, assembled text, shares_the_token)``.

    Two shapes escaped the round-5 guard, which walked bare ``ast.Constant`` nodes:
    a pattern assembled from several fragments (an f-string is a ``JoinedStr`` whose parts are
    separate nodes, so no single constant carries both the ``<!--`` and the repetition), and a
    pattern built by concatenation. Assembling the ``re.*`` call's first argument closes both.
    ``shares_the_token`` marks a pattern that interpolates the shared constant — the compliant
    state, which must not be reported as an offence.
    """
    # Module-level `NAME = "literal"` bindings, so a pattern assembled out of a local fragment is
    # judged on what it ACTUALLY spells. Without this, `_FRAG = r"<!--[^>]*-->"` followed by
    # `rf"(?:{_FRAG})*"` assembles to `(?:\x00)*` — a repetition with no `<!--` in it — and the
    # guard reports nothing. Proven by red proof: that exact pair is invisible without this map.
    modules, funcs = _re_module_aliases(tree)
    consts: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    consts[target.id] = node.value.value

    out: list[tuple[ast.expr, str, bool]] = []
    inside_calls: set[int] = set()
    for call in ast.walk(tree):
        if isinstance(call, ast.Call) and _is_re_call(call, modules, funcs) and call.args:
            arg = call.args[0]
            parts: list[str] = []
            shares = False
            for piece in (arg.values if isinstance(arg, ast.JoinedStr) else [arg]):
                if isinstance(piece, ast.Constant) and isinstance(piece.value, str):
                    parts.append(piece.value)
                elif isinstance(piece, ast.FormattedValue):
                    names = {n.id for n in ast.walk(piece) if isinstance(n, ast.Name)}
                    shares |= bool(names & {"HTML_COMMENT", "LEADING_COMMENT_LINES"})
                    resolved = [consts[n] for n in sorted(names) if n in consts]
                    parts.append("".join(resolved) if resolved else "\x00")
            for sub in ast.walk(arg):
                inside_calls.add(id(sub))
            out.append((call, "".join(parts), shares))
    for lit in ast.walk(tree):
        if (
            isinstance(lit, ast.Constant)
            and isinstance(lit.value, str)
            and id(lit) not in inside_calls
        ):
            out.append((lit, lit.value, False))
    return out


def _enclosing_function(tree: ast.Module, call: ast.Call) -> str | None:
    """The name of the function *call* is written inside, or ``None`` at module level.

    Base writes both `checks.py` front-matter readers INLINE inside a loop, assigned
    to a local, so there is no module-level name to select them by — and selecting "the first
    `<!--` regex in the file" silently took the `session-state:` marker instead. The function is
    the only stable handle the release's own bytes offer.
    """
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    cur: ast.AST | None = parents.get(call)
    while cur is not None:
        if isinstance(cur, ast.FunctionDef | ast.AsyncFunctionDef):
            return cur.name
        cur = parents.get(cur)
    return None


class TheCommentTokenHasExactlyOneDefinition(unittest.TestCase):
    """The structural half of the four-copies defect: four copies is what let three of four go unfixed.

    A test that the fix HELD is worth more than a test that the fix happened — the divergence was
    invisible for two rounds precisely because nothing compared the copies.
    """

    def test_no_module_outside_tools_lib_writes_its_own_comment_regex(self) -> None:
        """The first version of this guard hunted three
        hand-written literals, and a SIXTH site spelled the same idea a fourth way —
        ``<!--[^>]*-->`` in ``staged_content_scanner._LEGACY_CLASSIFICATION_RE`` — in the very
        module that owns the placement gate. A guard whose literal list is hand-written has the
        defect class it exists to catch.

        So it does not enumerate spellings: it flags any pattern that contains ``<!--`` inside a
        **repetition**, which is the precise shape of a comment RUN, parsed with ``ast`` rather
        than grepped. Round 5's version tested for the substrings ``)*`` and ``)+`` in single
        string CONSTANTS, and so missed two shapes: ``){2,}`` repetition, and a pattern assembled
        from more than one fragment — an f-string is a ``JoinedStr``, not a ``Constant``, so
        ``checks.py``'s own two front-matter readers were invisible to it. Both are covered now:
        the repetition test is a regex over the operators, and every ``re.*`` call's first
        argument is ASSEMBLED from its parts before it is judged.

        A pattern that interpolates ``HTML_COMMENT``/``LEADING_COMMENT_LINES`` is the compliant
        state, not an offence — that is what "import it from tools.lib" looks like in an f-string.

        Measured: the broader "any regex mentioning ``<!--``" rule flags five legitimate MARKER
        patterns (``<!--\\s*figure:…-->``, ``<!--\\s*record:…-->`` and kin) that match ONE specific
        comment and never a run — a different question, correctly written locally. A guard that
        cries wolf on five valid sites gets deleted; this one does not.
        """
        offenders: list[str] = []
        for path in sorted(_REPO.glob("tools/**/*.py")):
            rel = path.relative_to(_REPO).as_posix()
            if rel.startswith(("tools/lib/front_matter.py", "tools/tests/")):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            allowed = _ALLOWED_RUN_LITERALS.get(rel, ())
            for node, text, shares in _candidate_patterns(tree):
                if "<!--" not in text or shares:
                    continue
                if not _REPETITION_AFTER_GROUP.search(text):
                    continue
                if any(frag in text for frag in allowed):
                    continue
                offenders.append(f"{rel}:{node.lineno}: {text[:48]!r}")
        self.assertEqual(
            offenders, [],
            "a module outside tools/lib writes its own HTML-comment RUN. That is the four-copies "
            "shape (four copies, one of them fixed) and the blind-guard shape (a guard that could "
            "not see the fourth spelling). Import from tools.lib.front_matter, or — if the "
            "semantics genuinely differ — pin the literal in _ALLOWED_RUN_LITERALS with the "
            "reason:\n  " + "\n  ".join(offenders),
        )

    def test_the_allowlist_has_no_stale_entry(self) -> None:
        """A stale exemption is worse than none: it reads as a reviewed decision.

        ``rendered_output.py`` sat here for a round after a later fix deleted the regex its reason
        described. An allowlist that is never re-derived from the tree drifts exactly the way the
        pattern copies it polices did.
        """
        stale: list[str] = []
        for rel, frags in _ALLOWED_RUN_LITERALS.items():
            text = (_REPO / rel).read_text(encoding="utf-8")
            stale += [f"{rel}: {f!r}" for f in frags if f not in text]
        self.assertEqual(stale, [], "an allowlisted pattern is no longer in its file:\n  " + "\n  ".join(stale))

    def test_every_reader_is_built_from_the_shared_constant(self) -> None:
        for name, pattern in (
            ("classification._FRONT_MATTER_RE", CLASSIFICATION_RE.pattern),
            ("archive._FM_FENCE_RE", _FM_FENCE_RE.pattern),
            ("corpus._FRONT_MATTER_RE", CORPUS_RE.pattern),
        ):
            with self.subTest(reader=name):
                self.assertIn(HTML_COMMENT, pattern, f"{name} does not carry the shared token")

    def test_checks_py_uses_the_shared_run_for_both_cons09_and_build02(self) -> None:
        """This used to assert ``count("{LEADING_COMMENT_LINES}") == 2`` — two inline
        copies, each composing the shared run. Two copies passing a "did you fix both?" test is
        still two copies; they were byte-identical, recompiled per file inside two loops, and
        invisible to the `ast` differential because an f-string is a ``JoinedStr``. One
        module-level constant is the actual fix, so the assertion is now the stronger one: exactly
        one definition, and both checks call it.
        """
        text = (_REPO / "tools" / "health" / "checks.py").read_text(encoding="utf-8")
        self.assertEqual(
            text.count("{LEADING_COMMENT_LINES}"), 1,
            "the governed-document reader must have ONE definition in checks.py",
        )
        self.assertEqual(
            text.count("_GOVERNED_FRONT_MATTER_RE.match("), 2,
            "CONS-09 and BUILD-02 must BOTH call it — fixing one and not the other is the four-copies defect",
        )


class EveryReaderParsesTheAdversarialPrefixes(unittest.TestCase):
    """The four-copies defect and the placement-gate bypass, at each reader, over the whole class of prefixes."""

    def test_classification_front_matter_is_found_behind_every_prefix(self) -> None:
        for label, prefix in adversarial_prefixes():
            with self.subTest(prefix=label):
                text = _governed(prefix)
                self.assertTrue(
                    CLASSIFICATION_RE.search(text) is not None
                    or _verdict(text) is not None,
                    f"{label}: neither front matter NOR an unparseable block — classify_file "
                    "would return None, which is fail-open",
                )

    def test_corpus_check_front_matter_is_found_behind_every_prefix(self) -> None:
        for label, prefix in adversarial_prefixes():
            with self.subTest(prefix=label):
                text = _governed(prefix)
                self.assertTrue(
                    CORPUS_RE.match(text) is not None or _verdict(text) is not None,
                    f"{label}: corpus.governed cannot see it and the gate would not refuse it",
                )

    def test_checks_py_governed_counter_is_found_behind_every_prefix(self) -> None:
        """CONS-09 and BUILD-02 share one pattern; this is that pattern, composed as they compose it."""
        rx = re.compile(
            rf"\A﻿?{LEADING_COMMENT_LINES}[ \t]*---[ \t]*\r?\n(.*?\r?\n)---", re.DOTALL
        )
        for label, prefix in adversarial_prefixes():
            with self.subTest(prefix=label):
                text = _governed(prefix)
                found = rx.match(text)
                if found is None:
                    self.assertIsNotNone(
                        _verdict(text),
                        f"{label}: CONS-09 miscounts and BUILD-02 under-builds, and the gate "
                        "would let such a document into the tree",
                    )
                    continue
                self.assertIn("classification", found.group(1))

    def test_ordinary_documents_are_unaffected(self) -> None:
        """The other half: a reader that matched everything would pass every test above."""
        for label, text in (
            ("no front matter at all", "# Title\n\njust prose\n"),
            ("a fence that is not front matter", "prose\n\n---\nclassification: secret\n---\n"),
            ("an unterminated comment", "<!-- open\n---\nclassification: secret\n---\n"),
        ):
            with self.subTest(case=label):
                self.assertIsNone(CORPUS_RE.match(text), label)


class ArchiveStampsTheVersionBehindEveryPrefix(unittest.TestCase):
    """The four-copies defect at ``archive.py``: the silent one.

    ``_write_header_version`` returns ``False`` for an ungoverned document *by design* — so a
    reader that cannot parse the prefix does not fail, it silently declines to stamp and the
    archive records a governed document as ungoverned. Nothing downstream notices.
    """

    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="fm_archive_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_version_is_written_behind_every_prefix(self) -> None:
        for label, prefix in adversarial_prefixes():
            with self.subTest(prefix=label):
                doc = self.tmp / "d.md"
                doc.write_text(_governed(prefix), encoding="utf-8")
                if not _write_header_version(doc, 7):
                    # Allowed ONLY when the gate refuses such a document outright: the stamp can
                    # be skipped for a file that can never be committed. That is the fail-closed pairing.
                    self.assertIsNotNone(
                        _verdict(_governed(prefix)),
                        f"{label}: the version stamp was silently skipped for a document the "
                        "gate would ACCEPT — the archive records it as ungoverned",
                    )
                    continue
                self.assertIn("version: 7", doc.read_text(encoding="utf-8"))

    def test_a_genuinely_ungoverned_document_is_still_declined(self) -> None:
        doc = self.tmp / "plain.md"
        doc.write_text("# Title\n\nno front matter here\n", encoding="utf-8")
        self.assertFalse(_write_header_version(doc, 7))


class ThePlacementGateRefusesBehindEveryPrefix(unittest.TestCase):
    """The moat. This is the test that would have caught the placement-gate bypass.

    ``classify_file``'s contract is ``if not _has_doc_header(text): return None`` — a prefix the
    front-matter reader cannot parse is indistinguishable from a file with nothing to protect.
    """

    def setUp(self) -> None:
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="fm_repo_"))
        self.addCleanup(shutil.rmtree, self.root, True)
        subprocess.run(("git", "init", "-q", "."), cwd=self.root, check=True)
        (self.root / ".gitignore").write_text("docs/confidential/\n", encoding="utf-8")

    def test_a_secret_document_outside_the_vault_is_refused_behind_every_prefix(self) -> None:
        for label, prefix in adversarial_prefixes():
            with self.subTest(prefix=label):
                found = classify_file("docs/x.md", _governed(prefix), self.root)
                self.assertIsNotNone(found, f"{label}: COMMITTED CLEAN — placement-gate bypass")
                assert found is not None
                self.assertTrue(found.blocking, f"{label}: finding was not blocking")

    def test_a_public_document_still_commits_clean(self) -> None:
        public = "---\nclassification: public\nid: TOKENTEST-002\n---\n\nbody\n"
        for label, prefix in adversarial_prefixes():
            with self.subTest(prefix=label):
                found = classify_file("docs/x.md", prefix + public, self.root)
                if _verdict(prefix + public) is not None:
                    # An unparseable block is refused whatever the tier — the gate
                    # cannot read the tier, so "it says public" is not something it can trust.
                    self.assertIsNotNone(found, f"{label}: unparseable, so it must be refused")
                    continue
                self.assertIsNone(found, label)

    def test_a_header_less_document_still_commits_clean(self) -> None:
        self.assertIsNone(classify_file("docs/x.md", "# Title\n\nprose\n", self.root))


class TheReadersAreLinearOnAdversarialInput(unittest.TestCase):
    """``corpus.py``'s copy was catastrophic, and the caller's cap did not bound it.

    The ceiling is deliberately generous (250 ms against ~0.1 ms measured). This asserts the
    absence of catastrophic backtracking, not a performance budget — a tight bound would make the
    test flaky on a loaded machine and teach the next reader to raise it rather than to look.
    """

    CEILING_MS = 250.0

    def _elapsed_ms(self, call: Callable[[], object]) -> float:
        start = time.perf_counter()
        call()
        return (time.perf_counter() - start) * 1000

    def test_leading_comments_with_no_closing_fence_are_linear(self) -> None:
        """The exact shape that measured 8.3 s at 26 comments, across every declared unit."""
        for label, unit in TIMING_UNITS:
            for reps in (26, 60, 120):
                with self.subTest(shape=label, comments=reps):
                    self._assert_both_linear(unit * reps, label)

    def test_the_callers_own_4000_char_cap_is_linear(self) -> None:
        """``corpus.front_matter`` passes ``text[:4000]``; before the fix that cap did not bound it."""
        for label, unit in TIMING_UNITS:
            with self.subTest(shape=label):
                self._assert_both_linear((unit * 4000)[:4000], label)

    def test_the_reachability_scan_is_linear_in_fence_candidates(self) -> None:
        """The verdict now SCANS, so the scan has to be bounded too.

        The adversarial shape is many ``-->``/fence pairs, because each one costs a header parse.
        The requirement was explicit that reachability must not be implemented by running
        base 1.0.12's own pattern as an oracle — that pattern is the catastrophic
        backtracker, and importing it here would put a >6 s worst case on the commit path. This is
        the measurement that says the literal forward scan did not reintroduce one: 2,000 candidate
        pairs, none of which declares a classification, so every one is parsed and rejected.
        """
        # The `z` is load-bearing: it interrupts the strict run so the verdict does NOT return at
        # condition (ii). Without it the run lands on the first fence, the function returns before
        # the loop, and this test measures an early return — a timing test that cannot fail, which
        # is the shape this suite exists to stop. Asserted, not assumed: the count below proves the
        # scan really walked every candidate.
        worst = "<!-- a -->\nz\n" + "<!-- b -->\n---\nfoo: bar\n---\n" * 2000
        self.assertGreater(
            len(_REACHABLE_FENCE_RE.findall(worst)), 1999,
            "the timing input must actually present the candidates it claims to",
        )
        self.assertIsNone(_verdict(worst), "none of these fences declares a classification")
        self.assertLess(
            self._elapsed_ms(lambda: _verdict(worst)), self.CEILING_MS,
            "the reachability scan is superlinear in the number of fence candidates",
        )

    #: Shapes whose closing fence is ABSENT or SHARED — the two ways a per-candidate
    #: lookup becomes quadratic. Round 6's timing test used only the third shape, whose `\n---`
    #: sits immediately after every candidate so the lookup hits on its first comparison; at equal
    #: length it measured 3.4 ms where the miss-dense shape measured 536 ms.
    ADVERSARIAL_DENSITIES: ClassVar[tuple[tuple[str, Callable[[int], str]], ...]] = (
        ("miss-dense: no closing fence anywhere",
         lambda kb: "<!-- a -->\nz\n" + "-->---" * (kb * 1024 // 6)),
        ("miss-dense, space-separated (the verifier's end-to-end shape)",
         lambda kb: "<!-- a -->\nz\n" + "--> ---" * (kb * 1024 // 7)),
        ("shared-close: every candidate resolves to ONE distant fence",
         lambda kb: "<!-- a -->\nz\n" + "-->---\n" * (kb * 1024 // 7)
         + "\n---\nclassification: secret\n---\n"),
    )

    #: A quadratic costs (n2/n1)**2. Over the 4 KB -> 1 MB range that is x65,536 ideal, and round 6
    #: measured x122,692 end-to-end. This implementation measures x428 (verdict) and x1,194
    #: (through `classify_file`) — linear would be x256, and the excess is a cache cliff above
    #: 512 KB, not a growth term: doubling costs x1.99, x1.99, x2.00 up to 512 KB.
    #:
    #: The bound is set at x10,000 — 8x headroom over the worst measurement on a box at load 390,
    #: and still 12x below the quadratic this test exists to catch. A tight bound here would be
    #: flaky and would teach the next reader to raise it rather than to look.
    MAX_GROWTH_OVER_256X_INPUT = 10_000.0

    def test_the_scan_does_not_go_quadratic_when_the_closing_fence_is_absent_or_shared(self) -> None:
        """The defect round 6 shipped, as a property over the adversarial densities.

        `text.find("\n---", fence + 3)` is O(1) when it hits and O(remaining) when it MISSES, so a
        document dense in `-->` with no `\n---` after them cost 128.8 s for ONE 1 MB file at the
        real gate — against base 1.0.12's 39 ms. The 4,000-character cap that made the earlier
        quadratic scan look bounded does not apply here: `classify_file` receives the whole decoded blob.

        Growth is asserted over a 256x input range rather than per-doubling, because a cache cliff
        above 512 KB makes any single doubling a poor discriminator while the wide range separates
        linear from quadratic by two orders of magnitude.
        """
        for label, make in self.ADVERSARIAL_DENSITIES:
            with self.subTest(shape=label):
                small, large = make(4), make(1024)
                self.assertGreater(
                    len(_REACHABLE_FENCE_RE.findall(large)), 10_000,
                    "the timing input must actually present the candidates it claims to",
                )
                t_small = self._elapsed_ms(functools.partial(_verdict, small))
                t_large = self._elapsed_ms(functools.partial(_verdict, large))
                growth = t_large / max(t_small, 1e-3)
                self.assertLess(
                    growth, self.MAX_GROWTH_OVER_256X_INPUT,
                    f"{label}: x{growth:.0f} over a 256x input — a per-candidate scan has gone "
                    "superlinear again (the third quadratic in this sequence)",
                )

    def test_the_real_gate_absorbs_a_one_megabyte_adversarial_document(self) -> None:
        """End-to-end through ``classify_file``, which is where the 128.8 s was measured.

        The verdict being fast is not the claim that matters; the claim is that the COMMIT PATH is.
        Round 6 passed its own unit test while this took over two minutes for one file.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "docs" / "confidential").mkdir(parents=True)
            (root / ".gitignore").write_text("docs/confidential/\n")
            text = "<!-- a -->\nz\n" + "--> ---" * (1024 * 1024 // 7)
            start = time.perf_counter()
            self.assertIsNone(classify_file("docs/x.md", text, root))
            elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(
            elapsed_ms, 5_000.0,
            f"one 1 MB document took {elapsed_ms:.0f} ms at the gate (round 6: 128,826 ms)",
        )

    def test_the_verdict_is_linear_on_every_timing_unit(self) -> None:
        """The verdict runs on the commit path, so it is held to the readers' own ceiling."""
        for label, unit in TIMING_UNITS:
            with self.subTest(shape=label):
                text = (unit * 4000)[:4000]
                probe = functools.partial(_verdict, text)
                self.assertLess(self._elapsed_ms(probe), self.CEILING_MS, label)

    def _assert_both_linear(self, text: str, label: str) -> None:
        for name, call in (
            ("corpus", lambda t=text: CORPUS_RE.match(t)),
            ("classification", lambda t=text: CLASSIFICATION_RE.search(t)),
        ):
            self.assertLess(self._elapsed_ms(call), self.CEILING_MS, f"{name}: {label}")


class NothingBase1012AcceptedWasLost(unittest.TestCase):
    """The retained differential — now over ALL FIVE readers, from the release's own bytes.

    The first version shipped this with 2 of 5 readers pinned and one of those not byte-identical, so
    the property it advertised was narrower than it read. Every base pattern below is now extracted
    at runtime with ``git show <BASE_REV>:<file>`` — the release IS the fixture, so the
    test cannot drift from it and cannot be "tidied" into comparing the code to itself.

    **The invariant, stated precisely**: a reader may lose an input ONLY if
    the placement gate refuses that input. Anything a reader cannot see must be unable to enter the
    tree in the first place. That pairing is the whole argument for fail-closed, so it is asserted
    rather than described.
    """

    #: The engine release whose five front-matter readers are the "before": named by COMMIT, not by a tag (a tag is a name some
    #: clones never fetch), and chosen so that every clone of this repository has it — it is this repository's own history.
    #: A downstream copy measured the same five readers at a later release; they are byte-identical at this commit (checked by
    #: extracting each pattern from both and comparing), so the differential is unchanged by using the older, shared revision.
    BASE_REV = "185725a10da929f540c3e4c0334ff2b337229727"
    #: reader -> (base file, selector, how). The SELECTOR names the base node exactly:
    #: ``attr:<name>`` for a module-level assignment, ``func:<name>`` for a pattern written inline
    #: inside that function.
    #:
    #: The two ``checks`` entries used to carry ``None``, which meant "take the first
    #: ``re.*`` call in the file whose literal contains ``<!--``" — and in base that is the
    #: ``session-state:`` MARKER at ``checks.py:439``, not the front-matter readers at ``:1409`` and
    #: ``:1726``. One marker was stored twice under two reader names, and
    #: ``test_every_reader_has_a_base_pattern_extracted_from_the_tag`` passed on it, because it
    #: asserts that a pattern was found and never that it is the right one. Both base sites are
    #: inline in a loop and assigned to nothing, so an attribute selector cannot reach them; the
    #: enclosing function can, and is what distinguishes CONS-09 from BUILD-02 (their two literals
    #: are byte-identical, which is itself why HEAD now holds ONE constant for both).
    READERS: ClassVar[dict[str, tuple[str, str, str]]] = {
        "classification": ("tools/docgen/classification.py", "attr:_FRONT_MATTER_RE", "search"),
        "corpus": ("tools/corpus_check/corpus.py", "attr:_FRONT_MATTER_RE", "match"),
        "archive": ("tools/docgen/archive.py", "attr:_FM_FENCE_RE", "match"),
        "checks.CONS-09": ("tools/health/checks.py", "func:check_charter_counts", "match"),
        "checks.BUILD-02": ("tools/health/checks.py", "func:_doc_system_documents", "match"),
    }

    @classmethod
    def _base_source(cls, path: str) -> str:
        done = subprocess.run(
            ["git", "show", f"{cls.BASE_REV}:{path}"],
            cwd=_REPO, capture_output=True, text=True, check=False,
        )
        return done.stdout

    FIXTURE: ClassVar[pathlib.Path] = pathlib.Path(__file__).with_name("base_front_matter_readers.json")

    @classmethod
    def _release_reachable(cls) -> bool:
        done = subprocess.run(["git", "cat-file", "-e", f"{cls.BASE_REV}^{{commit}}"], cwd=_REPO, capture_output=True, check=False)
        return done.returncode == 0

    @classmethod
    def _base_patterns(cls) -> dict[str, re.Pattern[str]]:
        """The readers' "before" patterns: from the release's own source when its commit is in this clone, else from the committed fixture.

        A published snapshot or a fresh clone has no such commit; the fixture holds the same five patterns, and
        ``test_the_fixture_equals_the_release_where_both_exist`` keeps the two from drifting.
        """
        if cls._release_reachable():
            return cls._patterns_from_git()
        data = json.loads(cls.FIXTURE.read_text(encoding="utf-8"))["readers"]
        return {name: re.compile(pattern, re.DOTALL) for name, pattern in data.items()}

    @classmethod
    def _patterns_from_git(cls) -> dict[str, re.Pattern[str]]:
        """Compile each reader's base pattern out of the tag's own bytes, via ``ast``.

        Parsed, not grepped. The first version of this hunted string literals containing ``<!--``
        and so captured only the comment-RUN half of a two-literal pattern — a fragment of all-`*`
        quantifiers that matches every input, which made every document look "lost" and would have
        reported a fail-open regression that did not exist. A pattern is an expression, so read it
        with the expression parser.
        """
        found: dict[str, re.Pattern[str]] = {}
        for name, (path, selector, _how) in cls.READERS.items():
            source = cls._base_source(path)
            if not source:
                continue
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            kind, _, target = selector.partition(":")
            modules, funcs = _re_module_aliases(tree)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and _is_re_call(node, modules, funcs)):
                    continue
                if not node.args or not isinstance(node.args[0], ast.Constant):
                    continue
                pattern = node.args[0].value
                if not isinstance(pattern, str) or "<!--" not in pattern:
                    continue
                if kind == "attr" and not _assigns_to(tree, node, target):
                    continue
                if kind == "func" and _enclosing_function(tree, node) != target:
                    continue
                try:
                    found[name] = re.compile(pattern, re.DOTALL)
                except re.error:
                    continue
                break
        return found

    def test_the_two_checks_readers_are_the_front_matter_ones_not_the_session_marker(self) -> None:
        """The pin that passed on the wrong pattern.

        Asserting "a pattern was found" is not asserting "the right pattern was found" — the
        distinction is the whole finding, so it is now a separate assertion. A front-matter reader
        must contain a fence; the ``session-state:`` marker never does.
        """
        base = self._base_patterns()
        for name in ("checks.CONS-09", "checks.BUILD-02"):
            with self.subTest(reader=name):
                self.assertIn(name, base)
                self.assertIn("---", base[name].pattern, f"{name} pinned a non-front-matter regex")
                self.assertNotIn("session-state", base[name].pattern)
        self.assertEqual(
            base["checks.CONS-09"].pattern, base["checks.BUILD-02"].pattern,
            "base's two sites are byte-identical, which is why HEAD holds ONE constant for both; "
            "if they ever differed, one HEAD constant would be the wrong fix",
        )

    def test_the_fixture_equals_the_release_where_both_exist(self) -> None:
        """The committed fixture is the release's patterns, byte for byte; where the release is reachable the two must agree."""
        data = json.loads(self.FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(sorted(data["readers"]), sorted(self.READERS))
        if self._release_reachable():
            self.assertEqual(data["readers"], {name: pat.pattern for name, pat in self._patterns_from_git().items()})

    def test_every_reader_has_a_base_pattern_extracted_from_the_tag(self) -> None:
        """The four-copies gap: 2 of 5 were pinned, and the differential silently covered only those."""
        patterns = self._base_patterns()
        self.assertEqual(
            sorted(patterns), sorted(self.READERS),
            "a reader has no base-1.0.12 pattern in the differential, so 'nothing was lost' is "
            "unproven for it — exactly the earlier four-copies shape",
        )

    def test_a_reader_may_only_lose_what_the_gate_refuses(self) -> None:
        """The fail-closed pairing, as the AMENDED invariant scopes it.

        **The scope changed, and it changed deliberately — read this before "fixing" a failure.**
        Round 5 asserted the pairing over EVERY input: anything a reader could not see had to be
        refused at the gate. That held only because round 5's verdict refused any leading block it
        could not parse, whatever the document contained — which is what refused ten ordinary
        OpenZeppelin PR templates carrying no front matter at all. The amended verdict fires only
        when a CLASSIFICATION header sits behind the block, so the unconditional pairing is no
        longer true and asserting it would be asserting the cost the amendment was made to remove.

        What is asserted instead is the property that actually carries the security argument, in
        two halves — which is strictly more information than the old single list:

        * a GOVERNED input a reader loses must be refused by the gate (the fail-closed pairing);
        * an UNGOVERNED input a reader loses need not be, but the SAME SHAPE carrying a
          classification must be. A shape is guarded whenever being unguarded would matter.

        Measured at this commit: 243 governed losses, all refused; 243 ungoverned losses across 9
        shapes, every one of whose governed twin is refused. The ungoverned losses are documents
        base mis-parsed — ``<!-- a --> b -->`` is one comment and then the text `` b -->`` by
        HTML's own rules, so the strict readers are RIGHT to stop there; their cost is a `CONS-09`
        miscount or a skipped archive stamp, not a placement bypass.
        """
        base = self._base_patterns()
        # All FIVE, not three. The two `checks` entries had no `now` counterpart, so
        # the loop's `if name not in base` never reached them and the class advertised a coverage
        # it did not have. HEAD's single `_GOVERNED_FRONT_MATTER_RE` answers for both, because the
        # two base sites it replaces are byte-identical (asserted above).
        now = {
            "classification": (CLASSIFICATION_RE, "search"),
            "corpus": (CORPUS_RE, "match"),
            "archive": (_FM_FENCE_RE, "match"),
            "checks.CONS-09": (_GOVERNED_FRONT_MATTER_RE, "match"),
            "checks.BUILD-02": (_GOVERNED_FRONT_MATTER_RE, "match"),
        }
        def twin_key(label: str) -> tuple[str, str, str]:
            """(prefix, tail, body) — the body is what varies between an input and its twin.

            Keyed on the TAIL too: without it the four tails of one prefix collapse onto one
            entry, the last of which is "no fence at all", and every twin lookup then finds a
            fenceless document that no gate could refuse. That mistake reported 405 unguarded
            shapes in a tree that has none.
            """
            prefix, _, rest = label.partition(" body=")
            body, _, tail = rest.partition(" tail=")
            return prefix, tail, body

        by_twin: dict[tuple[str, str], dict[str, str]] = {}
        for label, text in generate():
            prefix, tail, body = twin_key(label)
            by_twin.setdefault((prefix, tail), {})[body] = text

        unguarded: list[str] = []
        unguarded_shapes: list[str] = []
        for label, text in generate():
            prefix, tail, body = twin_key(label)
            governed_doc = body == "governed"
            for name, (head_rx, how) in now.items():
                if name not in base:
                    continue
                if not (getattr(base[name], how)(text) and not getattr(head_rx, how)(text)):
                    continue
                if _verdict(text) is not None:
                    continue
                if governed_doc:
                    unguarded.append(f"{name}: {label}")
                elif _verdict(by_twin[prefix, tail].get("governed", "")) is None:
                    unguarded_shapes.append(f"{name}: {prefix} tail={tail}")

        self.assertEqual(
            unguarded[:10], [],
            f"{len(unguarded)} GOVERNED input(s) are invisible to a reader AND accepted by the "
            "gate — a classified document like this can enter the tree and then go ungoverned, "
            "which is the defect fail-closed exists to make impossible",
        )
        self.assertEqual(
            sorted(set(unguarded_shapes))[:10], [],
            f"{len(set(unguarded_shapes))} shape(s) are lost by a reader and NOT refused even "
            "when they carry a classification — the ungoverned loss is priced, being unguarded "
            "when it matters is not",
        )

    def test_the_gate_is_at_least_as_strict_as_base(self) -> None:
        """`base REFUSED => HEAD REFUSED`, as a property over the whole grammar.

        HEAD may refuse MORE — an unparseable block is now a refusal — but never less.
        """
        base = self._base_patterns()
        if "classification" not in base:
            self.skipTest("base pattern unavailable — a shallow clone cannot prove this")
        for label, text in generate():
            if not base["classification"].search(text):
                continue
            if "classification" not in text:
                continue
            with self.subTest(input=label):
                self.assertTrue(
                    CLASSIFICATION_RE.search(text) is not None
                    or _verdict(text) is not None,
                    f"{label}: base saw front matter here, HEAD sees neither front matter nor an "
                    "unparseable block — the gate would read it as 'nothing to protect'",
                )


class TheGeneratorConsumesEveryDeclaredShape(unittest.TestCase):
    """A grammar entry no generator reads is the same as an absent one.

    ``MULTILINE_RUNS`` (V11/V12/V13) was added in round 4 to close the blank-line-separated-run gap
    and then referenced by nothing for a whole round: ``generate()`` never consumed the tuple, so not one differential
    input carried a blank-line-separated run and the shape the finding existed for was still
    missing. Nobody noticed, because every test that mattered was green — the inputs were simply
    absent, which is the failure mode this whole module was written to stop
    (a differential is only as strong as its input grammar).

    So consumption is asserted, not reviewed. Add a tuple to this module and forget to wire it in,
    and this test names it.
    """

    def test_every_declared_tuple_reaches_the_generated_corpus(self) -> None:
        corpus = [text for _, text in generate()]
        missing: list[str] = []
        for tuple_name, shapes in (
            ("COMMENT_FORMS", fmi.COMMENT_FORMS),
            ("MULTILINE_RUNS", fmi.MULTILINE_RUNS),
            ("INTERRUPTED_RUNS", fmi.INTERRUPTED_RUNS),
        ):
            for label, shape in shapes:
                if not any(shape in text for text in corpus):
                    missing.append(f"{tuple_name}: {label}")
        for label, shape in fmi.FUSED_SHAPES:
            stem = shape.split("%s")[0]
            if not any(stem in text for text in corpus):
                missing.append(f"FUSED_SHAPES: {label}")
        self.assertEqual(
            missing, [],
            "a declared shape never reaches generate(), so every test that iterates it is blind "
            "to that shape:\n  " + "\n  ".join(missing),
        )

    def test_the_module_declares_no_tuple_the_generator_ignores(self) -> None:
        """The half the test above cannot see: a NEW tuple nobody added to the loop.

        Checking the declared tuples reach the corpus proves nothing about a tuple the checker
        itself does not list. This one derives the list from the module instead.
        """
        declared = {
            name for name, value in vars(fmi).items()
            if name.isupper() and isinstance(value, tuple) and value
            and all(isinstance(v, tuple) and len(v) == 2 for v in value)
        }
        wired = {"COMMENT_FORMS", "MULTILINE_RUNS", "INTERRUPTED_RUNS", "FUSED_SHAPES",
                 "BODIES", "TAILS", "TIMING_UNITS"}
        self.assertEqual(
            declared - wired, set(),
            "front_matter_inputs declares a shape tuple that neither generate() nor a named "
            "consumer reads — wire it in, or this is the unconsumed-shape defect again",
        )


class TheInterruptedRunClassIsRefusedAtTheRealGate(unittest.TestCase):
    """The class that survived four rounds. Driven through ``classify_file`` itself.

    Round 5's verdict asked whether the residue's first line re-contained ``<!--``. For
    ``<!-- a -->`` / ``z`` / ``<!-- b -->`` / fence the residue's first line is ``z``, so it
    returned ``None``, ``classify_file`` fell through its ``if not _has_doc_header`` branch, and a
    ``classification: secret`` document committed clean outside the vault. Base 1.0.12 REFUSED it.
    One byte of junk was the whole bypass, and a table of shapes could not have found it — which
    is why the verdict now asks about REACHABILITY instead of shape.
    """

    GOVERNED = "---\nclassification: secret\nid: GATE-1\n---\n\nbody\n"

    def _refused(self, text: str) -> bool:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "docs" / "confidential").mkdir(parents=True)
            (root / ".gitignore").write_text("docs/confidential/\n")
            return classify_file("docs/x.md", text, root) is not None

    def test_every_interrupted_run_hiding_a_classification_is_refused(self) -> None:
        for label, run in fmi.INTERRUPTED_RUNS:
            with self.subTest(shape=label):
                self.assertTrue(
                    self._refused(run + self.GOVERNED),
                    f"{label}: a classified document behind an unparseable run committed clean — "
                    "this is the interrupted-run fail-open",
                )

    def test_the_same_runs_are_accepted_when_nothing_is_classified(self) -> None:
        """The other half of the amendment: no header behind the block, no refusal.

        Round 5 refused these too, and that refused ten copies of OpenZeppelin's
        `PULL_REQUEST_TEMPLATE.md` on this disk — an ordinary document with no front matter at all,
        rejected because an earlier line began ``<!--``. A gate that refuses documents it has
        nothing to protect is an availability cost with no security return.
        """
        for label, run in fmi.INTERRUPTED_RUNS:
            with self.subTest(shape=label):
                self.assertFalse(self._refused(run + "\njust prose, no front matter\n"), label)

    def test_the_openzeppelin_pull_request_template_is_accepted(self) -> None:
        """The measured availability cost, pinned as a literal so it cannot regress silently."""
        self.assertFalse(self._refused(
            "<!-- a -->\nFixes #???? <!-- Fill in with issue number -->\n\nbody\n"
        ))

    def test_a_non_opener_candidate_cannot_consume_a_real_opener_s_closing_fence(self) -> None:
        """The fail-open the dedupe would create without the O(1) opener test.

        Collapsing candidates that share one closing fence is what keeps the surviving slices
        disjoint, and it is sound ONLY because a candidate whose `---` is not a front-matter
        opener is rejected before it can claim that fence. Without the opener test, the first
        candidate below — `--> ---x`, a `---` followed by junk — would mark the shared fence as
        seen, answer "no classification here", and the genuine mid-line opener after it would
        never be examined. A `classification: secret` document would commit clean.

        Both candidates resolve to the same `\n---`; that is the whole point of the fixture.
        """
        text = "<!-- a -->\nz\n--> ---x\n--> ---\nclassification: secret\nid: X-1\n---\n"
        self.assertEqual(len(_REACHABLE_FENCE_RE.findall(text)), 2, "fixture must present both")
        self.assertIsNotNone(_verdict(text), "the genuine opener behind the junk one was skipped")
        self.assertTrue(self._refused(text))

    def test_a_run_landing_on_an_indented_fence_is_not_called_unparseable(self) -> None:
        """The readers spell the fence ``[ \\t]*---``, so an indented fence is a fence.

        Testing the residue with ``startswith("---")`` instead would send a document every reader
        parses correctly into the reachability scan, which would then refuse it with a message
        about a block that is not in fact unparseable.
        """
        self.assertIsNone(_verdict("<!-- a -->\n  " + self.GOVERNED))
        self.assertTrue(self._refused("<!-- a -->\n  " + self.GOVERNED))  # placement, not parsing


class TheRenderedOutputStripperIsLinear(unittest.TestCase):
    """The fifth comment regex was quadratic, and a regex could not fix it.

    ``rendered_output._COMMENT_RE.sub(" ", text)`` measured 13.8 ms at 4 KB and 908 ms at 32 KB of
    repeated unterminated ``<!--`` — 8x the input, 66x the time. The cause is not the inner
    pattern's backtracking (an unrolled-loop regex measured 3.4x WORSE) but ``re.sub`` retrying at
    every position after a failed match, which no pattern can prevent. A single ``str.find`` scan
    never re-reads consumed text.

    Ceiling is generous on purpose: this asserts the absence of quadratic growth, not a budget.
    """

    CEILING_MS = 200.0

    def test_32kb_of_unterminated_openers_is_linear(self) -> None:
        for label, unit in (("open repeated", "<!--"), ("nested opens", "<!--<!--")):
            with self.subTest(shape=label):
                text = (unit * 40000)[: 32 * 1024]
                start = time.perf_counter()
                _strip_html_comments(text)
                self.assertLess((time.perf_counter() - start) * 1000, self.CEILING_MS, label)

    def test_it_is_identical_to_the_pattern_it_replaced(self) -> None:
        """Equivalence with base's `<!--.*?-->` + DOTALL, which is what it must preserve."""
        legacy = re.compile("<" + "!--.*?-" + "->", re.DOTALL)
        random.seed(11)
        cases = [
            "<!-- a --><p>x</p><!-- b -->", "<p>none</p>", "<!-- multi\nline -->tail", "<!--->x",
            "<!-- a --", "a<!--b-->c<!--d-->e", "<!-- -- -->", "<!--" * 50 + "-->", "", "-->",
        ]
        cases += [
            "".join(random.choice(["<!--", "-->", "x", "\n", " ", "<!-- a -->"]) for _ in range(60))
            for _ in range(2000)
        ]
        for case in cases:
            self.assertEqual(_strip_html_comments(case), legacy.sub(" ", case), repr(case[:60]))


if __name__ == "__main__":
    unittest.main()


class TheGuardResolvesEveryWayAnReAliasCanBeBound(unittest.TestCase):
    """The duplicate-run guard has now been blind three times in the same shape.

    The first version hunted hand-written pattern SPELLINGS and missed a fourth. The second
    replaced that with a structural rule but only saw single constants, so a two-fragment assembly
    escaped. The third taught it `import re as _rx` and left the ASSIGNMENT form — `_r = re`, then
    `_r.compile(rf"…")` — which passed the guard on a real duplicate comment run, measured at
    the copy's build 1.0.13. Each round the hand-written list got one level more abstract: pattern
    spellings, then import spellings, now BINDING FORMS.

    So the bindings are derived rather than listed, the same way `_candidate_patterns` already
    derives string constants, and this asserts the derivation directly instead of waiting for an
    offender to exist in the tree.
    """

    @staticmethod
    def _aliases(source: str) -> tuple[frozenset[str], frozenset[str]]:
        return _re_module_aliases(ast.parse(source))

    def test_an_assigned_module_alias_is_resolved(self) -> None:
        modules, _ = self._aliases("import re\n_r = re\n")
        self.assertIn("_r", modules)

    def test_a_chain_written_out_of_dependency_order_is_resolved(self) -> None:
        """Assignments need not be topologically ordered, and a single pass sees only one link."""
        modules, _ = self._aliases("import re\n_b = _a\n_a = re\n")
        self.assertIn("_a", modules)
        self.assertIn("_b", modules, "the fixpoint is what makes order irrelevant")

    def test_an_assigned_entry_point_is_resolved_as_a_function(self) -> None:
        """`_c = re.compile` is the assignment twin of `from re import compile as _c`."""
        _, funcs = self._aliases("import re\n_c = re.compile\n")
        self.assertIn("_c", funcs)

    def test_an_unrelated_assignment_is_not_mistaken_for_the_module(self) -> None:
        """The other direction: over-resolving would flag innocent modules as re-callers."""
        modules, funcs = self._aliases("import os\n_o = os\n_x = 'not a module'\n")
        self.assertNotIn("_o", modules)
        self.assertNotIn("_x", modules)
        self.assertEqual(funcs, frozenset())
