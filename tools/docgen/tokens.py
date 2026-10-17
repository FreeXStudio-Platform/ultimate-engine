"""Atlas design tokens -> CSS (RULEBOOK L15/L21, DESIGN_SYSTEM.md sections 1-3).

Loads ``assets/tokens.json`` (vendored from the Atlas — never fork values here, re-vendor
instead) and emits a single self-contained stylesheet: vendored ``@font-face`` faces
(``fonts.build_font_face_css()``), dark (native) + light (report/print) themes, brand +
severity variables, the Atlas ``.t-*`` type-role classes, spacing/radii, the blueprint
diagram canvas (``.svgwrap``), and the doc-system component CSS (masthead, classification
badge, data table, figure, callout, verified stamp, theme toggle).

Stdlib only; mypy --strict clean; no network references (no ``@import``, no CDN links) —
fonts are embedded as base64 data-URIs, not fetched.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from tools.docgen.figure_support import (
    FIG_FIT_H_PX,
    FIG_FIT_VH,
    FIG_MAX_W_PX,
    FIG_MIN_SCALE,
)
from tools.docgen.fonts import build_font_face_css

_ASSETS_DIR: Final[Path] = Path(__file__).resolve().parent / "assets"
_TOKENS_PATH: Final[Path] = _ASSETS_DIR / "tokens.json"


class TokensUnavailable(RuntimeError):
    """The design-token source could not be read.

    Raised instead of letting a bare ``JSONDecodeError``/``OSError`` escape at IMPORT time. Every
    entry point imports this module, so a corrupt ``tokens.json`` killed ``docgen manifest`` — and
    anything else — with a raw traceback that named a JSON column and not the problem. Fail-closed
    is right (a document rendered without its design tokens is not the document); an unreadable
    stack trace is not.
    """


def _load_tokens(path: Path = _TOKENS_PATH) -> dict[str, object]:
    """Load the vendored Atlas token JSON. Fail-CLOSED, with a diagnosis rather than a traceback."""
    try:
        with path.open("r", encoding="utf-8") as f:
            data: dict[str, object] = json.load(f)
    except (OSError, ValueError) as exc:
        raise TokensUnavailable(
            f"{path} could not be read as JSON ({exc}). Every rendered document depends on it, so "
            "the engine refuses rather than rendering an unstyled artifact. Restore the file from "
            "git: `git checkout -- tools/docgen/assets/tokens.json`."
        ) from exc
    if not isinstance(data, dict) or not data:
        raise TokensUnavailable(
            f"{path} parsed but is {type(data).__name__} and/or empty — the token set cannot be "
            "empty; every colour, size and spacing value in a rendered document comes from it."
        )
    return data


_TOKENS_CACHE: dict[str, object] | None = None


def tokens_data() -> dict[str, object]:
    """The token set, loaded on FIRST USE rather than at import.

    Module-level `TOKENS = _load_tokens()` raised during import, so no caller could ever catch it:
    every entry point imports this module, and a corrupt tokens.json killed `docgen manifest` and
    everything else with a raw traceback before `main()` existed to handle it. Deferring the load
    keeps the fail-closed behaviour and moves the failure somewhere a caller can turn into a
    diagnosis.
    """
    global _TOKENS_CACHE
    if _TOKENS_CACHE is None:
        _TOKENS_CACHE = _load_tokens()
    return _TOKENS_CACHE


def __getattr__(name: str) -> object:
    """Keep `tokens.TOKENS` working for existing callers, now lazily."""
    if name == "TOKENS":
        return tokens_data()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _css_vars(prefix_map: dict[str, str]) -> str:
    """Render a flat name->value mapping as ``--name:value;`` lines (2-space indented)."""
    lines = [f"  --{name}:{value};" for name, value in prefix_map.items()]
    return "\n".join(lines)


def _sub(name: str) -> dict[str, str]:
    """Fetch a nested string-keyed, string-valued sub-object from ``TOKENS`` (e.g. ``"brand"``)."""
    value = tokens_data()[name]
    if not isinstance(value, dict):
        raise TypeError(f"tokens.json[{name!r}] is not an object: {type(value).__name__}")
    return {str(k): str(v) for k, v in value.items()}


def build_css() -> str:
    """Emit the full self-contained doc-system stylesheet from ``TOKENS``.

    Includes the vendored ``@font-face`` rules (real Space Grotesk/Inter/JetBrains Mono faces,
    embedded as base64 data-URIs — see ``fonts.py``), both ``:root``/``[data-theme=dark]`` and
    ``[data-theme=light]`` grounds/inks, brand + severity variables, the Atlas ``.t-*``
    type-role classes (system-stack fallbacks after the real face, never a serif), spacing/
    radii, the ``.svgwrap`` blueprint grid, table/badge/callout/masthead component rules, a
    ``prefers-reduced-motion`` guard, and a visible ``:focus-visible`` ring. No ``@import``,
    no CDN reference — every font byte is embedded, so a self-contained render always shows
    the real Atlas faces rather than silently substituting a system font.
    """
    grounds_dark = _sub("grounds_dark")
    inks_dark = _sub("inks_dark")
    grounds_light = _sub("grounds_light")
    inks_light = _sub("inks_light")
    brand = _sub("brand")
    severity = _sub("severity")
    fonts = _sub("fonts")
    weights = _sub("weights")
    font_size = _sub("font_size")
    line_height = _sub("line_height")
    spacing = _sub("spacing")
    radii = _sub("radii")
    layout = _sub("layout")
    diagram = _sub("diagram")

    dark_vars = _css_vars(
        {
            "ink": grounds_dark["ink"],
            "night": grounds_dark["night"],
            "steel": grounds_dark["steel"],
            "steel-2": grounds_dark["steel-2"],
            "bone": inks_dark["bone"],
            "ash": inks_dark["ash"],
            "mute": inks_dark["mute"],
            "faint": inks_dark["faint"],
            "bg": "var(--night)",
            "paper": "var(--night)",
            "paper-2": "var(--steel)",
            "fg": "var(--bone)",
            # Distinct-named aliases for embedded third-party SVG (tools/docgen/mermaid_bridge.py):
            # those SVGs set their OWN local --bg/--fg on their own root element, which would
            # make a literal var(--bg) self-referencing (CSS treats that as a cycle -> the
            # guaranteed-invalid value, not "inherit from the page" — confirmed by rendering,
            # not assumed). Aliasing under different names one level up avoids the cycle: the
            # embedded SVG references var(--mermaid-bg), which is NOT redefined locally on the
            # SVG itself, so it correctly inherits this page-level value.
            "mermaid-bg": "var(--bg)",
            "mermaid-fg": "var(--fg)",
        }
    )
    light_vars = _css_vars(
        {
            "ink": grounds_light["ink"],
            "night": grounds_light["night"],
            "steel": grounds_light["steel"],
            "steel-2": grounds_light["steel-2"],
            "bone": inks_light["bone"],
            "ash": inks_light["ash"],
            "mute": inks_light["mute"],
            "faint": inks_light["faint"],
            "bg": grounds_light["night"],
            "paper": grounds_light["night"],
            "paper-2": grounds_light["steel"],
            "fg": inks_light["bone"],
            "mermaid-bg": "var(--bg)",
            "mermaid-fg": "var(--fg)",
        }
    )
    brand_vars = _css_vars(
        {
            "shield": brand["shield"],
            "shield-hi": brand["shield-hi"],
            "shield-dim": brand["shield-dim"],
            "bronze": brand["bronze"],
            "bronze-hi": brand["bronze-hi"],
            "ember": brand["ember"],
            "ember-hi": brand["ember-hi"],
            "gold": brand["gold"],
            "gold-hi": brand["gold-hi"],
            "gold-mark": brand["gold-mark"],
            "verify": brand["verify"],
            "sev-crit": severity["crit"],
            "sev-high": severity["high"],
            "sev-med": severity["med"],
            "sev-med-hi": severity["med-hi"],
            "sev-low": severity["low"],
            "sev-info": severity["info"],
            "accent": "var(--shield-hi)",
            "shield-glow": "#4A7FC126",
            "f-display": fonts["display"],
            "f-body": fonts["body"],
            "f-mono": fonts["mono"],
            "fw-label": str(weights["label"]),
            "fw-eyebrow": str(weights["eyebrow"]),
            "fw-body": str(weights["body"]),
            "fw-emphasis": str(weights["emphasis"]),
            "fw-button": str(weights["button"]),
            "fw-display": str(weights["display"]),
            "maxw": layout["maxw"],
            "pad": layout["pad"],
            "r-xs": radii["xs"],
            "r-sm": radii["sm"],
            "r-md": radii["md"],
            "r-lg": radii["lg"],
            "r-pill": radii["pill"],
            "diagram-grid": diagram["grid"],
        }
    )
    fs_vars = _css_vars({f"fs-{k}": v for k, v in font_size.items()})
    lh_vars = _css_vars({f"lh-{k}": v for k, v in line_height.items()})
    sp_vars = _css_vars({f"g{k}": v for k, v in spacing.items()})
    font_faces = build_font_face_css()

    return f"""\
/* doc-system stylesheet — generated by tools/docgen/tokens.py from assets/tokens.json.
   Self-contained: no @import, no CDN — fonts embedded as base64 data-URIs below. Do not
   hand-edit; edit the token source and rebuild (RULEBOOK L7). */

{font_faces}

:root, [data-theme="dark"] {{
{dark_vars}
}}

[data-theme="light"] {{
{light_vars}
}}

:root {{
{brand_vars}
{fs_vars}
{lh_vars}
{sp_vars}
  /* The figure size standard (FS-1 … FS-5, docs/design/FIGURE_SYSTEM.md §12): the numbers live in figure_support.py. */
  --fig-max-w: {FIG_MAX_W_PX}px;
  --fig-fit-h: min({FIG_FIT_VH}vh, {FIG_FIT_H_PX}px);
  --fig-min-scale: {FIG_MIN_SCALE:g};
  /* The blueprint grid is ground, not data: a few percent of the page ink, so it is there when you look and gone when you read. */
  --grid-line: color-mix(in srgb, var(--fg) 6%, transparent);
}}

* {{ box-sizing: border-box; }}

html {{ color-scheme: dark light; }}

body {{
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font-family: var(--f-body);
  font-weight: var(--fw-body);
  font-size: var(--fs-base);
  line-height: var(--lh-base);
  -webkit-font-smoothing: antialiased;
}}

.doc-root {{
  max-width: var(--maxw);
  margin: 0 auto;
  padding: var(--pad);
}}

/* ---- Atlas type-role classes (DESIGN_SYSTEM.md §2) ---- */
.t-h1, .t-h2, .t-h3, .t-h4 {{
  font-family: var(--f-display);
  font-weight: var(--fw-display);
  line-height: var(--lh-tight);
  letter-spacing: -0.01em;
  text-wrap: balance;
  margin: 0;
}}
.t-h1 {{ font-size: var(--fs-4xl); }}
.t-h2 {{ font-size: var(--fs-3xl); }}
.t-h3 {{ font-size: var(--fs-2xl); }}
.t-h4 {{ font-size: var(--fs-xl); }}

.t-lede {{
  font-family: var(--f-body);
  font-weight: var(--fw-body);
  font-size: var(--fs-lg);
  line-height: var(--lh-loose);
  max-width: 68ch;
}}
.t-body {{
  font-family: var(--f-body);
  font-weight: var(--fw-body);
  font-size: var(--fs-base);
  line-height: var(--lh-base);
  max-width: 68ch;
}}
.t-body-sm {{
  font-family: var(--f-body);
  font-weight: var(--fw-body);
  font-size: var(--fs-sm);
  line-height: var(--lh-base);
}}
.t-mono-label {{
  font-family: var(--f-mono);
  font-weight: var(--fw-label);
  font-size: var(--fs-xs);
  letter-spacing: 0.18em;
  text-transform: uppercase;
}}
.t-mono-data {{
  font-family: var(--f-mono);
  font-weight: var(--fw-body);
  font-variant-numeric: tabular-nums;
  font-size: var(--fs-sm);
}}
.t-caption, .t-eyebrow {{
  font-family: var(--f-mono);
  font-weight: var(--fw-eyebrow);
  font-size: var(--fs-xs);
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ash);
}}

/* ---- Masthead ---- */
.masthead {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--g4);
  padding-bottom: var(--g5);
  border-bottom: 1px solid var(--faint);
  margin-bottom: var(--g6);
}}
.masthead-brand {{ display: flex; align-items: center; gap: var(--g3); }}
.masthead-logo {{ width: 28px; height: 28px; color: var(--fg); flex: none; }}
.masthead-titles {{ display: flex; flex-direction: column; gap: var(--g1); }}
.masthead-meta {{ display: flex; align-items: center; gap: var(--g3); flex-wrap: wrap; }}

/* ---- Classification badge ---- */
.badge {{
  display: inline-flex;
  align-items: center;
  gap: var(--g1);
  padding: 3px var(--g3);
  border-radius: var(--r-pill);
  font-family: var(--f-mono);
  font-weight: var(--fw-label);
  font-size: var(--fs-2xs);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  white-space: nowrap;
}}
.badge-public {{ background: var(--shield-dim); color: var(--shield-hi); border: 1px solid var(--shield); }}
.badge-confidential {{ background: #3A2E10; color: var(--gold-hi); border: 1px solid var(--gold); }}
.badge-secret {{
  color: var(--bone);
  border: 1px solid var(--sev-crit);
  background: repeating-linear-gradient(45deg, #3A0E0F, #3A0E0F 6px, #2A0A0B 6px, #2A0A0B 12px);
}}

/* ---- Section frame ---- */
.doc-section {{ margin: var(--g8) 0; }}
.doc-section > .t-eyebrow {{ display: block; margin: 0 0 var(--g2); padding-bottom: var(--g1); border-bottom: 1px solid var(--faint); }}
/* The section eyebrow is an <h2> (a document needs a real heading outline, not one <h1> and
   24 styled spans), so its browser-default top margin has to be zeroed explicitly — the
   `.t-h*` reset above does not cover `.t-eyebrow`. */

/* ---- Tables ---- */
.doc-table-wrap {{ overflow-x: auto; margin: var(--g5) 0; }}

/* Every native figure draws its caption INSIDE the SVG (visual.py `_caption_block`) so that a
   standalone .svg export is self-describing. Inside a document the same caption is also emitted as
   a real <figcaption> — selectable, themed, at body size, and read by assistive technology — so the
   in-SVG copy is a duplicate rendered at ~4-9px after the viewBox scales down. Hide it here rather
   than removing it from the renderers, because the standalone export genuinely needs it: the
   duplication is a property of the EMBEDDING, so the embedding is where it should be resolved. */
.svgwrap svg text.figure-caption {{ display: none; }}

/* The .svgwrap blueprint grid is decorative and belongs behind docgen's own line-art figures. A
   chart-engine SVG paints no ground of its own (backgroundColor is "transparent", so it inherits
   the document), so the grid showed THROUGH the plot area — graph paper behind every bar and
   radar. Give an embedded chart its own ground. */
.svgwrap svg[data-engine="echarts"], .svgwrap svg[data-engine="mermaid"] {{ background: transparent; }}

/* A hash, a URL or a long path has no break opportunity, so it runs past the 68ch text column and
   out of its container. */
.t-body, .figcap, .t-list li, .doc-table td, .doc-table th {{ overflow-wrap: anywhere; }}

/* Block elements emitted by the Markdown renderer. `p` needs an explicit margin reset: the
   browser default is 1em top AND bottom, which stacked a full blank line between paragraphs and,
   before the renderer joined hard-wrapped lines, between every source line of one sentence. */
p {{ margin: 0; }}
.t-body + .t-body {{ margin-top: var(--g3); }}
.t-list {{ margin: var(--g3) 0; padding-left: var(--g5); line-height: var(--lh-base); }}
.t-list li {{ margin: var(--g1) 0; }}
.t-list li::marker {{ color: var(--mute); }}
.t-code {{
  font-family: var(--f-mono);
  font-size: 0.9em;
  padding: 0.1em 0.35em;
  border-radius: 3px;
  background: var(--faint);
  border: 1px solid var(--faint);
}}
.t-pre {{
  font-family: var(--f-mono);
  font-size: var(--fs-sm);
  line-height: 1.55;
  margin: var(--g4) 0;
  padding: var(--g3);
  border-radius: 6px;
  background: var(--faint);
  border: 1px solid var(--faint);
  overflow-x: auto;
  white-space: pre;
}}
.t-pre code {{ background: none; border: 0; padding: 0; font-size: inherit; }}
.t-quote {{
  margin: var(--g4) 0;
  padding: var(--g2) var(--g4);
  border-left: 3px solid var(--accent);
  color: var(--mute);
}}
.t-quote p {{ margin: 0; }}
.t-rule {{ border: 0; border-top: 1px solid var(--faint); margin: var(--g6) 0; }}
.t-link {{ color: var(--accent); text-decoration: underline; text-underline-offset: 2px; }}

/* Print. A table inside `overflow-x: auto` is CLIPPED on paper — the columns past the fold are
   simply gone from the PDF, with no scrollbar and no indication anything is missing. On print,
   let the wrapper overflow visibly and allow the table to shrink to the page instead. */
@media print {{
  .doc-table-wrap {{ overflow-x: visible; }}
  .doc-table-wrap table {{ width: 100%; table-layout: auto; font-size: 9pt; }}
  .doc-table-wrap td, .doc-table-wrap th {{ word-break: break-word; overflow-wrap: anywhere; }}
  .t-pre {{ white-space: pre-wrap; overflow-x: visible; }}
  figure, table, .t-pre, blockquote {{ break-inside: avoid; }}
  .t-h2, .t-h3 {{ break-after: avoid; }}
}}
table.doc-table {{ width: 100%; border-collapse: collapse; font-size: var(--fs-sm); }}
table.doc-table thead th {{
  background: var(--paper-2);
  color: var(--fg);
  text-align: left;
  font-family: var(--f-mono);
  font-weight: var(--fw-label);
  font-size: var(--fs-2xs);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: var(--g2) var(--g3);
  border-bottom: 1px solid var(--faint);
  white-space: nowrap;
}}
table.doc-table td {{
  padding: var(--g2) var(--g3);
  border-bottom: 1px solid var(--faint);
  font-variant-numeric: tabular-nums;
  vertical-align: top;
}}
table.doc-table tbody tr:nth-child(even) {{ background: color-mix(in srgb, var(--paper-2) 40%, transparent); }}

/* ---- Figure canvas ---- */
/* A figure takes the whole content width; the text around it keeps its 68ch measure. A 900px diagram squeezed into the
   text column was shown at two-thirds scale, which made its numbered circles and labels too small to read. `main` is the
   size container so `100cqw` is exactly the content box (no scrollbar-width overflow, which `100vw` would cause). Where
   container units are unsupported the figure simply stays in the text column. */
main {{ container-type: inline-size; }}
figure.doc-figure {{ margin: var(--g6) 0; scroll-margin-top: var(--g8); width: 100cqw; max-width: none; }}
.figure-insight-block, .fig-howto {{ max-width: 90ch; }}
/* The canvas is a plain framed surface, centred. It used to carry a decorative blueprint grid and a fixed box with the
   figure pinned to its left edge: a narrow map left a strip of empty graph paper on the right, and the grid showed
   through every chart's plot area. A figure that wants the grid back opts in with `.svgwrap--grid`. */
.svgwrap {{
  display: flex;
  justify-content: center;
  align-items: flex-start;
  background-color: var(--paper);
  border: 1px solid var(--faint);
  border-radius: var(--r-md);
  padding: var(--g4);
  overflow-x: auto;
}}
.svgwrap--grid {{
  background-image:
    linear-gradient(var(--grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
  background-size: var(--diagram-grid) var(--diagram-grid);
  background-position: center top;
}}
.svgwrap svg {{ display: block; max-width: 100%; height: auto; margin: 0 auto; }}
/* THE SIZE STANDARD. A picture that has told the document its design size (--fw x --fh) is shown at the SMALLEST of:
   the column (100%), the figure ceiling (FS-5), its own design size times its enlargement ceiling (FS-1: --up is 1 for an
   engine chart, 1.3 for a diagram drawn on an abstract canvas), and the width at which its height fits one screen (FS-2) -
   but that last term never drops below --fig-min-scale of the design size (FS-3: the page scrolls rather than the text
   shrinking past reading). Without this a bare-viewBox diagram took the column width: 960x740 became 1150x886. */
.svgwrap--sized svg {{
  width: min(100%, var(--fig-max-w), calc(var(--fw) * var(--up, 1) * 1px),
    max(calc(var(--fig-fit-h) * var(--fw) / var(--fh)), calc(var(--fw) * var(--fig-min-scale) * 1px)));
}}
/* FS-4: a tall or square figure is read by scrolling, so only the screen-fit term is dropped. */
.svgwrap--sized.svgwrap--tall svg {{
  width: min(100%, var(--fig-max-w), calc(var(--fw) * var(--up, 1) * 1px));
}}
figcaption.figcap {{ margin-top: var(--g3); font-size: var(--fs-sm); color: var(--ash); }}
.fig-num {{ font-family: var(--f-mono); font-weight: 600; color: var(--shield-hi); text-decoration: none; margin-right: var(--g1); }}
.fig-num:hover {{ text-decoration: underline; }}
.fig-up {{ margin-left: var(--g2); font-size: var(--fs-xs); color: var(--mute); text-decoration: none; white-space: nowrap; }}
.fig-up:hover {{ color: var(--fg); }}
/* Section -> figure links: the heading points at its pictures, the picture points back at its heading. */
.sec-figs {{ display: flex; flex-wrap: wrap; gap: var(--g2); margin: var(--g2) 0 var(--g3); }}
.fig-chip {{
  display: inline-flex; align-items: center; gap: var(--g1); padding: 3px 11px;
  border: 1px solid var(--faint); border-radius: 999px; font-size: var(--fs-xs); color: var(--ash);
  text-decoration: none; background: color-mix(in srgb, var(--fg) 3%, var(--bg));
}}
.fig-chip:hover {{ border-color: var(--shield-hi); color: var(--fg); }}
.fig-chip-n {{ font-family: var(--f-mono); font-weight: 600; color: var(--shield-hi); }}
a.fig-ref {{ color: var(--shield-hi); text-decoration: none; font-family: var(--f-mono); font-size: .92em; }}
a.fig-ref:hover {{ text-decoration: underline; }}
/* Reading guide: what the picture is, and what each numbered circle in it means. */
.fig-guide {{ margin-top: var(--g3); border: 1px solid var(--faint); border-radius: var(--r-md); padding: var(--g2) var(--g3); }}
.fig-guide > summary {{ cursor: pointer; font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: .06em; color: var(--mute); }}
.fig-howto {{ margin: var(--g2) 0; font-size: var(--fs-sm); color: var(--ash); }}
.fig-key {{ list-style: none; margin: var(--g2) 0 0; padding: 0; display: grid; gap: var(--g2); }}
.fig-key li {{
  display: grid; grid-template-columns: 30px 1fr; column-gap: var(--g2); row-gap: 2px; align-items: start;
  padding: 5px 7px; border-radius: 8px; scroll-margin-top: 90px;
}}
.fig-key li:target {{ background: color-mix(in srgb, var(--shield-hi) 16%, transparent); outline: 1px solid var(--shield-hi); }}
.fig-key-n {{
  grid-row: 1 / span 2; width: 26px; height: 26px; border-radius: 50%; display: inline-flex; align-items: center;
  justify-content: center; font-family: var(--f-mono); font-size: 12px; font-weight: 700; color: var(--fg);
  border: 1.5px solid var(--shield-hi); background: color-mix(in srgb, var(--shield-hi) 14%, transparent);
}}
.fig-marks {{ width: 100%; border-collapse: collapse; margin-top: var(--g2); font-size: var(--fs-sm); }}
.fig-marks th, .fig-marks td {{ text-align: left; padding: 5px 8px; border-top: 1px solid var(--faint); vertical-align: top; }}
.fig-marks thead th {{ font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: .05em; color: var(--mute); border-top: 0; }}
.fig-marks tbody th {{ font-weight: 600; white-space: nowrap; }}
.fig-marks td:nth-child(2) {{ font-family: var(--f-mono); white-space: nowrap; }}
/* A long unbreakable name must not push the page sideways on a phone: below 640 px the two columns that never wrap may. */
@media (max-width: 640px) {{ .fig-marks tbody th, .fig-marks td:nth-child(2) {{ white-space: normal; overflow-wrap: anywhere; }} }}
.fig-key-t {{ font-weight: 600; font-size: var(--fs-sm); }}
.fig-key-d {{ grid-column: 2; color: var(--ash); font-size: var(--fs-sm); }}
.figure-legend {{ display: flex; flex-wrap: wrap; gap: var(--g3); margin-top: var(--g2); }}
.figure-legend-item {{ display: flex; align-items: center; gap: var(--g1); font-size: var(--fs-xs); color: var(--ash); }}
/* Interpretive layer (see INTERPRETATION.md): what question the figure answers + the plain-
   language conclusion it makes obvious. Distinct from the caption (what it IS) on purpose. */
.figure-insight-block {{ margin-top: var(--g3); padding: var(--g2) var(--g3); border-left: 2px solid var(--shield-hi, var(--fg)); background: color-mix(in srgb, var(--fg) 4%, var(--bg)); }}
.figure-reader-question {{ font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: .04em; color: var(--mute); margin-bottom: var(--g1); }}
.figure-insight {{ font-size: var(--fs-sm); color: var(--fg); }}
/* Reference cards (assets/figure_runtime.js): every number that points somewhere says what it is. */
.sec-n, a.fig-ref, a.fig-num, a.fig-up, a.fig-chip {{ cursor: help; }}
.sec-n {{ font-family: var(--f-mono); border-bottom: 1px dotted var(--mute); outline-offset: 3px; }}
.sec-n:hover, .sec-n:focus-visible {{ color: var(--shield-hi); border-bottom-color: var(--shield-hi); }}
.ve-card {{
  position: fixed; z-index: 2147483001; width: min(380px, calc(100vw - 16px)); max-height: min(70vh, 460px); overflow: auto;
  padding: 12px 14px; border-radius: 10px; background: var(--paper-2, #141420); color: var(--fg); border: 1px solid var(--faint);
  box-shadow: 0 10px 34px rgba(0, 0, 0, .38); font-size: 12.5px; line-height: 1.5; text-align: left;
}}
.ve-card[hidden] {{ display: none; }}
.ve-card-kicker {{ font-family: var(--f-mono); font-size: 11px; letter-spacing: .04em; text-transform: uppercase; color: var(--shield-hi); }}
.ve-card-title {{ margin: 2px 0 6px; font-family: var(--f-display); font-size: 15px; line-height: 1.3; font-weight: 600; }}
.ve-card-text {{ margin: 6px 0; color: var(--ash); }}
.ve-card-label {{ margin: 10px 0 3px; font-size: 10.5px; letter-spacing: .06em; text-transform: uppercase; color: var(--mute); }}
.ve-card-link {{ display: block; color: var(--fg); text-decoration: none; padding: 2px 0; }}
.ve-card-link:hover {{ color: var(--shield-hi); text-decoration: underline; }}
.ve-card-doclist {{ list-style: none; margin: 0; padding: 0; }}
.ve-card-doc {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 8px; padding: 2px 0; }}
.ve-card-path {{ font-family: var(--f-mono); font-size: 11.5px; word-break: break-all; cursor: copy; }}
.ve-card-path[data-copied] {{ color: var(--verify); }}
.ve-card-kind {{ font-size: 10.5px; color: var(--mute); }}
@media (prefers-reduced-motion: no-preference) {{ .ve-card {{ animation: ve-card-in .12s ease-out; }} }}
@keyframes ve-card-in {{ from {{ opacity: 0; transform: translateY(3px); }} to {{ opacity: 1; transform: none; }} }}
@media print {{ .ve-card {{ display: none; }} }}
/* Figure runtime tooltip (assets/figure_runtime.js). One element per document, text only. */
.ve-tip {{
  position: fixed; z-index: 2147483000; max-width: 340px; padding: 8px 11px; border-radius: 8px;
  background: var(--paper-2, #141420); color: var(--fg); border: 1px solid var(--faint);
  box-shadow: 0 8px 28px rgba(0, 0, 0, .35); font-size: 12px; line-height: 1.45; pointer-events: none; white-space: pre-line;
}}
.ve-tip strong {{ display: block; margin-bottom: 2px; font-size: 13px; }}
.ve-tip-hint {{ margin-top: 6px; color: var(--mute); font-size: 11px; }}

/* ---- Module explorer (kind "explorer", tools/docgen/explorer.py + assets/explorer_runtime.js) ----
   A zoomable map: a stage of rectangles (area = size), a panel, a reader. The stage is 1000 x 620 (explorer.WORLD_W/H) so the
   aspect ratio below must match. Without script only the plain outline (.ve-ex-fallback) is shown; with script (data-ve-js) only
   the map. Hover law: tiles change outline / brightness / thickness only; the two arrow colours (--ve-out / --ve-in) are the
   declared exception it shares with the graph kind. */
.ve-ex {{
  --tone: var(--ash); --ex-mix: 52%; --ve-out: #4CC9F0; --ve-in: #F58AC0;
  position: relative; width: 100%; max-width: var(--fig-max-w); margin: 0 auto; background: var(--paper);
  border: 1px solid var(--faint); border-radius: var(--r-md); overflow: hidden;
}}
[data-theme="light"] .ve-ex {{ --ve-out: #0A7AA1; --ve-in: #B8337D; --ex-mix: 46%; }}
.ve-ex .tone-blue {{ --tone: var(--shield-hi); }}
.ve-ex .tone-gold {{ --tone: var(--gold-hi); }}
.ve-ex .tone-green {{ --tone: var(--verify); }}
.ve-ex .tone-red {{ --tone: var(--ember-hi); }}
.ve-ex .tone-bronze {{ --tone: var(--bronze-hi); }}
.ve-ex .tone-steel {{ --tone: var(--ash); }}
.ve-ex-bar {{ display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 16px; padding: 10px 14px; border-bottom: 1px solid var(--faint); }}
.ve-ex-crumbs ol {{ display: flex; flex-wrap: wrap; align-items: center; gap: 2px 0; margin: 0; padding: 0; list-style: none; }}
.ve-ex-crumbs li + li::before {{ content: "\\203A"; margin: 0 7px; color: var(--mute); }}
.ve-ex-crumb {{ appearance: none; background: none; border: 0; padding: 2px 4px; border-radius: 4px; color: var(--ash); font: inherit; font-size: var(--fs-sm); cursor: pointer; }}
.ve-ex-crumb:hover {{ color: var(--fg); text-decoration: underline; }}
.ve-ex-crumb[aria-current] {{ color: var(--fg); font-weight: 600; cursor: default; text-decoration: none; }}
.ve-ex-tools {{ display: flex; gap: 8px; }}
.ve-ex-btn {{ appearance: none; background: var(--paper-2); color: var(--fg); border: 1px solid var(--faint); border-radius: 6px; padding: 5px 11px; font: inherit; font-size: var(--fs-xs); cursor: pointer; }}
.ve-ex-btn:hover:not(:disabled) {{ border-color: var(--shield-hi); }}
.ve-ex-btn:disabled {{ opacity: .4; cursor: default; }}
.ve-ex button:focus-visible, .ve-ex a:focus-visible, .ve-ex-panel:focus-visible {{ outline: 2px solid var(--shield-hi); outline-offset: 2px; }}
.ve-ex-main {{ position: relative; display: grid; grid-template-columns: minmax(0, 1fr) minmax(250px, 330px); align-items: start; }}
.ve-ex-stagewrap {{ padding: 12px; min-width: 0; }}
.ve-ex-stage {{ position: relative; width: 100%; aspect-ratio: 1000 / 620; border-radius: 6px; overflow: hidden; background: color-mix(in srgb, var(--fg) 4%, var(--paper)); outline: none; }}
.svgwrap--block {{ display: block; padding: 0; border: 0; background: transparent; overflow: visible; }}
/* `.svgwrap svg` (height: auto, max-width: 100%) would out-rank a bare class: the camera changes the world's viewBox aspect, and
   height: auto would then change the svg's own box with it. The two layers must fill the stage exactly, always. */
.ve-ex .ve-ex-world, .ve-ex .ve-ex-links {{ position: absolute; inset: 0; width: 100%; height: 100%; max-width: none; margin: 0; display: block; }}
.ve-ex-links {{ pointer-events: none; }}
.ve-n {{ fill: color-mix(in srgb, var(--tone) var(--ex-mix), var(--paper)); stroke: var(--paper); stroke-width: 1.5px; vector-effect: non-scaling-stroke; cursor: pointer; outline: none; }}
.ve-n.ve-off {{ display: none; }}
.ve-n:hover, .ve-n.ve-hot {{ stroke: var(--fg); stroke-width: 2.5px; filter: brightness(1.14); }}
.ve-n.ve-sel {{ stroke: var(--fg); stroke-width: 3px; }}
.ve-n:focus-visible {{ stroke: var(--shield-hi); stroke-width: 3.5px; }}
.ve-moving .ve-n {{ pointer-events: none; }}
.ve-ex-labels {{ position: absolute; inset: 0; pointer-events: none; overflow: hidden; }}
.ve-ex-label {{ position: absolute; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; padding: 6px 8px; text-align: center; overflow: hidden; color: var(--fg); line-height: 1.15; }}
.ve-ex-label-n {{ font-family: var(--f-display); font-weight: 700; overflow: hidden; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; line-clamp: 3; overflow-wrap: normal; word-break: normal; hyphens: none; max-width: 100%; }}
.ve-ex-label-v, .ve-ex-label-c {{ font-size: .72em; font-weight: 500; opacity: .82; white-space: nowrap; }}
.ve-ex-label.ve-big {{ gap: 4px; }}
.ve-ex-arrow {{ fill: none; stroke-linecap: round; opacity: .92; }}
.ve-ex-arrow.ve-ex-out, .ve-ex-head.ve-ex-out {{ stroke: var(--ve-out); }}
.ve-ex-arrow.ve-ex-in, .ve-ex-head.ve-ex-in {{ stroke: var(--ve-in); }}
.ve-ex-head.ve-ex-out {{ fill: var(--ve-out); }}
.ve-ex-head.ve-ex-in {{ fill: var(--ve-in); }}
.ve-ex-legend, .ve-ex-kinds, .ve-ex-arrows {{ display: flex; flex-wrap: wrap; gap: 6px 16px; margin: 10px 0 0; padding: 0; list-style: none; font-size: var(--fs-xs); color: var(--ash); }}
.ve-ex-key {{ display: inline-flex; align-items: baseline; gap: 6px; }}
.ve-ex-swatch {{ align-self: center; width: 12px; height: 12px; border-radius: 3px; background: color-mix(in srgb, var(--tone) var(--ex-mix), var(--paper)); border: 1px solid color-mix(in srgb, var(--tone) 70%, transparent); }}
.ve-ex-key-l, .ve-ex-kind-l, .ve-ex-ak-l {{ color: var(--fg); font-weight: 600; }}
.ve-ex-kind, .ve-ex-ak {{ display: inline-flex; align-items: baseline; gap: 6px; }}
.ve-ex-kind::before {{ content: ""; align-self: center; width: 3px; height: 13px; border-radius: 2px; background: var(--tone); }}
.ve-ex-ak-line {{ align-self: center; position: relative; width: 22px; height: 0; border-top: 2px solid var(--ak); }}
.ve-ex-ak-line::after {{ content: ""; position: absolute; right: -1px; top: -5px; border-left: 7px solid var(--ak); border-top: 4px solid transparent; border-bottom: 4px solid transparent; }}
.ve-ex-ak-out {{ --ak: var(--ve-out); }}
.ve-ex-ak-in {{ --ak: var(--ve-in); }}
.ve-ex-key-d {{ color: var(--mute); }}
.ve-ex-status {{ min-height: 1.5em; margin: 8px 0 0; font-size: var(--fs-xs); color: var(--mute); }}
.ve-ex-panel {{ padding: 14px 16px 16px; border-left: 1px solid var(--faint); max-height: 640px; overflow: auto; min-width: 0; }}
.ve-ex-kicker {{ margin: 0; font-family: var(--f-mono); font-size: 11px; letter-spacing: .05em; text-transform: uppercase; color: var(--shield-hi); }}
.ve-ex-title {{ margin: 2px 0 6px; font-family: var(--f-display); font-size: 19px; line-height: 1.25; }}
.ve-ex-meta {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; margin: 0 0 8px; font-size: var(--fs-xs); color: var(--ash); }}
.ve-ex-pill {{ display: inline-block; padding: 2px 9px; border-radius: 999px; font-weight: 600; color: var(--fg); background: color-mix(in srgb, var(--tone) 26%, var(--paper)); border: 1px solid color-mix(in srgb, var(--tone) 65%, transparent); }}
.ve-ex-text {{ margin: 6px 0; color: var(--ash); font-size: var(--fs-sm); line-height: 1.5; }}
.ve-ex-sec {{ margin-top: 14px; }}
.ve-ex-label-h {{ margin-bottom: 5px; font-size: 10.5px; letter-spacing: .07em; text-transform: uppercase; color: var(--mute); }}
.ve-ex-chips {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.ve-ex-chip {{ appearance: none; display: inline-flex; align-items: baseline; gap: 6px; padding: 3px 10px 3px 8px; border-radius: 6px; border: 1px solid var(--faint); border-left: 3px solid var(--tone); background: var(--paper-2); color: var(--fg); font: inherit; font-size: 12.5px; cursor: pointer; text-align: left; }}
.ve-ex-chip:hover {{ border-color: var(--shield-hi); border-left-color: var(--tone); }}
.ve-ex-chip-w {{ color: var(--mute); font-size: 11px; white-space: nowrap; }}
.ve-ex-facts, .ve-ex-doc dl {{ display: grid; grid-template-columns: max-content 1fr; gap: 3px 12px; margin: 12px 0 0; font-size: var(--fs-xs); }}
.ve-ex-facts dt, .ve-ex-doc dt {{ color: var(--mute); }}
.ve-ex-facts dd, .ve-ex-doc dd {{ margin: 0; color: var(--fg); overflow-wrap: anywhere; }}
.ve-ex-list {{ margin: 0; padding-left: 1.1em; font-size: var(--fs-xs); color: var(--ash); }}
.ve-ex-list li {{ margin: 2px 0; }}
.ve-ex-doc-btn {{ appearance: none; display: block; width: 100%; margin-bottom: 5px; padding: 6px 10px; border-radius: 6px; border: 1px solid var(--faint); background: var(--paper-2); color: var(--fg); font: inherit; font-size: 12.5px; text-align: left; cursor: pointer; }}
.ve-ex-doc-btn::before {{ content: "\\2630\\00a0\\00a0"; color: var(--shield-hi); }}
.ve-ex-doc-btn:hover {{ border-color: var(--shield-hi); }}
.ve-ex-ref {{ display: block; padding: 2px 0; color: var(--shield-hi); font-size: var(--fs-xs); text-decoration: none; }}
.ve-ex-ref:hover {{ text-decoration: underline; }}
.ve-ex-reader {{ position: absolute; inset: 0; z-index: 4; overflow: auto; padding: 16px 22px 22px; background: var(--paper); }}
.ve-ex-reader[hidden] {{ display: none; }}
.ve-ex-reader-body {{ max-width: 78ch; margin-top: 14px; font-size: var(--fs-sm); line-height: 1.6; color: var(--fg); }}
.ve-ex-doc-title {{ margin: 0 0 10px; font-family: var(--f-display); font-size: 22px; line-height: 1.25; outline: none; }}
.ve-ex-h {{ margin: 18px 0 6px; font-size: 11.5px; letter-spacing: .07em; text-transform: uppercase; color: var(--shield-hi); }}
.ve-ex-doc p, .ve-ex-doc ul {{ margin: 6px 0; }}
.ve-ex-doc-src {{ color: var(--mute); font-size: var(--fs-xs); }}
.ve-ex-doc pre {{ overflow: auto; padding: 10px 12px; border-radius: 6px; background: var(--paper-2); border: 1px solid var(--faint); font-size: 12px; }}
.ve-ex-tablewrap {{ overflow-x: auto; margin: 8px 0; }}
.ve-ex-table {{ border-collapse: collapse; width: 100%; font-size: var(--fs-xs); }}
.ve-ex-table th {{ text-align: left; color: var(--mute); font-weight: 600; }}
.ve-ex-table th, .ve-ex-table td {{ padding: 5px 10px 5px 0; border-bottom: 1px solid var(--faint); vertical-align: top; }}
.ve-ex-fallback {{ padding: 14px 18px; font-size: var(--fs-sm); }}
.ve-ex-fallback details {{ margin: 2px 0 2px 14px; }}
.ve-ex-fallback summary {{ cursor: pointer; padding: 2px 0; }}
.ve-ex-fb-name {{ font-weight: 600; }}
.ve-ex-fb-val, .ve-ex-fb-status, .ve-ex-fb-kicker {{ color: var(--mute); font-size: var(--fs-xs); }}
.ve-ex-fb-kicker {{ margin: 2px 0; text-transform: uppercase; letter-spacing: .05em; }}
.ve-ex:not([data-ve-js]) .ve-ex-bar, .ve-ex:not([data-ve-js]) .ve-ex-main {{ display: none; }}
.ve-ex[data-ve-js] .ve-ex-fallback {{ display: none; }}
@media (max-width: 860px) {{
  .ve-ex-main {{ grid-template-columns: minmax(0, 1fr); }}
  .ve-ex-panel {{ border-left: 0; border-top: 1px solid var(--faint); max-height: none; }}
  .ve-ex-label-v, .ve-ex-label-c {{ display: none; }}
}}
@media print {{
  .ve-ex .ve-ex-bar, .ve-ex .ve-ex-main {{ display: none !important; }}
  .ve-ex .ve-ex-fallback {{ display: block !important; }}
  .ve-ex-fallback details::details-content {{ content-visibility: visible; display: block; }}
}}

/* ---- Callouts ---- */
.callout {{
  border-left: 3px solid var(--accent);
  background: var(--paper-2);
  border-radius: 0 var(--r-sm) var(--r-sm) 0;
  padding: var(--g4);
  margin: var(--g5) 0;
}}
.callout-info {{ border-left-color: var(--sev-info); }}
.callout-warn {{ border-left-color: var(--sev-med); }}
.callout-crit {{ border-left-color: var(--sev-crit); }}

/* ---- Verified stamp (trust footer) ---- */
.verified-stamp {{
  display: flex;
  align-items: center;
  gap: var(--g3);
  padding: var(--g5);
  margin-top: var(--g8);
  border-top: 1px solid var(--faint);
}}
.verified-stamp-mark {{ width: 32px; height: 32px; color: var(--verify); flex: none; }}
.verified-stamp-text {{ display: flex; flex-direction: column; gap: 2px; }}

/* ---- Theme toggle ---- */
.theme-toggle {{
  appearance: none;
  border: 1px solid var(--faint);
  background: var(--paper-2);
  color: var(--fg);
  border-radius: var(--r-pill);
  padding: 4px var(--g3);
  font-family: var(--f-mono);
  font-size: var(--fs-2xs);
  cursor: pointer;
}}

/* ---- Focus + motion guards (DESIGN_SYSTEM §7) ---- */
:focus-visible {{
  outline: 2px solid var(--shield-hi);
  outline-offset: 2px;
}}

@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
    scroll-behavior: auto !important;
  }}
}}

@media (max-width: 768px) {{
  .masthead {{ flex-direction: column; align-items: flex-start; }}
}}
"""
