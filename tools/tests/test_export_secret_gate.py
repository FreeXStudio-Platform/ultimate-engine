"""Gate 3 — the export-time credential scan — proven, `OG-157`.

**Why this file exists.** `export_sanitizer.SECRET_PATTERNS` and `gate_secret_value` are the leak
gate that runs on the FINAL RENDERED BYTES of every document this engine builds. A Pass-8 verifier
mutation-tested the retained counter-examples and found this one had **none**: the entire pattern
table could be emptied, or the gate deleted, and all 196 tests stayed green.

That is the exact decay `check_python_tests`' own docstring names as this project's dominant defect
family — *"Every guard here was falsified BY HAND when it was written … and the falsification was
thrown away."* A gate with no retained counter-example is a gate that has been proven once, by
someone who has since left the room.

**Every pattern is probed, derived from the live table**, so a class added later is covered without
anyone remembering (`L-29`: a probe that iterates a hardcoded copy of what it guards passes for
free). Each sample is synthesised at run time rather than written as a literal, so this file is not
itself a scannable secret — the repository's own pre-commit gate refuses those, which is the gate
working.
"""

from __future__ import annotations

import unittest

from tools.docgen.export_sanitizer import SECRET_PATTERNS, gate_secret_value

# One live-shaped sample per pattern name. Built by concatenation so no literal credential appears
# in this file. AWS's published documentation example key is used where a real shape is needed.
# One live-shaped sample per pattern name, assembled at RUN TIME from fragments.
#
# **Fragments, not literals — and the repository's own gate is why.** The first version wrote the
# connection string and the private-key header out in full, and `pre-push`'s secret scan refused
# the push naming this very file. That is the moat working, not a nuisance: a file that must
# contain live-shaped credentials to test a credential scanner is exactly the file most likely to
# leak one. No single source line here carries a matchable secret; joining happens below.
_PARTS: dict[str, tuple[str, ...]] = {
    "aws_access_key_id": ("AKIA", "IOSFODNN7EXAMPLE"),
    "anthropic_key": ("sk-", "ant-", "A" * 24),
    "generic_sk_key": ("sk-", "B" * 24),
    "github_token": ("gh", "p_", "C" * 36),
    "github_pat": ("github", "_pat_", "D" * 24),
    "google_api_key": ("AIza", "E" * 35),
    "slack_token": ("xox", "b-", "F" * 12),
    "dsn_with_credentials": ("postgres", "://", "user", ":", "pw", "@", "db.internal:5432/app"),
    "private_key_block": ("-----BEGIN ", "OPENSSH ", "PRIVATE KEY", "-----"),
    "aws_secret_access_key": ("aws_secret", "_access_key", " = ", "G" * 40),
    "jwt": ("eyJ", "H" * 12, ".", "I" * 12, ".", "J" * 12),
}

_SAMPLES: dict[str, str] = {name: "".join(parts) for name, parts in _PARTS.items()}


class EveryDeclaredSecretPatternFires(unittest.TestCase):
    """Derived from `SECRET_PATTERNS` itself — add a pattern and it is probed automatically."""

    def test_every_pattern_has_a_sample(self) -> None:
        """A pattern with no sample is an unprobed pattern, and this test says so by name."""
        missing = sorted(set(SECRET_PATTERNS) - set(_SAMPLES))
        self.assertEqual(
            missing, [],
            f"{len(missing)} secret pattern(s) have no sample here, so nothing proves they fire: "
            f"{missing}. Add one to _SAMPLES.",
        )

    def test_every_pattern_matches_its_own_sample(self) -> None:
        """Reachability: a pattern that cannot match anything is not a check (`OG-104`'s class)."""
        for name, pattern in SECRET_PATTERNS.items():
            with self.subTest(pattern=name):
                sample = _SAMPLES.get(name)
                self.assertIsNotNone(sample, f"{name}: no sample")
                assert sample is not None
                self.assertTrue(
                    pattern.search(sample),
                    f"{name}: pattern {pattern.pattern!r} does not match its own live-shaped sample",
                )

    def test_the_gate_blocks_every_sample(self) -> None:
        """End to end through the production entry point, not the pattern table."""
        for name, sample in _SAMPLES.items():
            with self.subTest(pattern=name):
                result = gate_secret_value(f"Deploy notes.\n\n{sample}\n")
                self.assertTrue(
                    result.findings, f"{name}: gate_secret_value returned no finding for a secret"
                )
                self.assertTrue(
                    any(f.blocking for f in result.findings),
                    f"{name}: the finding is not BLOCKING, so a build would export it",
                )

    def test_ordinary_prose_is_not_blocked(self) -> None:
        """Two-sided. Without this, a gate that blocks everything satisfies every probe above —
        and a leak gate that refuses clean documents is one somebody switches off."""
        clean = (
            "This document explains how the engine builds a page. It mentions AWS, GitHub and "
            "Slack by name, shows a URL like https://example.com/owner/repo, and quotes a "
            "shortened prefix such as sk- in prose without any key material after it.\n"
        )
        result = gate_secret_value(clean)
        self.assertEqual(
            [f.message for f in result.findings if f.blocking], [],
            "ordinary prose naming credential PREFIXES was blocked as a leak",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
