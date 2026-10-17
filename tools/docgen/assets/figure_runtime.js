/* docgen figure runtime v1 — one copy per document, ~17 KB, no dependencies, no network, no eval.
 *
 * Upgrades the attribute contract every figure already carries (svg[data-fig], data-s/data-i/data-k/data-id,
 * data-nb/data-eg/data-en, <title>) from "works with no script at all" to:
 *   - a styled tooltip on hover or keyboard focus (the native <title> tooltip is withdrawn so there is only one);
 *   - click to PIN a mark's details (Esc or a click elsewhere releases it);
 *   - "nearest mark" assist: a 7px dot is hit from 14px away;
 *   - focus/adjacency/legend highlighting for diagrams of any size (the CSS-only fallback stops at 160 marks);
 *   - tab stops on the marks of small figures;
 *   - in a graph, the direction of a focused node's lines (leaving / entering / both ways) as classes the figure colours;
 *   - REFERENCE CARDS: every number that points somewhere (Fig. 17, the 8 before a heading, a back-link) carries a
 *     data-ref attribute; hover or focus it and a card says what it is and which documents it draws on.
 *
 * Law: this script only READS the document's own attributes (and the JSON index it ships) and writes classes (`ve-on`,
 * `ve-pin`, `ve-out`, `ve-in`, `ve-both`) and `textContent`. It never builds markup from data, never evaluates a string,
 * never loads anything.
 */
/* global window, document, MouseEvent */
(function () {
  "use strict";
  if (window.__veFigures) { return; }
  window.__veFigures = true;

  const doc = document;
  const tip = doc.createElement("div");
  tip.className = "ve-tip";
  tip.setAttribute("role", "tooltip");
  tip.hidden = true;
  let hovered = null;
  let pinned = null;
  const MAX_NEAR_MARKS = 400;
  const NEAR_PX = 14;
  const KEYBOARD_MAX = 80;

  function tokens(value) { return value ? value.split(" ") : []; }

  function prepare(svg) {
    svg.setAttribute("data-ve-js", "1");
    const marks = svg.querySelectorAll("[data-s],[data-k],[data-t='legend']");
    let n = 0;
    let i;
    for (i = 0; i < marks.length; i++) {
      const m = marks[i];
      let t = null;
      for (let c = m.firstChild; c; c = c.nextSibling) {
        if (c.nodeName === "title") { t = c; break; }
      }
      if (t) {
        const text = t.textContent || "";
        m.setAttribute("data-tip", text);
        m.setAttribute("aria-label", text.split("\n").join(", "));
        m.removeChild(t);
      }
      if (m.hasAttribute("data-id")) { n += 1; }
    }
    if (n > 0 && n <= KEYBOARD_MAX) {
      for (i = 0; i < marks.length; i++) {
        if (marks[i].hasAttribute("data-id") && marks[i].getAttribute("data-k") !== "edge") {
          marks[i].setAttribute("tabindex", "0");
        }
      }
    }
  }

  function clearMarks(svg) {
    if (!svg) { return; }
    const on = svg.querySelectorAll(".ve-on");
    for (let i = 0; i < on.length; i++) { on[i].classList.remove("ve-on", "ve-out", "ve-in", "ve-both"); }
    svg.removeAttribute("data-ve-on");
  }

  function light(svg, list) {
    for (let i = 0; i < list.length; i++) { list[i].classList.add("ve-on"); }
    svg.setAttribute("data-ve-on", "1");
  }

  /* Direction (graphs): while a node is focused, each lit line is read relative to it. A line whose `data-en` is
   * "<from> <to>" LEAVES the node when `from` is the node, ENTERS it when `to` is, and runs BOTH ways when the reverse line
   * exists. The class only names the relation; the figure's own stylesheet decides the colours. */
  function directions(svg, id, lit) {
    const ends = {};
    const edges = svg.querySelectorAll("[data-k='edge'][data-en]");
    let i;
    for (i = 0; i < edges.length; i++) {
      const e = tokens(edges[i].getAttribute("data-en"));
      if (e.length === 2) { ends[e[0] + ">" + e[1]] = true; }
    }
    for (i = 0; i < lit.length; i++) {
      if (lit[i].getAttribute("data-k") !== "edge") { continue; }
      const e = tokens(lit[i].getAttribute("data-en"));
      if (e.length !== 2) { continue; }
      let cls = null;
      if (e[0] === id && e[1] !== id) { cls = "ve-out"; } else if (e[1] === id && e[0] !== id) { cls = "ve-in"; }
      if (cls && ends[e[1] + ">" + e[0]]) { cls = "ve-both"; }
      if (cls) { lit[i].classList.add(cls); }
    }
  }

  /* Marks whose id is in `ids`, plus the numbered circle of any lit edge (a badge names its edge in `data-be`). */
  function byIds(svg, ids) {
    const out = [];
    const all = svg.querySelectorAll("[data-id],[data-be]");
    for (let i = 0; i < all.length; i++) {
      if (ids[all[i].getAttribute("data-id")] || ids[all[i].getAttribute("data-be")]) { out.push(all[i]); }
    }
    return out;
  }

  function sameAttr(svg, name, value, within) {
    const out = [];
    const all = svg.querySelectorAll("[data-s],[data-k]");
    for (let i = 0; i < all.length; i++) {
      if (all[i].getAttribute(name) === value && (!within || all[i].getAttribute(within[0]) === within[1])) { out.push(all[i]); }
    }
    return out;
  }

  /* Which marks stay lit while `mark` is hovered. Mirrors the CSS fallback exactly. */
  function focusOn(svg, mark) {
    clearMarks(svg);
    if (mark.getAttribute("data-t") === "legend") {
      const li = mark.getAttribute("data-i");
      const mode = svg.getAttribute("data-fig-legend");
      if (mode === "series") { light(svg, sameAttr(svg, "data-s", li)); }
      else if (mode === "item") { light(svg, sameAttr(svg, "data-i", li)); }
      return;
    }
    const focus = svg.getAttribute("data-fig-focus") || "item";
    const id = mark.getAttribute("data-id");
    let lit = [mark];
    if (focus === "adjacency" && id) {
      const ids = {};
      ids[id] = true;
      const groups = [mark.getAttribute("data-nb"), mark.getAttribute("data-eg"), mark.getAttribute("data-en")];
      for (let g = 0; g < groups.length; g++) {
        const list = tokens(groups[g]);
        for (let k = 0; k < list.length; k++) { ids[list[k]] = true; }
      }
      lit = byIds(svg, ids);
      if (svg.getAttribute("data-fig-kind") === "graph" && mark.getAttribute("data-k") === "node") {
        light(svg, lit);
        directions(svg, id, lit);
        return;
      }
    } else if (focus === "series") {
      lit = sameAttr(svg, "data-s", mark.getAttribute("data-s"));
    } else if (focus === "index") {
      lit = sameAttr(svg, "data-i", mark.getAttribute("data-i"), ["data-s", mark.getAttribute("data-s")]);
    }
    light(svg, lit);
  }

  function renderTip(text) {
    const lines = (text || "").split("\n");
    while (tip.firstChild) { tip.removeChild(tip.firstChild); }
    for (let i = 0; i < lines.length; i++) {
      const row = doc.createElement(i === 0 ? "strong" : "div");
      row.textContent = lines[i];
      tip.appendChild(row);
    }
    if (pinned) {
      const hint = doc.createElement("div");
      hint.className = "ve-tip-hint";
      hint.textContent = "pinned · Esc or click elsewhere to release";
      tip.appendChild(hint);
    }
    tip.hidden = false;
  }

  function place(x, y) {
    if (!tip.parentNode) { doc.body.appendChild(tip); }
    const w = tip.offsetWidth;
    const h = tip.offsetHeight;
    const vx = window.innerWidth;
    const vy = window.innerHeight;
    let left = x + 14;
    let top = y + 14;
    if (left + w > vx - 8) { left = Math.max(8, x - w - 14); }
    if (top + h > vy - 8) { top = Math.max(8, y - h - 14); }
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }

  function hide() { tip.hidden = true; }

  function markOf(target, svg) {
    if (!target || !target.closest) { return null; }
    const m = target.closest("[data-tip],[data-s],[data-k],[data-t='legend']");
    return m && svg.contains(m) ? m : null;
  }

  /* A 7px dot is hard to hit; if the pointer is within NEAR_PX of a small mark, treat it as hovering that mark. */
  function nearest(svg, x, y) {
    const all = svg.querySelectorAll("[data-s][data-id]:not([data-k='edge'])");
    if (all.length === 0 || all.length > MAX_NEAR_MARKS) { return null; }
    let best = null;
    let bestD = NEAR_PX;
    for (let i = 0; i < all.length; i++) {
      const r = all[i].getBoundingClientRect();
      if (r.width > 28 || r.height > 28) { continue; }
      const d = Math.hypot(r.left + r.width / 2 - x, r.top + r.height / 2 - y);
      if (d < bestD) { bestD = d; best = all[i]; }
    }
    return best;
  }

  function show(svg, mark, x, y) {
    if (hovered !== mark) {
      hovered = mark;
      if (!pinned) { focusOn(svg, mark); }
    }
    if (pinned) { return; }
    const text = mark.getAttribute("data-tip");
    if (!text) { hide(); return; }
    renderTip(text);
    place(x, y);
  }

  function release() {
    if (pinned) {
      pinned.classList.remove("ve-pin");
      const svg = pinned.closest("svg[data-fig]");
      pinned = null;
      clearMarks(svg);
    }
    hovered = null;
    hide();
  }

  function onMove(e) {
    if (pinned) { return; }
    const svg = e.target && e.target.closest ? e.target.closest("svg[data-fig]") : null;
    if (!svg) { if (hovered) { clearMarks(hovered.closest("svg[data-fig]")); hovered = null; } hide(); return; }
    const mark = markOf(e.target, svg) || nearest(svg, e.clientX, e.clientY);
    if (!mark) { clearMarks(svg); hovered = null; hide(); return; }
    show(svg, mark, e.clientX, e.clientY);
  }

  function onClick(e) {
    const svg = e.target && e.target.closest ? e.target.closest("svg[data-fig]") : null;
    const mark = svg ? (markOf(e.target, svg) || nearest(svg, e.clientX, e.clientY)) : null;
    if (mark && mark.getAttribute("data-tip") && mark.getAttribute("data-t") !== "legend" && mark.tagName !== "a") {
      if (pinned) { release(); }
      pinned = mark;
      mark.classList.add("ve-pin");
      focusOn(svg, mark);
      renderTip(mark.getAttribute("data-tip"));
      place(e.clientX, e.clientY);
      return;
    }
    if (pinned) { release(); }
  }

  function onKey(e) {
    if (e.key === "Escape") { release(); hideCard(); }
    if (e.key === "Enter" && e.target && e.target.hasAttribute && e.target.hasAttribute("data-tip")) {
      e.target.dispatchEvent(new MouseEvent("click", { bubbles: true, clientX: e.target.getBoundingClientRect().left, clientY: e.target.getBoundingClientRect().top }));
    }
  }

  function onFocus(e) {
    const t = e.target;
    if (!t || !t.hasAttribute || !t.hasAttribute("data-tip") || pinned) { return; }
    const svg = t.closest("svg[data-fig]");
    const r = t.getBoundingClientRect();
    show(svg, t, r.left + r.width / 2, r.top + r.height / 2);
  }

  function onBlur() { if (!pinned) { hovered = null; hide(); } }

  /* ---- reference cards ---------------------------------------------------------------------------------------------
   * The document ships one JSON index (a script block of type application/json whose id is ve-doc-index): what each figure
   * and section IS, and which documents it draws on. A reference names an entry in its data-ref attribute. Hover or focus it
   * and a card says so; the link itself still navigates, and a pointer can travel from the reference into the card (its
   * links are clickable). */
  const card = doc.createElement("div");
  card.className = "ve-card";
  card.setAttribute("role", "region");
  card.hidden = true;
  let index = null;
  let cardAnchor = null;
  let cardTimer = 0;
  const CARD_SHOW_MS = 90;
  const CARD_HIDE_MS = 200;

  function loadIndex() {
    try {
      const el = doc.getElementById("ve-doc-index");
      const data = el ? JSON.parse(el.textContent) : null;
      index = data && data.v === 1 && data.figures && data.sections ? data : null;
    } catch { index = null; }
  }

  function node(tag, cls, text) {
    const e = doc.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined) { e.textContent = text; }
    return e;
  }

  function anchorTo(text, href) {
    const a = node("a", "ve-card-link", text);
    a.setAttribute("href", href);
    return a;
  }

  function docsBlock(docs) {
    if (!docs || docs.length === 0) { return null; }
    const wrap = node("div", "ve-card-docs");
    wrap.appendChild(node("div", "ve-card-label", "Draws on"));
    const list = node("ul", "ve-card-doclist");
    for (let i = 0; i < docs.length; i++) {
      const d = docs[i];
      const row = node("li", "ve-card-doc");
      if (d.url && /^https?:\/\//.test(d.url)) {
        const a = node("a", "ve-card-link", d.ref);
        a.setAttribute("href", d.url);
        a.setAttribute("target", "_blank");
        a.setAttribute("rel", "noopener noreferrer");
        row.appendChild(a);
      } else {
        const code = node("code", "ve-card-path", d.ref);
        code.setAttribute("data-copy", d.ref);
        code.setAttribute("title", "click to copy this path");
        row.appendChild(code);
      }
      row.appendChild(node("span", "ve-card-kind", d.kind === "mentioned" ? "named in the text" : (d.kind || "source")));
      list.appendChild(row);
    }
    wrap.appendChild(list);
    return wrap;
  }

  function sectionLabel(sec) { return (sec.n ? sec.n + " \u00b7 " : "") + sec.title; }

  function buildCard(id) {
    const fig = index.figures[id];
    const sec = index.sections[id];
    if (!fig && !sec) { return false; }
    while (card.firstChild) { card.removeChild(card.firstChild); }
    let docs = null;
    if (fig) {
      card.appendChild(node("div", "ve-card-kicker", "Fig. " + fig.n + (fig.kind ? " \u00b7 " + fig.kind.split("_").join(" ") : "")));
      card.appendChild(node("div", "ve-card-title", fig.title));
      const home = index.sections[fig.section];
      if (home) { card.appendChild(anchorTo("\u2191 Section " + sectionLabel(home), "#" + fig.section)); }
      if (fig.question) { card.appendChild(node("p", "ve-card-text", fig.question)); }
      docs = fig.docs;
    } else {
      card.appendChild(node("div", "ve-card-kicker", "Section" + (sec.n ? " " + sec.n : "")));
      card.appendChild(node("div", "ve-card-title", sec.title));
      if (sec.lede) { card.appendChild(node("p", "ve-card-text", sec.lede)); }
      if (sec.figures && sec.figures.length) {
        const wrap = node("div", "ve-card-figs");
        wrap.appendChild(node("div", "ve-card-label", sec.figures.length === 1 ? "Figure" : "Figures"));
        for (let i = 0; i < sec.figures.length; i++) {
          const f = index.figures[sec.figures[i]];
          if (f) { wrap.appendChild(anchorTo("Fig. " + f.n + " \u00b7 " + f.title, "#" + sec.figures[i])); }
        }
        card.appendChild(wrap);
      }
      docs = sec.docs;
    }
    const block = docsBlock(docs);
    if (block) { card.appendChild(block); }
    return true;
  }

  function placeCard(anchor) {
    if (!card.parentNode) { doc.body.appendChild(card); }
    card.hidden = false;
    const r = anchor.getBoundingClientRect();
    const w = card.offsetWidth;
    const h = card.offsetHeight;
    const vx = window.innerWidth;
    const vy = window.innerHeight;
    let left = Math.min(Math.max(8, r.left), Math.max(8, vx - w - 8));
    let top = r.bottom + 8;
    if (top + h > vy - 8 && r.top - h - 8 >= 8) { top = r.top - h - 8; }
    top = Math.max(8, Math.min(top, vy - h - 8));
    left = Math.max(8, left);
    card.style.left = left + "px";
    card.style.top = top + "px";
  }

  function hideCard() {
    window.clearTimeout(cardTimer);
    card.hidden = true;
    cardAnchor = null;
  }

  function refOf(target) {
    if (!index || !target || !target.closest || card.contains(target)) { return null; }
    const a = target.closest("[data-ref]");
    return a && (index.figures[a.getAttribute("data-ref")] || index.sections[a.getAttribute("data-ref")]) ? a : null;
  }

  function showCard(anchor) {
    window.clearTimeout(cardTimer);
    if (cardAnchor === anchor && !card.hidden) { return; }
    if (!buildCard(anchor.getAttribute("data-ref"))) { return; }
    cardAnchor = anchor;
    placeCard(anchor);
  }

  function scheduleHide() {
    window.clearTimeout(cardTimer);
    cardTimer = window.setTimeout(hideCard, CARD_HIDE_MS);
  }

  function onRefOver(e) {
    if (e.pointerType === "touch") { return; }
    const a = refOf(e.target);
    if (a) {
      window.clearTimeout(cardTimer);
      if (a !== cardAnchor) { cardTimer = window.setTimeout(function () { showCard(a); }, CARD_SHOW_MS); }
    } else if (card.contains(e.target)) {
      window.clearTimeout(cardTimer);
    }
  }

  function onRefOut(e) {
    if (e.pointerType === "touch") { return; }
    const leaving = refOf(e.target) || (card.contains(e.target) ? card : null);
    if (!leaving) { return; }
    const to = e.relatedTarget;
    if (to && (card.contains(to) || (cardAnchor && cardAnchor.contains(to)))) { return; }
    scheduleHide();
  }

  function onRefFocus(e) {
    const a = refOf(e.target);
    if (a) { showCard(a); }
  }

  function onRefBlur(e) {
    const to = e.relatedTarget;
    if (to && card.contains(to)) { return; }
    if (refOf(e.target)) { scheduleHide(); }
  }

  function onCardClick(e) {
    const t = e.target;
    if (!t || !t.closest) { return; }
    if (card.contains(t)) {
      const copy = t.closest("[data-copy]");
      if (copy) {
        const text = copy.getAttribute("data-copy");
        try { window.navigator.clipboard.writeText(text); copy.setAttribute("data-copied", "1"); } catch { /* no clipboard: the path is still on screen */ }
        return;
      }
      if (t.closest("a[href^='#']")) { hideCard(); }
    } else if (!card.hidden && !t.closest("[data-ref]")) {
      hideCard();
    }
  }

  function init() {
    loadIndex();
    if (index) {
      doc.addEventListener("pointerover", onRefOver);
      doc.addEventListener("pointerout", onRefOut);
      doc.addEventListener("focusin", onRefFocus);
      doc.addEventListener("focusout", onRefBlur);
      doc.addEventListener("click", onCardClick);
    }
    const figs = doc.querySelectorAll("svg[data-fig]");
    for (let i = 0; i < figs.length; i++) { prepare(figs[i]); }
    if (figs.length === 0) { return; }
    doc.body.appendChild(tip);
    doc.addEventListener("pointermove", onMove, { passive: true });
    doc.addEventListener("click", onClick);
    doc.addEventListener("keydown", onKey);
    doc.addEventListener("focusin", onFocus);
    doc.addEventListener("focusout", onBlur);
    window.addEventListener("scroll", function () {
      if (!pinned) { hide(); }
      if (card.hidden) { return; }
      // A card a keyboard focus opened follows its reference (focus itself scrolls the page); a hover card just goes away.
      if (cardAnchor && doc.activeElement === cardAnchor) { placeCard(cardAnchor); } else { hideCard(); }
    }, { passive: true });
  }

  if (doc.readyState === "loading") { doc.addEventListener("DOMContentLoaded", init); } else { init(); }
}());
