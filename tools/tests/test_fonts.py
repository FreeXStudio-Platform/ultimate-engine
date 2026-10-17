"""Counter-example for the vendored font faces.

The italic monospace face was a byte-identical copy of the upright one, declared to CSS as a real
italic. Italic monospace therefore rendered upright in every generated document, silently — and
because a genuine `@font-face` italic WAS supplied, the browser would not synthesize an oblique
fallback. A duplicate that claims to be a distinct face is worse than a missing face.
"""

from __future__ import annotations

import hashlib
import unittest

from tools.docgen import fonts


class NoTwoDeclaredFacesAreTheSameFile(unittest.TestCase):
    def _digests(self) -> dict[str, list[str]]:
        by_digest: dict[str, list[str]] = {}
        for family, weight, style, filename in fonts._STATIC_FACES + fonts._VARIABLE_FACES:
            data = (fonts._FONTS_DIR / filename).read_bytes()
            by_digest.setdefault(hashlib.sha256(data).hexdigest(), []).append(
                f"{family} {weight} {style} ({filename})"
            )
        return by_digest

    def test_the_scan_finds_faces(self) -> None:
        """Guard against the vacuous pass — an empty face set would make the assertion trivial."""
        self.assertGreater(len(fonts._STATIC_FACES), 3)

    def test_every_declared_face_is_a_distinct_file(self) -> None:
        duplicates = {d: names for d, names in self._digests().items() if len(names) > 1}
        self.assertEqual(
            duplicates, {},
            "two declared faces share a digest — one of them is a copy pretending to be a "
            "different style or weight, and it will render as the face it actually is",
        )

    def test_every_declared_face_file_exists_and_is_woff2(self) -> None:
        for _family, _weight, _style, filename in fonts._STATIC_FACES + fonts._VARIABLE_FACES:
            path = fonts._FONTS_DIR / filename
            with self.subTest(filename=filename):
                self.assertTrue(path.is_file(), f"{filename} is declared but absent")
                self.assertEqual(path.read_bytes()[:4], b"wOF2", f"{filename} is not WOFF2")

    def test_no_orphan_font_files(self) -> None:
        """A vendored face nothing declares is dead weight embedded in nothing — or worse, a file
        someone will later 'restore' into the table without checking what it is."""
        declared = {f for *_rest, f in fonts._STATIC_FACES + fonts._VARIABLE_FACES}
        on_disk = {p.name for p in fonts._FONTS_DIR.glob("*.woff2")}
        self.assertEqual(sorted(on_disk - declared), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
