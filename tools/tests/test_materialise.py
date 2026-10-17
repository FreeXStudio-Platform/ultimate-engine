"""Counter-examples for blob materialisation — the shared root of three proven defects.

Both hooks used to fork once per blob and hand the scanner raw bytes. That single shape produced a
fork storm that denied the gate, an encoding class the scanner could not read, and a submodule that
could not be committed at all. These are the inputs that broke each.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.docgen.hooks import materialise as _materialise_module
from tools.docgen.hooks.materialise import (
    looks_utf16_or_32,
    materialise,
    normalise_for_scanning,
)


def _repo_root() -> Path:
    from tools.corpus_check.corpus import repo_root

    return repo_root()


_KEY = "AKIA" + "IOSFODNN7EXAMPLE"     # split so this file is not itself a scannable secret


class EncodingDetection(unittest.TestCase):
    """A blob that natively IS UTF-16 defeats a grep-based scanner completely: the pattern cannot
    match across interleaved NULs. Fixing `working-tree-encoding` earlier only moved this hole."""

    def test_plain_ascii_is_not_touched(self) -> None:
        self.assertIsNone(looks_utf16_or_32(b"AWS_ACCESS_KEY_ID=" + _KEY.encode()))
        self.assertEqual(normalise_for_scanning(b"hello"), (b"hello", None))

    def test_bom_less_utf16_le_is_detected(self) -> None:
        self.assertEqual(looks_utf16_or_32(f"KEY={_KEY}\n".encode("utf-16-le")), "utf-16-le")

    def test_bom_less_utf16_be_is_detected(self) -> None:
        self.assertEqual(looks_utf16_or_32(f"KEY={_KEY}\n".encode("utf-16-be")), "utf-16-be")

    def test_bom_prefixed_forms_are_detected(self) -> None:
        """`P8-099`: this used to loop only `("utf-16", "utf-32")` and assert `assertIsNotNone`.

        Both of those are Python's *native-endian* codecs — little-endian on every machine this
        suite has run on — so the two big-endian rows in `materialise._BOMS`
        (`utf-16-be`/`utf-32-be`) were never actually exercised: a regression that broke only
        big-endian detection (e.g. swapping the `_BOMS` order, or a typo'd BE marker byte) would
        pass this test every time. Iterating `_BOMS` itself, and asserting the exact encoding name
        `looks_utf16_or_32` returns (not just "some truthy string"), closes both gaps: every BOM
        row is reachable, and a detector that returns the WRONG encoding for a right BOM now fails
        instead of passing on `assertIsNotNone` alone.
        """
        payload = f"KEY={_KEY}\n".encode("ascii")
        for bom, expected_encoding in _materialise_module._BOMS:
            with self.subTest(bom=bom, expected_encoding=expected_encoding):
                self.assertEqual(looks_utf16_or_32(bom + payload), expected_encoding)

    def test_transcoding_makes_the_key_visible_to_a_text_scanner(self) -> None:
        raw = f"AWS_ACCESS_KEY_ID={_KEY}\n".encode("utf-16-le")
        self.assertNotIn(_KEY.encode(), raw, "precondition: invisible before transcoding")
        out, enc = normalise_for_scanning(raw)
        self.assertIn(_KEY.encode(), out)
        # The label NAMES the encoding rather than equalling it. It became compound
        # (`utf-16-le+ascii-runs:utf-16-le`) when normalisation stopped replacing the blob and
        # started appending readable views to it — an exact-equality assertion on a label is a
        # test of a diagnostic string, not of the behaviour, and it broke on a fix that made the
        # module strictly better. What matters is that the operator-facing note says which
        # encoding was read.
        self.assertIsNotNone(enc)
        self.assertIn("utf-16-le", enc or "")

    def test_no_wire_form_of_the_same_secret_escapes_the_scanner(self) -> None:
        """**Every encoding a real editor emits, carrying one key, all must surface it.**

        The class, not the instance (`docs/process/RULES.md` Rule 1). Each fix here closed one
        encoding and left its siblings: UTF-16 with a BOM, then without, then UTF-32 without —
        and finally a UTF-16 document padded with CJK, whose two-byte codepoints drop NUL density
        to 0.0004 and sail under the detector's 0.10 threshold with an ASCII key intact inside it.
        Enumerating the wire forms is what stops the next one being found by an attacker.
        """
        secret = f"aws_secret = {_KEY}\n"
        pad = "文書説明" * 1500  # non-ASCII padding: the case that defeats NUL-density detection
        forms = {
            "utf-8": secret.encode(),
            "cp1252": secret.encode("cp1252"),
            "utf-16 (BOM)": secret.encode("utf-16"),
            "utf-32 (BOM)": secret.encode("utf-32"),
            "utf-16-le": secret.encode("utf-16-le"),
            "utf-16-be": secret.encode("utf-16-be"),
            "utf-32-le": secret.encode("utf-32-le"),
            "utf-32-be": secret.encode("utf-32-be"),
            "utf-16-le + CJK padding": (pad + secret + pad).encode("utf-16-le"),
            "utf-16-be + CJK padding": (pad + secret + pad).encode("utf-16-be"),
            "utf-32-le + CJK padding": (pad + secret + pad).encode("utf-32-le"),
            "utf-32-be + CJK padding": (pad + secret + pad).encode("utf-32-be"),
        }
        for label, raw in forms.items():
            with self.subTest(wire_form=label):
                out, _enc = normalise_for_scanning(raw)
                self.assertIn(
                    _KEY.encode(), out,
                    f"{label}: the key is not greppable after normalisation — a scanner would "
                    "report this blob clean",
                )

    def test_a_tracked_binary_asset_is_not_multiplied(self) -> None:
        """The cost side of the union. A gate people wait for is a gate people bypass.

        Two discriminators were tried and measured wrong before this one: printable-byte share
        (rejects CJK, the very payload) and decode damage (compressed bytes land on valid BMP
        codepoints, so a `.woff2` scored clean and grew 150%). Extracting ASCII runs from a UTF-8
        encoding of each view is what made real assets grow by nothing at all.
        """
        import subprocess

        root = _repo_root()
        listed = subprocess.run(
            ("git", "-C", str(root), "ls-files"), capture_output=True, text=True, check=False
        ).stdout.split()
        assets = [f for f in listed if f.endswith((".woff2", ".png", ".ico", ".jpg", ".gz"))]
        self.assertTrue(assets, "no tracked binary assets found; this probe would be vacuous")
        for rel in assets:
            with self.subTest(asset=rel):
                data = (root / rel).read_bytes()
                out, _enc = normalise_for_scanning(data)
                self.assertLessEqual(
                    len(out), len(data) * 1.10,
                    f"{rel} grew from {len(data)} to {len(out)} bytes",
                )

    def test_an_empty_blob_is_handled(self) -> None:
        self.assertIsNone(looks_utf16_or_32(b""))

    def test_a_binary_blob_without_a_bom_is_not_mangled_into_nonsense(self) -> None:
        """Over-eager transcoding is its own defect — a PNG must not be rewritten."""
        png = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4
        out, enc = normalise_for_scanning(png)
        if enc is None:
            self.assertEqual(out, png)


class MaterialiseFromGit(unittest.TestCase):
    """End-to-end against a real repository, because the batch protocol is the thing under test."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        self._git("init", "-q", "-b", "master", ".")
        self._git("config", "user.email", "t@x")
        self._git("config", "user.name", "t")

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(("git", "-C", str(self.repo), *args),
                              capture_output=True, text=True, check=False, timeout=60)

    def _blob(self, data: bytes) -> str:
        proc = subprocess.run(("git", "-C", str(self.repo), "hash-object", "-w", "--stdin"),
                              input=data, capture_output=True, check=True, timeout=60)
        return proc.stdout.decode().strip()

    def test_a_utf16_blob_is_written_transcoded(self) -> None:
        sha = self._blob(f"AWS_ACCESS_KEY_ID={_KEY}\n".encode("utf-16-le"))
        dest = Path(self._tmp.name) / "out"
        result = materialise([(sha, "windows.ps1")], dest, self.repo)
        self.assertEqual(result.written, 1)
        self.assertIn(_KEY, (dest / sha).read_text(encoding="utf-8"))
        self.assertTrue(result.transcoded)

    def test_many_blobs_in_one_batch(self) -> None:
        """The fork storm: 1000 tiny files took 331 s, of which 9.9 s was compute. One process now."""
        records = [(self._blob(f"file {i}\n".encode()), f"f{i}.txt") for i in range(200)]
        dest = Path(self._tmp.name) / "many"
        result = materialise(records, dest, self.repo)
        self.assertEqual(result.written, 200)
        self.assertEqual(result.failed, [])

    def test_a_gitlink_is_skipped_not_fatal(self) -> None:
        """A submodule pointer's 'blob sha' is a COMMIT sha. `cat-file blob` fails on it, and the
        hook used to refuse the whole commit with no path named and no exit but a total bypass —
        the moat teaching its own bypass."""
        (self.repo / "a.txt").write_text("x", encoding="utf-8")
        self._git("add", "a.txt")
        self._git("commit", "-q", "-m", "base", "--no-verify")
        commit_sha = self._git("rev-parse", "HEAD").stdout.strip()
        dest = Path(self._tmp.name) / "gl"
        result = materialise([(commit_sha, "vendor/sub")], dest, self.repo)
        self.assertEqual(result.failed, [], "a gitlink must not be a failure")
        self.assertEqual(result.skipped_gitlinks, ["vendor/sub"])

    def test_a_missing_object_is_reported_not_swallowed(self) -> None:
        dest = Path(self._tmp.name) / "miss"
        result = materialise([("0" * 40, "ghost.txt")], dest, self.repo)
        self.assertTrue(result.failed, "an unreadable object must never be a silent skip")

    def test_blobs_are_named_by_sha_not_path(self) -> None:
        """Load-bearing three times: it defeats the scanner's basename self-exclusion, makes case
        collision impossible, and keeps a hostile path out of the shell."""
        sha = self._blob(b"content\n")
        dest = Path(self._tmp.name) / "named"
        materialise([(sha, "kit/secret-scan.sh")], dest, self.repo)
        self.assertTrue((dest / sha).is_file())
        self.assertFalse((dest / "secret-scan.sh").exists())


class CliUsageMentionsStdin(unittest.TestCase):
    """Retained counter-example for `P8-109`.

    `main()`'s docstring always documented that it reads ``<sha>\\t<path>`` lines on stdin, but the
    printed usage line — what a caller actually sees at the command line on a bad invocation — named
    only the two positional args and never mentioned stdin at all.
    """

    def test_usage_line_names_stdin(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "tools.docgen.hooks.materialise"],
            input="", capture_output=True, text=True, timeout=30, check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("stdin", proc.stderr)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
