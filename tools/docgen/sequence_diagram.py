"""SequenceSpec -> SVG renderer (VISUAL_LIBRARY.md catalog: "who talks to whom, in what
order, over time"). A genuinely different visual convention from the flowchart family:
vertical actor lifelines + horizontal ordered messages, not a node/edge graph.

Static by design (no animated dot) — the numbered message badges already state the
travel order explicitly (VISUAL_LIBRARY §3: "the static state must already tell the
story"), matching the flowchart family's own reduced-motion fallback convention.

Reuses the flowchart family's generic geometry/text/escape helpers (``tools.docgen.visual``)
so collision math and formatting stay identical across every figure type in the engine.

Stdlib only; mypy --strict clean; deterministic (2dp-rounded floats, stable ordering).
"""

from __future__ import annotations

from tools.docgen.figure_support import KeyItem, fig_dom_id, native_figure_css
from tools.docgen.models import Finding, Message, SequenceSpec, Severity
from tools.docgen.visual import (
    BBox,
    _escape,
    _fmt,
    _gap,
    _intersects,
    _r,
    _text_box,
)

_LIFELINE_TOP = 56.0
# A title is drawn on the baseline y=20 (18px type, so its glyphs end near y=24); the actor boxes used to start at y=20,
# so a centred title sat on the middle participant. Titled figures push the whole diagram down by this much, and a spec
# whose height was valid before is drawn at most this much taller (``_canvas_height``) instead of being refused: an engine
# upgrade must never turn a document that built into one that does not. A spec short by MORE than this is still refused.
_TITLE_RESERVE_PX = 24.0
_BADGE_R = 12.0
_ROW_GAP_PX = 48.0
_ACTOR_BOX_W = 120.0
_ACTOR_BOX_H = 36.0
_LABEL_FONT_PX = 12.0
_ARROW_HEAD_LEN = 9.0
_CAPTION_RESERVE_PX = 40.0


class SequenceCollisionError(RuntimeError):
    """Raised by ``render`` when ``check_collisions`` finds a blocking overlap."""


def _actor_x_positions(spec: SequenceSpec) -> dict[str, float]:
    n = len(spec.actors)
    if n == 0:
        return {}
    step = spec.width / (n + 1)
    return {actor.id: _r(step * (i + 1)) for i, actor in enumerate(spec.actors)}


def _top(spec: SequenceSpec) -> float:
    """Y of the actor boxes' bottom edge / lifeline start: lower when the figure has a title above it."""
    return _LIFELINE_TOP + (_TITLE_RESERVE_PX if spec.title else 0.0)


def _required_height(spec: SequenceSpec) -> float:
    rows = len(spec.messages)
    return _top(spec) + _ACTOR_BOX_H + rows * _ROW_GAP_PX + _CAPTION_RESERVE_PX


def _canvas_height(spec: SequenceSpec) -> float:
    """The height the figure is drawn at: the spec's, grown by at most the title reserve.

    The title reserve (``OG-257``) is the engine's own addition, so it must not turn a spec that built before it into a
    refusal (the host's own test suite found one: a titled, one-message spec at height 200 was valid at the old 180 minimum
    and refused at the new 204). A spec that clears the requirement WITHOUT the reserve is drawn at the requirement WITH it;
    one that is short by more than the reserve is still refused, exactly as before.
    """
    need = _required_height(spec)
    legacy_need = need - (_TITLE_RESERVE_PX if spec.title else 0.0)
    return need if legacy_need <= spec.height < need else spec.height


def _row_y(spec: SequenceSpec, idx: int) -> float:
    """Y of the idx-th message's arrow (0-based): one row gap below the one before it."""
    return _r(_top(spec) + _ACTOR_BOX_H / 2 + (idx + 1) * _ROW_GAP_PX)


def _lifeline_spans(top: float, bottom: float, gaps: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """The spans a lifeline is drawn in: the whole line minus the intervals a message label sits across it.

    A label that crosses a participant's dashed lifeline used to have the line run through its letters
    ("refund only |f unclaimed"); cutting the line behind the text needs no plate and no halo (`OG-271`).
    """
    spans: list[tuple[float, float]] = []
    cur = top
    for g0, g1 in sorted(gaps):
        if g1 <= cur:
            continue
        if g0 > cur:
            spans.append((cur, min(g0, bottom)))
        cur = max(cur, g1)
    if cur < bottom:
        spans.append((cur, bottom))
    return [(a, b) for a, b in spans if b - a > 0.5]


def message_kind(msg: Message, x0: float, x1: float) -> str:
    """Colour class of a message: explicit ``kind``, else dashed = async, left-to-right = call, right-to-left = return."""
    if msg.kind in ("call", "return", "async", "error"):
        return msg.kind
    if msg.style == "dashed":
        return "async"
    return "call" if x1 >= x0 else "return"


def reading_key(spec: SequenceSpec) -> list[KeyItem]:
    """The numbered explanation of the circles on the messages — the SAME numbering ``render`` draws."""
    labels = {a.id: a.label for a in spec.actors}
    fid = fig_dom_id(spec.id)
    out: list[KeyItem] = []
    for idx, msg in enumerate(sorted(spec.messages, key=lambda m: m.order)):
        bits = [msg.label] if msg.label else []
        if msg.note:
            bits.append(msg.note)
        out.append(
            {
                "n": idx + 1,
                "title": f"{labels.get(msg.src, msg.src)} \u2192 {labels.get(msg.dst, msg.dst)}",
                "detail": " \u00b7 ".join(bits),
                "anchor": f"{fid}-k{idx + 1}",
            }
        )
    return out


HOW_TO_READ_SEQUENCE = (
    "Time runs from top to bottom. Each column is a participant and each arrow a message between two of them: blue "
    "arrows are calls, green arrows are results coming back, gold dashed arrows are queued or asynchronous work. "
    "Numbered circles give the order and each number is explained below. Hover a participant to light up its messages."
)


def check_collisions(spec: SequenceSpec) -> list[Finding]:
    """Blocking findings: unknown actor refs, duplicate ``order`` values, actor-label
    overlap, and insufficient ``height`` for the message count (the vertical analogue
    of the flowchart family's overlap-can-never-ship rule).
    """
    findings: list[Finding] = []
    actor_ids = {a.id for a in spec.actors}

    for msg in spec.messages:
        if msg.src not in actor_ids:
            findings.append(
                Finding(
                    # `sequence.rule`, not `sequence.collision` (`OG-195`). The four
                    # well-formedness findings here used to carry the collision label, and that
                    # label maps to CONTRADICTION row 9 — so an "unknown src actor" reference
                    # error was annotated with *"legibility wins; expressiveness is bounded by the
                    # contrast floor"*, advice about nothing it describes. The geometry findings
                    # keep `.collision`: a diagram too short to separate its messages IS a
                    # legibility failure.
                    gate="sequence.rule",
                    message=f"Message references unknown src actor '{msg.src}'",
                    severity=Severity.CRIT,
                    blocking=True,
                )
            )
        if msg.dst not in actor_ids:
            findings.append(
                Finding(
                    gate="sequence.rule",
                    message=f"Message references unknown dst actor '{msg.dst}'",
                    severity=Severity.CRIT,
                    blocking=True,
                )
            )
        if msg.src == msg.dst:
            findings.append(
                Finding(
                    gate="sequence.rule",
                    message=f"Self-messages are not supported yet (src==dst=='{msg.src}')",
                    severity=Severity.CRIT,
                    blocking=True,
                )
            )

    orders = [m.order for m in spec.messages]
    seen: set[int] = set()
    for order in orders:
        if order in seen:
            findings.append(
                Finding(
                    gate="sequence.rule",
                    message=f"Duplicate message order={order} (ambiguous vertical position)",
                    severity=Severity.CRIT,
                    blocking=True,
                )
            )
        seen.add(order)

    required_h = _required_height(spec)
    if _canvas_height(spec) < required_h:
        findings.append(
            Finding(
                gate="sequence.collision",
                message=f"height={spec.height} is below the {required_h:.2f}px required for {len(spec.messages)} message(s)",
                severity=Severity.CRIT,
                blocking=True,
            )
        )

    xs = _actor_x_positions(spec)
    boxes: list[BBox] = []
    for actor in spec.actors:
        x = xs.get(actor.id, 0.0)
        box = _text_box(x, _top(spec) - _ACTOR_BOX_H / 2, actor.label, _LABEL_FONT_PX)
        boxes.append(box)
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if _intersects(boxes[i], boxes[j]):
                findings.append(
                    Finding(
                        gate="sequence.collision",
                        message=f"Actor label boxes {i} and {j} overlap",
                        severity=Severity.CRIT,
                        blocking=True,
                    )
                )
            elif _gap(boxes[i], boxes[j]) < 22.0:
                findings.append(
                    Finding(
                        gate="sequence.collision",
                        message=f"Actor label gap between boxes {i} and {j} below the 22px minimum",
                        severity=Severity.CRIT,
                        blocking=True,
                    )
                )

    return findings


def _defs_css() -> str:
    return (
        "<style><![CDATA["
        ".lifeline{stroke:currentColor;stroke-width:1;stroke-dasharray:4 4;opacity:0.5;}"
        ".actor-box{fill:none;stroke:currentColor;stroke-width:1.5;}"
        ".actor-label,.msg-label,.figure-caption{font-family:var(--f-body,Inter,system-ui,sans-serif);fill:currentColor;}"
        ".msg-line{stroke:currentColor;stroke-width:2;fill:none;}"
        ".msg-line-dashed{stroke-dasharray:6 4;}"
        # One colour per kind of message, line AND head: direction and kind read at a glance.
        ".msg-call{stroke:var(--shield-hi,#4A7FC1);}.msg-head-call{fill:var(--shield-hi,#4A7FC1);}"
        ".msg-return{stroke:var(--verify,#3DA875);}.msg-head-return{fill:var(--verify,#3DA875);}"
        ".msg-async{stroke:var(--gold-hi,#EDB84A);}.msg-head-async{fill:var(--gold-hi,#EDB84A);}"
        ".msg-error{stroke:var(--ember-hi,#E03638);}.msg-head-error{fill:var(--ember-hi,#E03638);}"
        ".msg-hit{fill:none;stroke:transparent;stroke-width:16;pointer-events:stroke;}"
        ".msg-badge{fill:var(--paper-2,#141420);stroke:var(--shield-hi,#4A7FC1);stroke-width:1.8;}"
        ".msg-badge-label{font-family:var(--f-mono,ui-monospace,monospace);font-size:12px;font-weight:700;"
        "fill:var(--fg,currentColor);pointer-events:none;}"
        "a.fig-badge{cursor:pointer;}"
        "]]></style>"
    )


def render(spec: SequenceSpec, *, theme: str | None = None) -> str:
    """Render ``spec`` to a complete, self-contained ``<svg>``. Raises
    ``SequenceCollisionError`` on any blocking finding (never ships an overlap).
    Deterministic: identical input -> byte-identical output on every call.

    Carries the figure attribute contract (``data-fig``, ``data-k``, ``data-id``, ``data-nb``, ``data-eg``,
    ``data-en``, ``<title>`` per element) and its own scoped hover CSS, like every native figure.
    """
    collisions = check_collisions(spec)
    if collisions:
        messages = "; ".join(f.message for f in collisions)
        raise SequenceCollisionError(
            f"{spec.id}: {len(collisions)} blocking collision(s): {messages}"
        )

    fid = fig_dom_id(spec.id)
    xs = _actor_x_positions(spec)
    top = _top(spec)
    labels = {a.id: a.label for a in spec.actors}
    actor_idx = {a.id: f"n{i}" for i, a in enumerate(spec.actors)}
    ordered_messages: list[Message] = sorted(spec.messages, key=lambda m: m.order)
    key = {item["n"]: item for item in reading_key(spec)}

    # adjacency: an actor lights its own messages and the actors on the other end
    nb: dict[str, list[str]] = {i: [] for i in actor_idx.values()}
    eg: dict[str, list[str]] = {i: [] for i in actor_idx.values()}
    ends: list[tuple[str, list[str]]] = []
    for idx, msg in enumerate(ordered_messages):
        a, b = actor_idx[msg.src], actor_idx[msg.dst]
        ends.append((f"e{idx}", [a, b]))
        for p, q in ((a, b), (b, a)):
            if q not in nb[p]:
                nb[p].append(q)
            eg[p].append(f"e{idx}")

    parts: list[str] = [_defs_css()]
    height = _canvas_height(spec)
    lifeline_bottom = height - _CAPTION_RESERVE_PX
    label_boxes: list[BBox] = []
    for idx, msg in enumerate(ordered_messages):
        if msg.label:
            lx = _r((xs[msg.src] + xs[msg.dst]) / 2)
            label_boxes.append(_text_box(lx, _row_y(spec, idx) - 7.0 - _LABEL_FONT_PX * 0.35, msg.label, _LABEL_FONT_PX))
    for actor in spec.actors:
        x = xs[actor.id]
        gaps = [(b[1] - 2.0, b[3] + 2.0) for b in label_boxes if b[0] - 3.0 <= x <= b[2] + 3.0]
        for y0, y1 in _lifeline_spans(top, lifeline_bottom, gaps):
            parts.append(
                f'<line class="lifeline" x1="{_fmt(x)}" y1="{_fmt(y0)}" '
                f'x2="{_fmt(x)}" y2="{_fmt(y1)}"/>'
            )

    for actor in spec.actors:
        x = xs[actor.id]
        aid = actor_idx[actor.id]
        box_x = _r(x - _ACTOR_BOX_W / 2)
        box_y = _r(top - _ACTOR_BOX_H)
        sends = [labels[m.dst] for m in ordered_messages if m.src == actor.id]
        gets = [labels[m.src] for m in ordered_messages if m.dst == actor.id]
        tip = [actor.label]
        if sends:
            tip.append("\u2192 " + ", ".join(dict.fromkeys(sends)))
        if gets:
            tip.append("\u2190 " + ", ".join(dict.fromkeys(gets)))
        parts.append(
            f'<g class="node" data-k="node" data-id="{aid}" data-nb="{" ".join(nb[aid])}" data-eg="{" ".join(eg[aid])}">'
            f"<title>{_escape(chr(10).join(tip))}</title>"
            f'<rect class="actor-box" x="{_fmt(box_x)}" y="{_fmt(box_y)}" '
            f'width="{_fmt(_ACTOR_BOX_W)}" height="{_fmt(_ACTOR_BOX_H)}" rx="6"/></g>'
            f'<text class="actor-label" x="{_fmt(x)}" y="{_fmt(top - _ACTOR_BOX_H / 2 + 4.0)}" '
            f'text-anchor="middle" font-size="{_LABEL_FONT_PX}">{_escape(actor.label)}</text>'
        )

    for idx, msg in enumerate(ordered_messages):
        y = _row_y(spec, idx)
        x0, x1 = xs[msg.src], xs[msg.dst]
        direction = 1.0 if x1 >= x0 else -1.0
        arrow_x1 = _r(x1 - direction * _ARROW_HEAD_LEN)
        kind = message_kind(msg, x0, x1)
        cls = f"msg-line msg-{kind}" + (" msg-line-dashed" if msg.style == "dashed" else "")
        eid = f"e{idx}"
        en = " ".join(dict.fromkeys([actor_idx[msg.src], actor_idx[msg.dst]]))
        tip = [f"{labels[msg.src]} \u2192 {labels[msg.dst]}"]
        if msg.label:
            tip.append(msg.label)
        if msg.note:
            tip.append(msg.note)
        title = f"<title>{_escape(chr(10).join(tip))}</title>"
        attrs = f'data-k="edge" data-id="{eid}" data-en="{en}"'
        parts.append(
            f'<line class="{cls}" x1="{_fmt(x0)}" y1="{_fmt(y)}" x2="{_fmt(arrow_x1)}" y2="{_fmt(y)}" {attrs}>{title}</line>'
        )
        parts.append(f'<line class="msg-hit" x1="{_fmt(x0)}" y1="{_fmt(y)}" x2="{_fmt(x1)}" y2="{_fmt(y)}" {attrs}>{title}</line>')
        head = _r(5.0) * direction
        parts.append(
            f'<polygon class="msg-head-{kind}" points="'
            f"{_fmt(x1)},{_fmt(y)} {_fmt(x1 - direction * _ARROW_HEAD_LEN)},{_fmt(y - abs(head))} "
            f'{_fmt(x1 - direction * _ARROW_HEAD_LEN)},{_fmt(y + abs(head))}" pointer-events="none"/>'
        )
        label_x = _r((x0 + x1) / 2)
        if msg.label:
            parts.append(
                f'<text class="msg-label" x="{_fmt(label_x)}" y="{_fmt(y - 7.0)}" '
                f'text-anchor="middle" font-size="{_LABEL_FONT_PX}">{_escape(msg.label)}</text>'
            )
        badge_x = max(_BADGE_R + 2.0, min(x0, x1) - 24.0)
        step_title = f"Step {idx + 1}: {key[idx + 1]['title']}"
        step_tip = step_title + (f"\n{key[idx + 1]['detail']}" if key[idx + 1]["detail"] else "")
        parts.append(
            f'<a class="fig-badge" href="#{fid}-k{idx + 1}" data-k="badge" data-id="b{idx + 1}" data-be="e{idx}" aria-label="{_escape(step_title)}">'
            f"<title>{_escape(step_tip)}</title>"
            f'<circle class="msg-badge" cx="{_fmt(badge_x)}" cy="{_fmt(y)}" r="{_fmt(_BADGE_R)}"/>'
            f'<text class="msg-badge-label" x="{_fmt(badge_x)}" y="{_fmt(y + 4.2)}" text-anchor="middle">{idx + 1}</text></a>'
        )

    if spec.title:
        parts.append(
            f'<text x="{_fmt(spec.width / 2)}" y="22" class="figure-title" '
            f'font-size="18" text-anchor="middle" font-weight="700" fill="currentColor">{_escape(spec.title)}</text>'
        )
    if spec.caption:
        parts.append(
            f'<text x="{_fmt(spec.width / 2)}" y="{_fmt(height - 10.0)}" '
            f'class="figure-caption" font-size="12" text-anchor="middle">{_escape(spec.caption)}</text>'
        )
    scoped = native_figure_css(fid, [(actor_idx[a.id], nb[actor_idx[a.id]], eg[actor_idx[a.id]]) for a in spec.actors], ends)
    parts.insert(1, f'<style data-ve="{fid}"><![CDATA[{scoped}]]></style>')

    body = "".join(parts)
    # Stamp data-theme ONLY when a caller explicitly pins a theme (the standalone-SVG CLI
    # path). Embedded in a docgen document the page owns the theme: tokens.py declares the
    # palette on `[data-theme="dark"]` / `[data-theme="light"]`, so a data-theme attribute on
    # the <svg> re-declares that whole palette ON THE FIGURE — a descendant of the <html> the
    # toggle writes to — and the figure keeps its pinned colours while the rest of the page
    # switches. Measured: with a hardcoded "dark" default, 7 of 21 figures in a real document
    # stayed dark in light mode. None = inherit from the page, which is what an embedded
    # figure should always do.
    theme_attr = f'data-theme="{theme}" ' if theme else ""
    return (
        f'<svg viewBox="0 0 {_fmt(spec.width)} {_fmt(height)}" '
        f'xmlns="http://www.w3.org/2000/svg" class="fig-figure fig-sequence" data-fig="{fid}" '
        f'data-fig-kind="sequence" data-fig-focus="adjacency" {theme_attr}'
        f'role="img" aria-label="{_escape(spec.title or spec.id)}">{body}</svg>'
    )
