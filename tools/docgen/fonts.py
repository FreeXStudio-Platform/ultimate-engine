"""Vendored Atlas fonts -> self-contained @font-face CSS (RULEBOOK L15/L21).

Space Grotesk (variable, wght 300-700), Inter (static 300/400/500/600), and JetBrains Mono
(static 400/400-italic/500) are vendored from ``brand-source/atlas/fonts/`` — the
same OFL-licensed files the marketing site self-hosts (see ``assets/fonts/LICENSE-OFL.txt``).
Embedding them as base64 data-URIs means every rendered doc shows the real Atlas faces with
zero network dependency: no CDN request, no silent system-font substitution.

Space Grotesk ships as a single variable-font file covering weights 300-700, so it gets ONE
``@font-face`` rule with a weight *range* (``font-weight: 300 700``) rather than duplicating
the ~22KB payload per named weight.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Final

_FONTS_DIR: Final[Path] = Path(__file__).resolve().parent / "assets" / "fonts"
_WOFF2_MAGIC: Final[bytes] = b"wOF2"

# (family, weight-or-range, style, filename)
_STATIC_FACES: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("Inter", "300", "normal", "inter-300.woff2"),
    ("Inter", "400", "normal", "inter-400.woff2"),
    ("Inter", "500", "normal", "inter-500.woff2"),
    ("Inter", "600", "normal", "inter-600.woff2"),
    ("JetBrains Mono", "400", "normal", "jetbrains-mono-400.woff2"),
    # NO italic monospace face is declared, on purpose (2026-08-21).
    #
    # `jetbrains-mono-400-italic.woff2` was byte-identical to the upright face — same sha256 — while
    # being declared to CSS as a real `font-style: italic`. So italic monospace rendered UPRIGHT in
    # every generated document, silently, and the browser would not synthesize an oblique precisely
    # BECAUSE a genuine italic face was supplied. Declaring nothing is strictly better than
    # declaring a lie: the browser now synthesizes an oblique, which is visibly italic.
    #
    # If a real italic is ever vendored, add it here — `test_fonts.py` asserts no two declared faces
    # share a digest, so a copy cannot silently take its place again.
    ("JetBrains Mono", "500", "normal", "jetbrains-mono-500.woff2"),
)
_VARIABLE_FACES: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("Space Grotesk", "300 700", "normal", "space-grotesk-variable.woff2"),
)


def _data_uri(filename: str) -> str:
    """Read a vendored woff2 file and return it as a base64 ``data:`` URI (fail-closed on bad magic)."""
    data = (_FONTS_DIR / filename).read_bytes()
    if data[:4] != _WOFF2_MAGIC:
        raise ValueError(f"{filename!r} is not a valid WOFF2 file (bad magic bytes)")
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:font/woff2;base64,{encoded}"


def _face_rule(family: str, weight: str, style: str, filename: str) -> str:
    uri = _data_uri(filename)
    return (
        "@font-face {\n"
        f'  font-family: "{family}";\n'
        f"  font-style: {style};\n"
        f"  font-weight: {weight};\n"
        "  font-display: swap;\n"
        f'  src: url({uri}) format("woff2");\n'
        "}"
    )


def build_font_face_css() -> str:
    """Emit the full self-contained ``@font-face`` CSS block for all vendored Atlas fonts.

    No ``@import``, no ``https://``/``http://`` reference — every byte is embedded. Deterministic
    (same input files -> same output string every call).
    """
    rules = [_face_rule(*face) for face in (*_VARIABLE_FACES, *_STATIC_FACES)]
    header = (
        "/* Vendored Atlas fonts (OFL) - see assets/fonts/LICENSE-OFL.txt. Self-contained: "
        "no CDN, no @import. */"
    )
    return "\n".join((header, *rules))
