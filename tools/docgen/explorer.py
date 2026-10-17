"""The module explorer: a zoomable, clickable map of a hierarchy, with a panel and a reader for what is inside it.

A static diagram answers one question at one distance. A system has many: what are its parts, how big is each, what does this
one call and who calls it, what is inside it, which documents describe it. The explorer holds ONE hierarchy (system, modules,
packages, submodules) and lets a reader move through it: start zoomed out, click a part and the camera glides into it, show
what is inside, zoom out, go into another. The panel beside the map says what the focused part is, how big, what it connects
to (chips that navigate there) and which documents describe it (a reader opens them in place). Numbers are the same numbers
in every view: a tile's area is its size, and a part's size is the sum of its children's.

This module owns the SPEC (validated, closed vocabularies, bounded sizes), the deterministic LAYOUT (squarified treemap, one
normalised stage per parent, so zooming into any part fills the stage with that part's children in good proportions), the
CONNECTIONS (exact edges, reversed for "called by", siblings for the arrows) and the HTML: the markup the runtime
(``assets/explorer_runtime.js``) takes over, a complete static outline of the same content for a browser without script, a
printer and a machine, and the record the blueprint JSON carries.

Law (same as the figure runtime): the runtime reads this module's JSON and builds DOM with ``createElement`` and
``textContent``; the documents' HTML is rendered HERE, at build time, with every string escaped. Nothing is evaluated.

Stdlib only; ``mypy --strict`` clean; deterministic (no clock, no randomness; coordinates rounded to 3 dp).
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from html import escape
from typing import Any, Final

from tools.docgen.assets.glyphs import TONES, validate_tone
from tools.docgen.doc_index import to_script_json
from tools.docgen.figure_support import KeyItem, fig_dom_id

WORLD_W: Final = 1000.0  # every parent is laid out on a stage this size ...
WORLD_H: Final = 620.0  # ... and mapped into its own rectangle, so a zoom into any part fills the stage
INSET: Final = 5.0  # space between a parent's edge and its children, in stage units
GAP: Final = 2.5  # space between siblings
FLOOR_SHARE: Final = 0.012  # a part smaller than this share of its siblings is drawn at this share (it must stay clickable)

MAX_NODES: Final = 700
MAX_DEPTH: Final = 5
MAX_EDGES: Final = 3000
MAX_CHILDREN: Final = 60
MAX_TEXT: Final = 600
MAX_NAME: Final = 90
MAX_LIST_ITEMS: Final = 60
MAX_FACTS: Final = 40
MAX_DOCS: Final = 400
MAX_BLOCKS: Final = 80
BLOCK_TYPES: Final = ("h", "p", "ul", "kv", "table", "code")
_ID_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
_KEY_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")


class ExplorerError(ValueError):
    """A spec the explorer refuses, naming what is wrong and where."""


@dataclass(frozen=True)
class ExplorerRef:
    """An in-page link from a part to somewhere else in the document (``#sec-...`` / ``#fig-...``)."""

    label: str
    href: str


@dataclass(frozen=True)
class ExplorerBlock:
    """One block of a document: a heading, a paragraph, a list, key/value rows, a table or a code sample."""

    t: str
    text: str = ""
    items: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()
    head: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExplorerDoc:
    """A document a reader can open in place. ``sources`` names the files it was written from (paths, copyable)."""

    id: str
    title: str
    blocks: tuple[ExplorerBlock, ...]
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExplorerList:
    title: str
    items: tuple[str, ...]


@dataclass(frozen=True)
class ExplorerNode:
    """One part of the hierarchy. ``value`` is its own size when it is a leaf; a part with children is the sum of theirs."""

    id: str
    name: str
    kicker: str = ""
    value: float | None = None
    status: str = ""
    summary: str = ""
    facts: tuple[tuple[str, str], ...] = ()
    lists: tuple[ExplorerList, ...] = ()
    docs: tuple[str, ...] = ()
    refs: tuple[ExplorerRef, ...] = ()
    children: tuple[ExplorerNode, ...] = ()


@dataclass(frozen=True)
class ExplorerEdge:
    """A connection between two parts: ``src`` calls / depends on / feeds ``dst``. Exact: no roll-up between levels."""

    src: str
    dst: str
    weight: float = 1.0
    kind: str = ""


@dataclass(frozen=True)
class ExplorerStatus:
    """A state a part can be in (clean, leaky, ...): its label, its colour family (``tone``) and what it means."""

    key: str
    label: str
    tone: str
    detail: str = ""


@dataclass(frozen=True)
class ExplorerKind:
    """A kind of connection (declared, leak, ...): its label, colour family and what it means. Listed in priority order."""

    key: str
    label: str
    tone: str = "blue"
    detail: str = ""


@dataclass(frozen=True)
class ExplorerArrows:
    """The words the hover arrows and their legend use. The defaults describe code ("calls" / "called by"); a documents explorer
    says "cites" / "cited by", a pipeline "feeds" / "fed by". ``out`` and ``into`` are the legend labels, the two details finish the
    sentence "the parts ...": one for the parts this part points at, one for the parts that point at it."""

    out: str = "calls"
    into: str = "called by"
    out_detail: str = "the parts it calls"
    into_detail: str = "the parts that call it"


@dataclass(frozen=True)
class ExplorerSpec:
    id: str
    title: str
    caption: str
    root: ExplorerNode
    edges: tuple[ExplorerEdge, ...] = ()
    documents: tuple[ExplorerDoc, ...] = ()
    statuses: tuple[ExplorerStatus, ...] = ()
    kinds: tuple[ExplorerKind, ...] = ()
    unit: str = "lines of code"
    reader_question: str = ""
    insight: str = ""
    data_sources: list[Any] = field(default_factory=list)
    arrows: ExplorerArrows = field(default_factory=ExplorerArrows)


# ---------------------------------------------------------------------------------------------------------------------
# Parsing and validation
# ---------------------------------------------------------------------------------------------------------------------


def _text(value: Any, where: str, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise ExplorerError(f"{where}: expected text, got {type(value).__name__}")
    if len(value) > limit:
        raise ExplorerError(f"{where}: {len(value)} characters; the limit is {limit}")
    return value


def _objects(value: Any, where: str, limit: int) -> list[dict[str, Any]]:
    """A list whose every entry is an object: a stray string or number is refused with its position, never dropped (a dropped edge
    would build a diagram that looks complete and is missing a connection)."""
    out = _seq(value, where, limit)
    for k, entry in enumerate(out):
        if not isinstance(entry, dict):
            raise ExplorerError(f"{where}[{k}]: expected an object, got {type(entry).__name__}")
    return out


def _ident(value: Any, where: str) -> str:
    text = _text(value, where, 64)
    if not _ID_RE.match(text):
        raise ExplorerError(f"{where}: {text!r} is not an id (letters, digits, and . _ : -; at most 64; starts alphanumeric)")
    return text


def _key(value: Any, where: str) -> str:
    text = _text(value, where, 32)
    if not _KEY_RE.match(text):
        raise ExplorerError(f"{where}: {text!r} is not a key (letters, digits, - _; at most 32)")
    return text


def _href(value: Any, where: str) -> str:
    text = _text(value, where, 200)
    if not re.match(r"^#[A-Za-z0-9][A-Za-z0-9_.:-]*$", text):
        raise ExplorerError(f"{where}: {text!r} must be an in-page link such as '#sec-modules' or '#fig-modules'")
    return text


def _tone(value: Any, where: str) -> str:
    text = _text(value, where, 16)
    try:
        tone = validate_tone(text)
    except ValueError as exc:
        raise ExplorerError(f"{where}: {exc}") from exc
    return tone


def _number(value: Any, where: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ExplorerError(f"{where}: expected a number, got {type(value).__name__}")
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        raise ExplorerError(f"{where}: {value!r} is not a finite number >= {minimum:g}")
    return number


def _seq(value: Any, where: str, limit: int) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ExplorerError(f"{where}: expected a list, got {type(value).__name__}")
    if len(value) > limit:
        raise ExplorerError(f"{where}: {len(value)} entries; the limit is {limit}")
    return value


def _block_from_dict(data: Any, where: str) -> ExplorerBlock:
    if not isinstance(data, dict):
        raise ExplorerError(f"{where}: a block is an object")
    t = _text(data.get("t"), f"{where}.t", 8)
    if t not in BLOCK_TYPES:
        raise ExplorerError(f"{where}.t: {t!r} is not one of {', '.join(BLOCK_TYPES)}")
    items = tuple(_text(i, f"{where}.items[{k}]", MAX_TEXT) for k, i in enumerate(_seq(data.get("items"), f"{where}.items", MAX_LIST_ITEMS)))
    head = tuple(_text(i, f"{where}.head[{k}]", MAX_NAME) for k, i in enumerate(_seq(data.get("head"), f"{where}.head", 12)))
    rows: list[tuple[str, ...]] = []
    for k, row in enumerate(_seq(data.get("rows"), f"{where}.rows", 200)):
        if not isinstance(row, list) or not row:
            raise ExplorerError(f"{where}.rows[{k}]: a row is a non-empty list of text cells")
        rows.append(tuple(_text(c, f"{where}.rows[{k}][{j}]", MAX_TEXT) for j, c in enumerate(row[:12])))
    text = _text(data.get("text", ""), f"{where}.text", 4000)
    return ExplorerBlock(t=t, text=text, items=items, rows=tuple(rows), head=head)


def _doc_from_dict(data: Any, index: int) -> ExplorerDoc:
    where = f"documents[{index}]"
    if not isinstance(data, dict):
        raise ExplorerError(f"{where}: a document is an object")
    blocks = tuple(_block_from_dict(b, f"{where}.blocks[{k}]") for k, b in enumerate(_seq(data.get("blocks"), f"{where}.blocks", MAX_BLOCKS)))
    sources = tuple(_text(s, f"{where}.sources[{k}]", 200) for k, s in enumerate(_seq(data.get("sources"), f"{where}.sources", 20)))
    return ExplorerDoc(id=_ident(data.get("id"), f"{where}.id"), title=_text(data.get("title"), f"{where}.title", MAX_NAME + 40), blocks=blocks, sources=sources)


def _node_from_dict(data: Any, depth: int, counter: list[int]) -> ExplorerNode:
    if not isinstance(data, dict):
        raise ExplorerError("a node is an object")
    nid = _ident(data.get("id"), "node.id")
    where = f"node {nid}"
    counter[0] += 1
    if counter[0] > MAX_NODES:
        raise ExplorerError(f"more than {MAX_NODES} nodes: the explorer holds a system's parts, not its every file")
    if depth > MAX_DEPTH:
        raise ExplorerError(f"{where}: deeper than {MAX_DEPTH} levels")
    raw_children = _seq(data.get("children"), f"{where}.children", MAX_CHILDREN)
    value = data.get("value")
    fact_rows = _seq(data.get("facts"), f"{where}.facts", MAX_FACTS)
    facts: list[tuple[str, str]] = []
    for k, f in enumerate(fact_rows):
        if not isinstance(f, list | tuple) or len(f) != 2:
            raise ExplorerError(f"{where}.facts[{k}]: a fact is a [label, value] pair")
        facts.append((_text(f[0], f"{where}.facts[{k}][0]", MAX_NAME), _text(f[1], f"{where}.facts[{k}][1]", MAX_TEXT)))
    lists = tuple(
        ExplorerList(
            title=_text(entry.get("title"), f"{where}.lists[{k}].title", MAX_NAME),
            items=tuple(_text(i, f"{where}.lists[{k}].items[{j}]", MAX_TEXT) for j, i in enumerate(_seq(entry.get("items"), f"{where}.lists[{k}].items", MAX_LIST_ITEMS))),
        )
        for k, entry in enumerate(_seq(data.get("lists"), f"{where}.lists", 12))
        if isinstance(entry, dict)
    )
    refs = tuple(
        ExplorerRef(label=_text(r.get("label"), f"{where}.refs[{k}].label", MAX_NAME + 20), href=_href(r.get("href"), f"{where}.refs[{k}].href"))
        for k, r in enumerate(_seq(data.get("refs"), f"{where}.refs", 12))
        if isinstance(r, dict)
    )
    docs = tuple(_ident(d, f"{where}.docs[{k}]") for k, d in enumerate(_seq(data.get("docs"), f"{where}.docs", 12)))
    return ExplorerNode(
        id=nid,
        name=_text(data.get("name"), f"{where}.name", MAX_NAME),
        kicker=_text(data.get("kicker", ""), f"{where}.kicker", MAX_NAME + 20),
        value=None if value is None else _number(value, f"{where}.value"),
        status=_key(data["status"], f"{where}.status") if data.get("status") else "",
        summary=_text(data.get("summary", ""), f"{where}.summary"),
        facts=tuple(facts),
        lists=lists,
        docs=docs,
        refs=refs,
        children=tuple(_node_from_dict(c, depth + 1, counter) for c in raw_children),
    )


_ARROW_KEYS: Final = {"out": "out", "in": "into", "out_detail": "out_detail", "in_detail": "into_detail"}


def _arrows_from(raw: Any) -> ExplorerArrows:
    """The optional ``arrows`` object: any of ``out``, ``in``, ``out_detail``, ``in_detail`` (short text); unknown keys are refused."""
    if raw is None:
        return ExplorerArrows()
    if not isinstance(raw, dict):
        raise ExplorerError("arrows: expected an object with keys from out, in, out_detail, in_detail")
    unknown = sorted(set(raw) - set(_ARROW_KEYS))
    if unknown:
        raise ExplorerError(f"arrows: unknown key(s) {', '.join(unknown)}; the keys are out, in, out_detail, in_detail")
    values = {_ARROW_KEYS[k]: _text(v, f"arrows.{k}", 60).strip() for k, v in raw.items()}
    if any(not v for v in values.values()):
        raise ExplorerError("arrows: a value is empty; leave the key out to keep the default wording")
    return ExplorerArrows(**values)


def spec_from_dict(data: dict[str, Any]) -> ExplorerSpec:
    """Build and validate an :class:`ExplorerSpec` from a sidecar entry (``kind: "explorer"``)."""
    from tools.docgen.models import DataSource

    counter = [0]
    root = _node_from_dict(data.get("root"), 0, counter)
    if not root.children:
        raise ExplorerError("the root has no children: an explorer needs at least one part to open")
    statuses = tuple(
        ExplorerStatus(key=_key(s.get("key"), f"statuses[{k}].key"), label=_text(s.get("label"), f"statuses[{k}].label", 40),
                       tone=_tone(s.get("tone", ""), f"statuses[{k}].tone"), detail=_text(s.get("detail", ""), f"statuses[{k}].detail", 300))
        for k, s in enumerate(_objects(data.get("statuses"), "statuses", 12))
    )
    kinds = tuple(
        ExplorerKind(key=_key(s.get("key"), f"kinds[{k}].key"), label=_text(s.get("label"), f"kinds[{k}].label", 40),
                     tone=_tone(s.get("tone", "blue"), f"kinds[{k}].tone"), detail=_text(s.get("detail", ""), f"kinds[{k}].detail", 300))
        for k, s in enumerate(_objects(data.get("kinds"), "kinds", 8))
    )
    edges = tuple(
        ExplorerEdge(src=_ident(e.get("src"), f"edges[{k}].src"), dst=_ident(e.get("dst"), f"edges[{k}].dst"),
                     weight=_number(e.get("weight", 1.0), f"edges[{k}].weight"), kind=_key(e["kind"], f"edges[{k}].kind") if e.get("kind") else "")
        for k, e in enumerate(_objects(data.get("edges"), "edges", MAX_EDGES))
    )
    docs = tuple(_doc_from_dict(d, k) for k, d in enumerate(_seq(data.get("documents"), "documents", MAX_DOCS)))
    sources = [
        DataSource(kind=str(s["kind"]), ref=str(s["ref"]), retrieved=str(s.get("retrieved", "")), url=str(s.get("url", "")))
        for s in _seq(data.get("data_sources"), "data_sources", 20)
    ]
    spec = ExplorerSpec(
        arrows=_arrows_from(data.get("arrows")),
        id=_text(data.get("id"), "id", 64), title=_text(data.get("title"), "title", 160), caption=_text(data.get("caption"), "caption", 600),
        root=root, edges=edges, documents=docs, statuses=statuses, kinds=kinds, unit=_text(data.get("unit", "lines of code"), "unit", 40),
        reader_question=_text(data.get("reader_question", ""), "reader_question", 300), insight=_text(data.get("insight", ""), "insight", 600),
        data_sources=sources,
    )
    validate(spec)
    return spec


def walk(node: ExplorerNode, depth: int = 0, parent: str = "") -> list[tuple[ExplorerNode, int, str]]:
    """Every node in document order as ``(node, depth, parent id)``."""
    out = [(node, depth, parent)]
    for child in node.children:
        out.extend(walk(child, depth + 1, node.id))
    return out


def validate(spec: ExplorerSpec) -> None:
    """Cross-reference checks the per-field parsers cannot make: unique ids, edges and documents that exist."""
    nodes = walk(spec.root)
    ids = [n.id for n, _d, _p in nodes]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ExplorerError(f"node ids must be unique; repeated: {', '.join(dup[:6])}")
    known = set(ids)
    status_keys = {s.key for s in spec.statuses}
    kind_keys = {k.key for k in spec.kinds}
    if len(status_keys) != len(spec.statuses):
        raise ExplorerError("status keys must be unique")
    if len(kind_keys) != len(spec.kinds):
        raise ExplorerError("connection kinds must be unique")
    doc_ids = [d.id for d in spec.documents]
    if len(set(doc_ids)) != len(doc_ids):
        raise ExplorerError("document ids must be unique")
    for node, _d, _p in nodes:
        if node.status and node.status not in status_keys:
            raise ExplorerError(f"node {node.id}: status {node.status!r} is not declared in `statuses` ({', '.join(sorted(status_keys)) or 'none'})")
        for doc in node.docs:
            if doc not in doc_ids:
                raise ExplorerError(f"node {node.id}: document {doc!r} is not in `documents`")
    seen_edges: set[tuple[str, str]] = set()
    for edge in spec.edges:
        for end in (edge.src, edge.dst):
            if end not in known:
                raise ExplorerError(f"edge {edge.src} -> {edge.dst}: {end!r} is not a node")
        if edge.src == edge.dst:
            raise ExplorerError(f"edge {edge.src} -> {edge.dst}: a part cannot connect to itself")
        if edge.kind and edge.kind not in kind_keys:
            raise ExplorerError(f"edge {edge.src} -> {edge.dst}: kind {edge.kind!r} is not declared in `kinds` ({', '.join(sorted(kind_keys)) or 'none'})")
        if (edge.src, edge.dst) in seen_edges:
            raise ExplorerError(f"edge {edge.src} -> {edge.dst} is listed twice: merge the weights")
        seen_edges.add((edge.src, edge.dst))
    for ident in ids:
        if not _ID_RE.match(ident):
            raise ExplorerError(f"{ident!r} is not a valid id")


# ---------------------------------------------------------------------------------------------------------------------
# Layout: a squarified treemap per parent, on a normalised stage
# ---------------------------------------------------------------------------------------------------------------------


def _worst(areas: Sequence[float], side: float) -> float:
    total = sum(areas)
    return max(side * side * max(areas) / (total * total), (total * total) / (side * side * min(areas)))


def squarify(values: Sequence[float], x: float, y: float, w: float, h: float) -> list[tuple[float, float, float, float]]:
    """Rectangles tiling ``(x, y, w, h)`` with areas proportional to ``values`` (all positive), in the order given.

    Bruls, Huizing and van Wijk's squarified treemap: rows are laid along the shorter side and a row keeps growing while it
    makes the worst aspect ratio no worse. The caller sorts descending, which is what makes the tiles near-square.
    """
    if not values:
        return []
    if any(v <= 0 or not math.isfinite(v) for v in values):
        raise ExplorerError("squarify needs positive finite values")
    total = float(sum(values))
    areas = [v / total * w * h for v in values]
    out: list[tuple[float, float, float, float]] = []
    cx, cy, cw, ch = x, y, w, h
    i = 0
    while i < len(areas):
        side = min(cw, ch)
        j = i + 1
        worst = _worst(areas[i:j], side)
        while j < len(areas) and _worst(areas[i : j + 1], side) <= worst:
            j += 1
            worst = _worst(areas[i:j], side)
        row = areas[i:j]
        row_area = sum(row)
        if cw >= ch:  # a strip down the left edge
            strip = row_area / ch
            ry = cy
            for a in row:
                hh = a / strip
                out.append((cx, ry, strip, hh))
                ry += hh
            cx += strip
            cw -= strip
        else:  # a strip along the top edge
            strip = row_area / cw
            rx = cx
            for a in row:
                ww = a / strip
                out.append((rx, cy, ww, strip))
                rx += ww
            cy += strip
            ch -= strip
        i = j
    return [(round(a, 3), round(b, 3), round(c, 3), round(d, 3)) for a, b, c, d in out]


def raw_value(node: ExplorerNode) -> float:
    """A leaf's own size, or the sum of its children's: the number a label prints."""
    if node.children:
        return float(sum(raw_value(c) for c in node.children))
    return float(node.value or 0.0)


def _weights(children: Sequence[ExplorerNode]) -> list[float]:
    raws = [raw_value(c) for c in children]
    total = sum(raws)
    if total <= 0:
        return [1.0] * len(children)
    floor = total * FLOOR_SHARE
    return [max(r, floor) for r in raws]


Rect = tuple[float, float, float, float]


def layout(spec: ExplorerSpec) -> dict[str, Rect]:
    """World rectangle of every node. The root fills the stage; each parent's children tile a stage of the same size and are
    mapped into the parent's own rectangle, so the camera that frames a parent shows its children in good proportions."""
    rects: dict[str, Rect] = {spec.root.id: (0.0, 0.0, WORLD_W, WORLD_H)}

    def place(node: ExplorerNode) -> None:
        if not node.children:
            return
        px, py, pw, ph = rects[node.id]
        weights = _weights(node.children)
        order = sorted(range(len(node.children)), key=lambda i: (-weights[i], node.children[i].id))
        tiles = squarify([weights[i] for i in order], INSET, INSET, WORLD_W - 2 * INSET, WORLD_H - 2 * INSET)
        for idx, (nx, ny, nw, nh) in zip(order, tiles, strict=True):
            nx, ny = nx + GAP / 2, ny + GAP / 2
            nw, nh = max(nw - GAP, 1.0), max(nh - GAP, 1.0)
            rects[node.children[idx].id] = (
                round(px + nx / WORLD_W * pw, 3),
                round(py + ny / WORLD_H * ph, 3),
                round(nw / WORLD_W * pw, 3),
                round(nh / WORLD_H * ph, 3),
            )
            place(node.children[idx])

    place(spec.root)
    return rects


# ---------------------------------------------------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Connections:
    """Every part's exact connections. ``out``/``into`` are ``(other id, weight, kind)``; ``sib`` is, per PARENT, the
    ``(src, dst, weight, kind)`` links between its children: what the stage draws when a child is hovered."""

    out: dict[str, list[tuple[str, float, str]]]
    into: dict[str, list[tuple[str, float, str]]]
    sib: dict[str, list[tuple[str, str, float, str]]]


def connections(spec: ExplorerSpec) -> Connections:
    parent: dict[str, str] = {n.id: p for n, _d, p in walk(spec.root)}
    out: dict[str, list[tuple[str, float, str]]] = {}
    into: dict[str, list[tuple[str, float, str]]] = {}
    sib: dict[str, list[tuple[str, str, float, str]]] = {}
    for e in spec.edges:
        out.setdefault(e.src, []).append((e.dst, e.weight, e.kind))
        into.setdefault(e.dst, []).append((e.src, e.weight, e.kind))
        if parent.get(e.src) == parent.get(e.dst) and parent.get(e.src) is not None:
            sib.setdefault(parent[e.src], []).append((e.src, e.dst, e.weight, e.kind))
    priority = {k.key: i for i, k in enumerate(spec.kinds)}
    for table in (out, into):
        for rows in table.values():
            rows.sort(key=lambda r: (priority.get(r[2], 99), -r[1], r[0]))
    for links in sib.values():
        links.sort(key=lambda r: (r[0], r[1]))
    return Connections(out=out, into=into, sib=sib)


def fmt_value(value: float, unit: str = "") -> str:
    """``30664`` -> ``30,664``; with a unit, ``30,664 lines of code``."""
    text = f"{value:,.0f}" if abs(value - round(value)) < 1e-9 else f"{value:,.2f}"
    return f"{text} {unit}".strip()


# ---------------------------------------------------------------------------------------------------------------------
# HTML: the documents, the static outline, the stage, and the page's markup
# ---------------------------------------------------------------------------------------------------------------------


def render_blocks(blocks: Sequence[ExplorerBlock]) -> str:
    """A document's blocks as HTML. Every string is escaped; there is no markdown and no inline markup."""
    parts: list[str] = []
    for b in blocks:
        if b.t == "h":
            parts.append(f'<h5 class="ve-ex-h">{escape(b.text)}</h5>')
        elif b.t == "p":
            parts.append(f"<p>{escape(b.text)}</p>")
        elif b.t == "ul":
            parts.append("<ul>" + "".join(f"<li>{escape(i)}</li>" for i in b.items) + "</ul>")
        elif b.t == "kv":
            parts.append("<dl>" + "".join(f"<dt>{escape(r[0])}</dt><dd>{escape(r[1] if len(r) > 1 else '')}</dd>" for r in b.rows) + "</dl>")
        elif b.t == "table":
            head = "".join(f"<th>{escape(h)}</th>" for h in b.head)
            body = "".join("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in r) + "</tr>" for r in b.rows)
            parts.append(f'<div class="ve-ex-tablewrap"><table class="ve-ex-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')
        elif b.t == "code":
            parts.append(f"<pre><code>{escape(b.text)}</code></pre>")
    return "".join(parts)


def render_doc(doc: ExplorerDoc, fid: str) -> str:
    sources = (
        '<p class="ve-ex-doc-src">Written from: ' + ", ".join(f"<code>{escape(s)}</code>" for s in doc.sources) + "</p>" if doc.sources else ""
    )
    return (
        f'<article class="ve-ex-doc" id="{fid}-doc-{escape(doc.id, quote=True)}" data-doc="{escape(doc.id, quote=True)}">'
        f'<h4 class="ve-ex-doc-title">{escape(doc.title)}</h4>{render_blocks(doc.blocks)}{sources}</article>'
    )


def _status_label(spec: ExplorerSpec, key: str) -> str:
    for s in spec.statuses:
        if s.key == key:
            return s.label
    return ""


def _tone_of(spec: ExplorerSpec, key: str) -> str:
    for s in spec.statuses:
        if s.key == key:
            return s.tone if s.tone != "none" else ""
    return ""


def _names(spec: ExplorerSpec) -> dict[str, ExplorerNode]:
    return {n.id: n for n, _d, _p in walk(spec.root)}


def _conn_text(spec: ExplorerSpec, rows: list[tuple[str, float, str]], names: dict[str, ExplorerNode]) -> str:
    kinds = {k.key: k.label for k in spec.kinds}
    bits = []
    for other, weight, kind in rows:
        label = names[other].name
        extra = [f"{weight:g}"] if weight != 1.0 else []
        if kind and kind in kinds:
            extra.append(kinds[kind])
        bits.append(label + (f" ({', '.join(extra)})" if extra else ""))
    return ", ".join(bits)


def render_outline(spec: ExplorerSpec, fid: str, conn: Connections) -> str:
    """The same content as plain, nested, semantic HTML: what a browser without script, a printer and a machine read."""
    names = _names(spec)
    used_docs = {d for n in names.values() for d in n.docs}

    def node_html(n: ExplorerNode, depth: int) -> str:
        total = raw_value(n)
        label = _status_label(spec, n.status)
        head = f'<span class="ve-ex-fb-name">{escape(n.name)}</span>'
        if total:
            head += f' <span class="ve-ex-fb-val">{escape(fmt_value(total, spec.unit))}</span>'
        if label:
            head += f' <span class="ve-ex-fb-status">{escape(label)}</span>'
        body: list[str] = []
        if n.kicker:
            body.append(f'<p class="ve-ex-fb-kicker">{escape(n.kicker)}</p>')
        if n.summary:
            body.append(f"<p>{escape(n.summary)}</p>")
        if n.facts:
            body.append("<dl>" + "".join(f"<dt>{escape(k)}</dt><dd>{escape(v)}</dd>" for k, v in n.facts) + "</dl>")
        for lst in n.lists:
            body.append(f"<p><strong>{escape(lst.title)}</strong></p><ul>" + "".join(f"<li>{escape(i)}</li>" for i in lst.items) + "</ul>")
        if conn.out.get(n.id):
            body.append(f"<p><strong>Connects to:</strong> {escape(_conn_text(spec, conn.out[n.id], names))}</p>")
        if conn.into.get(n.id):
            body.append(f"<p><strong>Connected from:</strong> {escape(_conn_text(spec, conn.into[n.id], names))}</p>")
        if n.refs:
            body.append("<p><strong>In this document:</strong> " + ", ".join(f'<a href="{escape(r.href, quote=True)}">{escape(r.label)}</a>' for r in n.refs) + "</p>")
        if n.docs:
            titles = {d.id: d.title for d in spec.documents}
            body.append(
                "<p><strong>Documents:</strong> "
                + ", ".join(f'<a href="#{fid}-doc-{escape(d, quote=True)}">{escape(titles[d])}</a>' for d in n.docs)
                + "</p>"
            )
        kids = "".join(node_html(c, depth + 1) for c in n.children)
        opened = " open" if depth < 1 else ""
        return f'<details class="ve-ex-fb" data-id="{escape(n.id, quote=True)}"{opened}><summary>{head}</summary>{"".join(body)}{kids}</details>'

    docs = "".join(render_doc(d, fid) for d in spec.documents if d.id in used_docs)
    return f'<div class="ve-ex-fallback">{node_html(spec.root, 0)}<div class="ve-ex-docs">{docs}</div></div>'


def _round(value: float) -> float:
    return round(value, 3)


def payload(spec: ExplorerSpec, fid: str, rects: dict[str, Rect], conn: Connections) -> dict[str, Any]:
    """The JSON the runtime reads: every part with its rectangle, text, connections and documents."""
    nodes: dict[str, Any] = {}
    for n, depth, parent in walk(spec.root):
        r = rects[n.id]
        entry: dict[str, Any] = {
            "n": n.name, "d": depth, "p": parent, "c": [c.id for c in n.children],
            "r": [_round(v) for v in r], "v": _round(raw_value(n)),
        }
        if n.kicker:
            entry["k"] = n.kicker
        if n.status:
            entry["s"] = n.status
        if n.summary:
            entry["t"] = n.summary
        if n.facts:
            entry["f"] = [[a, b] for a, b in n.facts]
        if n.lists:
            entry["l"] = [{"t": lst.title, "i": list(lst.items)} for lst in n.lists]
        if n.docs:
            entry["doc"] = list(n.docs)
        if n.refs:
            entry["ref"] = [[r_.label, r_.href] for r_ in n.refs]
        if conn.out.get(n.id):
            entry["out"] = [[o, w, k] for o, w, k in conn.out[n.id]]
        if conn.into.get(n.id):
            entry["in"] = [[o, w, k] for o, w, k in conn.into[n.id]]
        if conn.sib.get(n.id):
            entry["sib"] = [[a, b, w, k] for a, b, w, k in conn.sib[n.id]]
        nodes[n.id] = entry
    return {
        "v": 1, "id": fid, "root": spec.root.id, "w": WORLD_W, "h": WORLD_H, "unit": spec.unit, "nodes": nodes,
        "status": {s.key: {"l": s.label, "t": s.tone, "d": s.detail} for s in spec.statuses},
        "kinds": {k.key: {"l": k.label, "t": k.tone, "d": k.detail} for k in spec.kinds},
        "docs": {d.id: d.title for d in spec.documents},
    }


HOW_TO_READ: Final = (
    "Each rectangle is a part of the system and its area is its size, so a bigger rectangle is a bigger part. Click a part and the "
    "map zooms into it to show what it is made of; the panel says what it is, how big it is, what it connects to (each name is a "
    "button that takes you there) and which documents describe it (open one to read it in place). Hover a part to see its "
    "connections drawn as arrows: blue for {out_detail}, pink for {into_detail}. Press Escape, the Zoom out "
    "button or a name in the trail above the map to go back up; with the keyboard, Tab to the map, arrow keys move between "
    "parts, Enter opens one. Without script the same content is a plain outline."
)


def how_to_read(spec: ExplorerSpec | None = None) -> str:
    """The reading guide; with a spec, the arrow sentence uses that spec's own wording (default: the code wording)."""
    arrows = spec.arrows if spec is not None else ExplorerArrows()
    return HOW_TO_READ.format(out_detail=arrows.out_detail, into_detail=arrows.into_detail)


def reading_key(spec: ExplorerSpec) -> list[KeyItem]:
    """An explorer has no numbered circles: its key is empty (the statuses are its legend)."""
    return []


def marks(spec: ExplorerSpec) -> tuple[tuple[str, str, str], ...]:
    """``(mark, value, what it tells you)`` for the top-level parts: what the document prints under the figure."""
    rows = []
    for child in spec.root.children:
        status = _status_label(spec, child.status)
        detail = child.summary or child.kicker
        rows.append((child.name, fmt_value(raw_value(child), spec.unit), f"{status}. {detail}".strip(". ") if status else detail))
    return tuple(rows) if 0 < len(rows) <= 30 else ()


def record(spec: ExplorerSpec) -> dict[str, Any]:
    """The machine twin for the blueprint JSON: the whole hierarchy, its connections and its documents, no geometry."""
    conn = connections(spec)
    nodes = []
    for n, depth, parent in walk(spec.root):
        nodes.append({
            "id": n.id, "name": n.name, "depth": depth, "parent": parent, "kicker": n.kicker, "value": raw_value(n),
            "status": n.status, "summary": n.summary, "facts": [list(f) for f in n.facts],
            "lists": [{"title": lst.title, "items": list(lst.items)} for lst in n.lists],
            "documents": list(n.docs), "refs": [{"label": r.label, "href": r.href} for r in n.refs],
            "calls": [{"to": o, "weight": w, "kind": k} for o, w, k in conn.out.get(n.id, [])],
            "called_by": [{"from": o, "weight": w, "kind": k} for o, w, k in conn.into.get(n.id, [])],
        })
    return {
        "kind": "explorer", "unit": spec.unit, "statuses": [{"key": s.key, "label": s.label, "detail": s.detail} for s in spec.statuses],
        "connection_kinds": [{"key": k.key, "label": k.label, "detail": k.detail} for k in spec.kinds], "nodes": nodes,
        "documents": [{"id": d.id, "title": d.title, "sources": list(d.sources), "blocks": [{"t": b.t, "text": b.text, "items": list(b.items), "rows": [list(r) for r in b.rows], "head": list(b.head)} for b in d.blocks]} for d in spec.documents],
    }


def _tone_class(spec: ExplorerSpec, status: str) -> str:
    tone = _tone_of(spec, status)
    return f" tone-{tone}" if tone in TONES else ""


def render(spec: ExplorerSpec, *, theme: str | None = None) -> str:
    """The explorer as a block of HTML: bar, stage, panel, reader, legend, the static outline and the data the runtime reads."""
    del theme  # the page owns the theme; the explorer follows its variables
    fid = fig_dom_id(spec.id)
    rects = layout(spec)
    conn = connections(spec)
    data = payload(spec, fid, rects, conn)
    w, h = WORLD_W, WORLD_H

    tiles: list[str] = []
    for n, depth, _parent in walk(spec.root):
        if depth == 0:
            continue
        x, y, rw, rh = rects[n.id]
        label = n.name
        size = fmt_value(raw_value(n), spec.unit) if raw_value(n) else ""
        status = _status_label(spec, n.status)
        aria = ", ".join(p for p in (label, n.kicker, size, status) if p)
        tiles.append(
            f'<rect class="ve-n{_tone_class(spec, n.status)}" data-id="{escape(n.id, quote=True)}" data-d="{depth}" '
            f'x="{x:g}" y="{y:g}" width="{rw:g}" height="{rh:g}" role="button" tabindex="-1" aria-label="{escape(aria, quote=True)}"/>'
        )

    legend = "".join(
        f'<li class="ve-ex-key{_tone_class(spec, s.key)}"><span class="ve-ex-swatch" aria-hidden="true"></span>'
        f'<span class="ve-ex-key-l">{escape(s.label)}</span>'
        + (f'<span class="ve-ex-key-d">{escape(s.detail)}</span>' if s.detail else "")
        + "</li>"
        for s in spec.statuses
    )
    kinds = "".join(
        f'<li class="ve-ex-kind{" tone-" + k.tone if k.tone in TONES else ""}"><span class="ve-ex-kind-l">{escape(k.label)}</span>'
        + (f'<span class="ve-ex-key-d">{escape(k.detail)}</span>' if k.detail else "")
        + "</li>"
        for k in spec.kinds
    )
    root = spec.root
    root_status = _status_label(spec, root.status)
    return (
        f'<div class="ve-ex" id="{fid}-ex" data-fig="{fid}" data-fig-kind="explorer" data-ve-explorer data-focus="{escape(root.id, quote=True)}" '
        f'role="group" aria-label="{escape(spec.title, quote=True)}">'
        f'<div class="ve-ex-bar"><nav class="ve-ex-crumbs" aria-label="Where you are in the map"><ol></ol></nav>'
        f'<div class="ve-ex-tools"><button type="button" class="ve-ex-btn" data-act="out" aria-label="Zoom out one level">Zoom out</button>'
        f'<button type="button" class="ve-ex-btn" data-act="reset" aria-label="Back to the whole system">Whole system</button></div></div>'
        f'<div class="ve-ex-main">'
        f'<div class="ve-ex-stagewrap"><div class="ve-ex-stage" data-w="{w:g}" data-h="{h:g}" tabindex="-1">'
        f'<svg class="ve-ex-world" viewBox="0 0 {w:g} {h:g}" preserveAspectRatio="none" aria-hidden="false" focusable="false">{"".join(tiles)}</svg>'
        f'<svg class="ve-ex-links" aria-hidden="true" focusable="false"></svg>'
        f'<div class="ve-ex-labels" aria-hidden="true"></div></div>'
        f'<ul class="ve-ex-legend" aria-label="What the colours mean">{legend}</ul>'
        + '<ul class="ve-ex-arrows" aria-label="What the arrows mean">'
        f'<li class="ve-ex-ak ve-ex-ak-out"><span class="ve-ex-ak-line" aria-hidden="true"></span><span class="ve-ex-ak-l">{escape(spec.arrows.out)}</span><span class="ve-ex-key-d">hover a part: {escape(spec.arrows.out_detail)}</span></li>'
        f'<li class="ve-ex-ak ve-ex-ak-in"><span class="ve-ex-ak-line" aria-hidden="true"></span><span class="ve-ex-ak-l">{escape(spec.arrows.into)}</span><span class="ve-ex-key-d">{escape(spec.arrows.into_detail)}</span></li></ul>'
        + (f'<ul class="ve-ex-kinds" aria-label="What the connection kinds mean">{kinds}</ul>' if kinds else "")
        + '<p class="ve-ex-status" role="status" aria-live="polite"></p></div>'
        f'<aside class="ve-ex-panel" aria-label="About the part you are looking at" tabindex="-1">'
        f'<p class="ve-ex-kicker">{escape(root.kicker)}</p><h4 class="ve-ex-title">{escape(root.name)}</h4>'
        + (f'<p class="ve-ex-text">{escape(root.summary)}</p>' if root.summary else "")
        + (f'<p class="ve-ex-text">{escape(root_status)}</p>' if root_status else "")
        + "</aside>"
        '<div class="ve-ex-reader" hidden><button type="button" class="ve-ex-btn" data-act="close-doc">Back to the map</button><div class="ve-ex-reader-body"></div></div>'
        "</div>"
        f"{render_outline(spec, fid, conn)}"
        f'<script type="application/json" class="ve-ex-data">{to_script_json(data)}</script>'
        "</div>"
    )
