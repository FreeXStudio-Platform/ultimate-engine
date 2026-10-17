"""The document index: what every number in a rendered document IS, written once, read by the page and by machines.

A document prints numbers that point somewhere: ``Fig. 17``, the ``8`` in front of a heading, the back-link ``↑ 8 · Modules``.
Until now each was a bare number: a reader could not tell what section 16 was, or which documents it drew on, without
scrolling to find out. The index closes that. ``build`` collects, from what the render already learned (sections and
figures), a small JSON document; the page embeds it as ``<script type="application/json" id="ve-doc-index">`` and the
figure runtime shows a card when a reference is hovered or focused. The same facts are in the blueprint JSON for machines;
this is the slice a BROWSER needs.

Stdlib only; deterministic (document order, no clock, no randomness); ``mypy --strict`` clean.
"""

from __future__ import annotations

import json
import re
from typing import Any, Final

_LEDE_MAX: Final = 240
_DOCS_MAX: Final = 12
_FIG_REF_RE: Final = re.compile(r"\[\[fig:[^\]]+\]\]")
_PATH_RE: Final = re.compile(
    r"`([A-Za-z0-9_./-]+\.(?:md|json|py|ya?ml|sh|mjs|cjs|js|ts|tsx|html|toml|txt|sql|csv|tsv))(?::\d+(?:-\d+)?)?`"
)
# An ordinal is a number the author set off with a dot or a bracket ("8. Modules", "2.1) Sub") or a middle dot ("8 · Modules").
# A bare leading number is NOT one: "10 findings remain" is a sentence, and "2026-10-10 notes" a date.
_ORDINAL_RE: Final = re.compile(r"^(\d+(?:\.\d+)*)(?:[.)]\s+|\s+\u00b7\s+)")


def split_ordinal(title: str) -> tuple[str, str]:
    """``"8. Modules"`` -> ``("8", "Modules")``; a title with no leading ordinal -> ``("", title)``."""
    match = _ORDINAL_RE.match(title.strip())
    return (match.group(1), title.strip()[match.end() :]) if match else ("", title.strip())


def _plain(text: str) -> str:
    """Markdown to the plain words a card prints: code spans, emphasis and figure markers dropped, links reduced to labels."""
    t = _FIG_REF_RE.sub("the figure", text)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = t.replace("`", "").replace("**", "").replace("__", "")
    t = re.sub(r"(?<![\w*])\*(?!\s)([^*]+?)(?<!\s)\*(?![\w*])", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


def lede(markdown: str) -> str:
    """The first sentence of the first paragraph of a section: what a reader needs to decide whether to go there."""
    in_fence = False
    paragraph: list[str] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        blocked = (not line) or line.startswith(("#", "|", ">", "<!--", "- ", "* ", "+ ")) or bool(re.match(r"^\d+[.)]\s", line))
        if blocked:
            if paragraph:
                break
            continue
        paragraph.append(line)
    text = _plain(" ".join(paragraph))
    if not text:
        return ""
    # first sentence, unless that is a stub ("Overview.")
    first = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text, maxsplit=1)[0]
    chosen = first if len(first) >= 30 else text
    return chosen if len(chosen) <= _LEDE_MAX else chosen[: _LEDE_MAX - 1].rstrip() + "\u2026"


def documents_in(markdown: str) -> list[str]:
    """File paths a section names in code spans (``docs/x.md``), in order of first mention, without duplicates."""
    seen: list[str] = []
    for match in _PATH_RE.finditer(markdown):
        ref = match.group(1)
        if ref not in seen:
            seen.append(ref)
    return seen


def _doc_entries(refs: list[tuple[str, str, str]]) -> list[dict[str, str]]:
    """``(ref, kind, url)`` triples -> index entries, unique by ref, capped."""
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for ref, kind, url in refs:
        if not ref or ref in seen:
            continue
        seen.add(ref)
        entry = {"ref": ref, "kind": kind}
        if url:
            entry["url"] = url
        out.append(entry)
        if len(out) >= _DOCS_MAX:
            break
    return out


def build(sections: list[dict[str, Any]], figures: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The index for a document, or ``None`` when there is nothing to point at (a document with no figures is unchanged)."""
    if not figures:
        return None
    fig_docs: dict[str, list[tuple[str, str, str]]] = {}
    out_figs: dict[str, Any] = {}
    for fig in figures:
        sources = [(str(s.get("ref", "")), str(s.get("kind", "")), str(s.get("url", ""))) for s in fig.get("data_sources", [])]
        fig_docs[str(fig["dom_id"])] = sources
        title = _plain(str(fig.get("caption", "")))
        first = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", title, maxsplit=1)[0]
        out_figs[str(fig["dom_id"])] = {
            "n": int(fig["number"]),
            "kind": str(fig.get("kind", "")),
            "title": first if len(first) <= 160 else first[:159].rstrip() + "\u2026",
            "section": str(fig.get("section", "")),
            "question": str(fig.get("reader_question", "")),
            "docs": _doc_entries(sources),
        }
    out_secs: dict[str, Any] = {}
    for sec in sections:
        sid = str(sec["id"])
        number, title = split_ordinal(str(sec.get("title", "")))
        figure_ids = [str(f) for f in sec.get("figures", [])]
        refs: list[tuple[str, str, str]] = []
        for fid in figure_ids:
            refs.extend(fig_docs.get(fid, []))
        refs.extend((path, "mentioned", "") for path in documents_in(str(sec.get("markdown", ""))))
        out_secs[sid] = {
            "n": number,
            "title": _plain(title),
            "lede": lede(str(sec.get("markdown", ""))),
            "figures": figure_ids,
            "docs": _doc_entries(refs),
        }
    return {"v": 1, "sections": out_secs, "figures": out_figs}


def to_script_json(index: dict[str, Any]) -> str:
    """The index as the body of a ``<script type="application/json">``: no ``</script>`` can end it early."""
    raw = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
