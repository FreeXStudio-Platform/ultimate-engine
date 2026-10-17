/* docgen explorer runtime v1 — one copy per document that holds an explorer; no dependencies, no network, no eval.
 *
 * Takes over the markup `tools/docgen/explorer.py` renders (a stage of rectangles, a panel, a reader, a trail) and the JSON that
 * module ships next to it, and makes the hierarchy explorable:
 *   - click a part and the camera glides into it (the part's children appear inside it); Escape, the trail, the Zoom out button
 *     or the Whole system button go back up; a name in the panel (what a part calls, who calls it, what is inside it) takes you
 *     there, zooming out and in as needed;
 *   - hover a part and its connections to its siblings are drawn as arrows (blue: it calls; pink: it is called by);
 *   - the panel says what the part is, how big, what colour state it is in, what it connects to, which documents describe it
 *     (opened in place in the reader) and where this document talks about it;
 *   - the keyboard works: Tab to the map, arrows move between parts, Enter opens one, Escape goes up;
 *   - `prefers-reduced-motion` turns every glide into a cut.
 *
 * Law (same as the figure runtime): this script READS the explorer's JSON and the document's own markup and writes DOM with
 * `createElement` / `textContent` / `setAttribute` and class names. It never builds markup from data, never evaluates a
 * string, never loads anything. A document's HTML (the reader) is CLONED from the outline the page already carries.
 */
/* global window, document, requestAnimationFrame, cancelAnimationFrame, ResizeObserver */
(function () {
  "use strict";
  if (window.__veExplorers) { return; }
  window.__veExplorers = {};

  const doc = document;
  const SVG_NS = "http://www.w3.org/2000/svg";
  const GLIDE_MS = 560;
  const HALF_GLIDE_MS = 380;
  const MIN_LABEL_W = 52;
  const MIN_LABEL_H = 24;

  function el(tag, cls, text) {
    const e = doc.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined) { e.textContent = text; }
    return e;
  }

  function svgEl(tag, attrs) {
    const e = doc.createElementNS(SVG_NS, tag);
    if (attrs) { for (const k in attrs) { e.setAttribute(k, String(attrs[k])); } }
    return e;
  }

  function fmt(n) { return Math.round(n).toLocaleString("en-US"); }
  function reducedMotion() { return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); }
  function ease(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  function toneClass(tone) { return tone && tone !== "none" ? " tone-" + tone : ""; }

  function Explorer(root) {
    const dataEl = root.querySelector("script.ve-ex-data");
    let data;
    try { data = JSON.parse(dataEl.textContent); } catch { return null; }
    if (!data || data.v !== 1 || !data.nodes || !data.nodes[data.root]) { return null; }

    const nodes = data.nodes;
    const stage = root.querySelector(".ve-ex-stage");
    const world = root.querySelector(".ve-ex-world");
    const linksSvg = root.querySelector(".ve-ex-links");
    const labels = root.querySelector(".ve-ex-labels");
    const panel = root.querySelector(".ve-ex-panel");
    const reader = root.querySelector(".ve-ex-reader");
    const readerBody = root.querySelector(".ve-ex-reader-body");
    const crumbs = root.querySelector(".ve-ex-crumbs ol");
    const statusEl = root.querySelector(".ve-ex-status");
    const outBtn = root.querySelector('[data-act="out"]');
    const resetBtn = root.querySelector('[data-act="reset"]');
    const tiles = {};
    const tileEls = world.querySelectorAll(".ve-n");
    for (let i = 0; i < tileEls.length; i++) { tiles[tileEls[i].getAttribute("data-id")] = tileEls[i]; }

    let focus = data.root;
    let selected = null;
    let hover = null;
    let cursor = null;
    let cam = { x: 0, y: 0, w: data.w, h: data.h };
    let frame = 0;
    let moving = false;
    let readerOpen = false;
    const tip = window.__veExTip || (window.__veExTip = (function () {
      const t = el("div", "ve-tip ve-ex-tip");
      t.setAttribute("role", "tooltip");
      t.hidden = true;
      doc.body.appendChild(t);
      return t;
    }()));

    function rectOf(id) { const r = nodes[id].r; return { x: r[0], y: r[1], w: r[2], h: r[3] }; }
    function name(id) { return nodes[id].n; }
    function chain(id) { const out = []; for (let n = id; n; n = nodes[n].p) { out.unshift(n); } return out; }

    /* ---- camera ------------------------------------------------------------------------------------------------- */
    function setCamera(r) {
      cam = { x: r.x, y: r.y, w: r.w, h: r.h };
      world.setAttribute("viewBox", r.x + " " + r.y + " " + r.w + " " + r.h);
    }

    function showTiles(ids) {
      const on = {};
      for (let i = 0; i < ids.length; i++) { on[ids[i]] = true; }
      for (const id in tiles) { tiles[id].classList.toggle("ve-off", !on[id]); }
    }

    function childrenOf(id) { return nodes[id].c; }

    /* The camera glides from `a` to `b`: both sides of the frame move at one perceived speed (width and height change by the
     * same ratio, the pan follows the zoom), so the target seems to grow out of the screen rather than slide across it. */
    function frameAt(a, b, e) {
      const k = Math.pow(b.w / a.w, e);
      const kh = Math.pow(b.h / a.h, e);
      const w = a.w * k;
      const h = a.h * kh;
      const px = Math.abs(1 - b.w / a.w) < 1e-6 ? e : (1 - w / a.w) / (1 - b.w / a.w);
      const py = Math.abs(1 - b.h / a.h) < 1e-6 ? e : (1 - h / a.h) / (1 - b.h / a.h);
      return { x: a.x + (b.x - a.x) * px, y: a.y + (b.y - a.y) * py, w: w, h: h };
    }

    function glide(to, ms, done) {
      cancelAnimationFrame(frame);
      const from = { x: cam.x, y: cam.y, w: cam.w, h: cam.h };
      if (reducedMotion() || ms <= 0) { setCamera(to); done(); return; }
      const start = window.performance.now();
      function step(now) {
        const t = Math.min(1, (now - start) / ms);
        setCamera(t >= 1 ? to : frameAt(from, to, ease(t)));
        if (t < 1) { frame = requestAnimationFrame(step); } else { done(); }
      }
      frame = requestAnimationFrame(step);
    }

    /* ---- navigation --------------------------------------------------------------------------------------------- */
    function begin() {
      moving = true;
      root.removeAttribute("data-settled");
      stage.classList.add("ve-moving");
      hideTip();
      clearHover();
      labels.replaceChildren();
      linksSvg.replaceChildren();
    }

    function settle(target) {
      focus = target;
      moving = false;
      stage.classList.remove("ve-moving");
      showTiles(childrenOf(target));
      cursor = cursor && nodes[cursor] && nodes[cursor].p === target ? cursor : (childrenOf(target)[0] || null);
      root.setAttribute("data-focus", target);
      root.setAttribute("data-settled", "1");
      renderChrome();
      renderOverlay();
      /* The part that was clicked has just been hidden, and the focus went with it: keep the keyboard (Escape, arrows) on the map. */
      const held = doc.activeElement;
      if (!held || held === doc.body || root.contains(held)) { stage.focus({ preventScroll: true }); }
      announce("Showing " + name(target) + (childrenOf(target).length ? ": " + childrenOf(target).length + " parts inside." : "."));
    }

    /* Go to `target`: zoom out to the common ancestor if the target is not inside the current focus, then in. */
    function go(target, then) {
      if (!nodes[target]) { return; }
      if (!nodes[target].c.length) { reveal(target); return; }
      if (target === focus && !moving) { if (then) { then(); } return; }
      closeReader();
      begin();
      const visible = {};
      function mark(id) { visible[id] = true; for (let i = 0; i < nodes[id].c.length; i++) { visible[nodes[id].c[i]] = true; } }
      mark(focus);
      mark(target);
      const a = chain(focus);
      const b = chain(target);
      let k = 0;
      while (k < a.length && k < b.length && a[k] === b[k]) { k += 1; }
      const lca = a[k - 1];
      const viaLca = lca !== focus && lca !== target;
      if (viaLca) { mark(lca); }
      showTiles(Object.keys(visible));
      const finish = function () { settle(target); if (then) { then(); } };
      if (viaLca) {
        glide(rectOf(lca), HALF_GLIDE_MS, function () { glide(rectOf(target), HALF_GLIDE_MS, finish); });
      } else {
        glide(rectOf(target), GLIDE_MS, finish);
      }
    }

    /* Select a leaf (or any part): make its parent the focus if it is not, then mark it. */
    function reveal(id) {
      const parent = nodes[id].p;
      const select = function () { selected = id; cursor = id; renderChrome(); renderOverlay(); const t = tiles[id]; if (t) { t.setAttribute("tabindex", "0"); } };
      if (parent && parent !== focus) { go(parent, select); } else { select(); }
    }

    function up() {
      closeReader();
      if (focus === data.root) { return; }
      go(nodes[focus].p);
    }

    /* ---- the stage: labels and arrows, in pixels, after the camera has stopped ------------------------------------ */
    function stagePx() { const b = stage.getBoundingClientRect(); return { w: b.width, h: b.height }; }

    function tilePx(id, px) {
      const r = nodes[id].r;
      return { x: (r[0] - cam.x) * px.w / cam.w, y: (r[1] - cam.y) * px.h / cam.h, w: r[2] * px.w / cam.w, h: r[3] * px.h / cam.h };
    }

    function renderLabels() {
      labels.replaceChildren();
      const px = stagePx();
      const kids = childrenOf(focus);
      for (let i = 0; i < kids.length; i++) {
        const id = kids[i];
        const b = tilePx(id, px);
        if (b.w < MIN_LABEL_W || b.h < MIN_LABEL_H) { continue; }
        const n = nodes[id];
        const lab = el("div", "ve-ex-label" + (b.w * b.h > 40000 ? " ve-big" : ""));
        lab.style.left = b.x + "px";
        lab.style.top = b.y + "px";
        lab.style.width = b.w + "px";
        lab.style.height = b.h + "px";
        const size = Math.max(12, Math.min(22, Math.sqrt(b.w * b.h) / 11));
        lab.style.fontSize = size + "px";
        lab.appendChild(el("span", "ve-ex-label-n", n.n));
        if (b.h > 52 && n.v) { lab.appendChild(el("span", "ve-ex-label-v", fmt(n.v) + " " + data.unit)); }
        if (n.c.length && b.h > 74) { lab.appendChild(el("span", "ve-ex-label-c", n.c.length + (n.c.length === 1 ? " part inside" : " parts inside"))); }
        labels.appendChild(lab);
        fitLabel(lab, size);
      }
    }

    /* A name is never cut inside a word and never clipped: shrink it to the smallest readable size; if it still does not fit, drop
     * the size and count lines, and if it still does not fit draw no label at all (the tooltip and the panel name every part). */
    function fitLabel(lab, size) {
      const name = lab.firstChild;
      const room = function () {
        if (name.scrollWidth > name.clientWidth + 0.5 || lab.scrollHeight > lab.clientHeight + 0.5) { return false; }
        for (let i = 1; i < lab.children.length; i++) { if (lab.children[i].scrollWidth > lab.clientWidth - 15) { return false; } }
        return true;
      };
      let fs = size;
      while (!room() && fs > 10) { fs -= 1; lab.style.fontSize = fs + "px"; }
      while (!room() && lab.children.length > 1) { lab.removeChild(lab.lastChild); }
      if (!room()) { lab.remove(); }
    }

    function arrow(from, to, kind, weight, color) {
      const ax = from.x + from.w / 2;
      const ay = from.y + from.h / 2;
      const bx = to.x + to.w / 2;
      const by = to.y + to.h / 2;
      const mx = (ax + bx) / 2;
      const my = (ay + by) / 2;
      const nx = -(by - ay);
      const ny = bx - ax;
      const len = Math.max(1, Math.hypot(nx, ny));
      const bend = Math.min(60, len * 0.18);
      const cx = mx + (nx / len) * bend;
      const cy = my + (ny / len) * bend;
      const path = svgEl("path", {
        d: "M" + ax + " " + ay + " Q" + cx + " " + cy + " " + bx + " " + by, "class": "ve-ex-arrow ve-ex-" + color,
        "marker-end": "url(#" + data.id + "-head-" + color + ")",
      });
      path.style.strokeWidth = (1.6 + Math.min(3, Math.log10(Math.max(1, weight)) * 1.2)) + "px";
      if (kind) { path.setAttribute("data-kind", kind); }
      return path;
    }

    function renderLinks() {
      linksSvg.replaceChildren();
      const px = stagePx();
      linksSvg.setAttribute("viewBox", "0 0 " + px.w + " " + px.h);
      const defs = svgEl("defs");
      ["out", "in"].forEach(function (c) {
        const m = svgEl("marker", { id: data.id + "-head-" + c, viewBox: "0 0 10 10", refX: 9, refY: 5, markerUnits: "userSpaceOnUse", markerWidth: 11, markerHeight: 11, orient: "auto" });
        m.appendChild(svgEl("path", { d: "M0 0L10 5L0 10z", "class": "ve-ex-head ve-ex-" + c }));
        defs.appendChild(m);
      });
      linksSvg.appendChild(defs);
      const sib = nodes[focus].sib || [];
      const who = hover || selected;
      for (let i = 0; i < sib.length; i++) {
        const l = sib[i];
        if (!who || (l[0] !== who && l[1] !== who)) { continue; }
        const a = tiles[l[0]] && !tiles[l[0]].classList.contains("ve-off") ? tilePx(l[0], px) : null;
        const b = tiles[l[1]] && !tiles[l[1]].classList.contains("ve-off") ? tilePx(l[1], px) : null;
        if (!a || !b) { continue; }
        linksSvg.appendChild(arrow(a, b, l[3], l[2], l[0] === who ? "out" : "in"));
      }
    }

    function renderOverlay() {
      renderLabels();
      renderLinks();
      for (const id in tiles) {
        tiles[id].classList.toggle("ve-sel", id === selected);
        tiles[id].classList.toggle("ve-hot", id === hover);
        tiles[id].setAttribute("tabindex", id === cursor && !tiles[id].classList.contains("ve-off") ? "0" : "-1");
      }
    }

    /* ---- the trail, the panel, the reader ------------------------------------------------------------------------ */
    function renderCrumbs() {
      crumbs.replaceChildren();
      const path = chain(focus);
      for (let i = 0; i < path.length; i++) {
        const li = el("li");
        const b = el("button", "ve-ex-crumb", name(path[i]));
        b.setAttribute("type", "button");
        b.setAttribute("data-go", path[i]);
        if (i === path.length - 1) { b.setAttribute("aria-current", "true"); }
        li.appendChild(b);
        crumbs.appendChild(li);
      }
      outBtn.disabled = focus === data.root;
      resetBtn.disabled = focus === data.root;
    }

    function chip(id, weight, kind) {
      const b = el("button", "ve-ex-chip");
      b.setAttribute("type", "button");
      b.setAttribute("data-go", id);
      const k = kind && data.kinds[kind] ? data.kinds[kind] : null;
      if (k) { b.className += toneClass(k.t); b.setAttribute("title", k.l + (k.d ? ": " + k.d : "")); }
      b.appendChild(el("span", "ve-ex-chip-n", name(id)));
      const extra = [];
      if (weight !== 1) { extra.push(String(weight)); }
      if (k) { extra.push(k.l); }
      if (extra.length) { b.appendChild(el("span", "ve-ex-chip-w", extra.join(" · "))); }
      return b;
    }

    function section(title) { const s = el("div", "ve-ex-sec"); s.appendChild(el("div", "ve-ex-label-h", title)); return s; }

    function renderPanel() {
      const id = selected && nodes[selected] ? selected : focus;
      const n = nodes[id];
      panel.replaceChildren();
      if (n.k) { panel.appendChild(el("p", "ve-ex-kicker", n.k)); }
      panel.appendChild(el("h4", "ve-ex-title", n.n));
      const st = n.s && data.status[n.s] ? data.status[n.s] : null;
      const meta = el("p", "ve-ex-meta");
      if (st) { const c = el("span", "ve-ex-pill" + toneClass(st.t), st.l); if (st.d) { c.setAttribute("title", st.d); } meta.appendChild(c); }
      if (n.v) {
        const total = nodes[data.root].v || 1;
        meta.appendChild(el("span", "ve-ex-size", fmt(n.v) + " " + data.unit + (id === data.root ? "" : " · " + (n.v / total * 100 >= 1 ? Math.round(n.v / total * 100) : "<1") + "% of the whole")));
      }
      panel.appendChild(meta);
      if (n.t) { panel.appendChild(el("p", "ve-ex-text", n.t)); }
      if (n.c.length) {
        const s = section("Inside");
        const list = el("div", "ve-ex-chips");
        const kids = n.c.slice().sort(function (a, b) { return nodes[b].v - nodes[a].v; });
        for (let i = 0; i < kids.length; i++) { list.appendChild(chip(kids[i], 1, "")); }
        s.appendChild(list);
        panel.appendChild(s);
      }
      if (n.out && n.out.length) {
        const s = section("Connects to");
        const list = el("div", "ve-ex-chips");
        for (let i = 0; i < n.out.length; i++) { list.appendChild(chip(n.out[i][0], n.out[i][1], n.out[i][2])); }
        s.appendChild(list);
        panel.appendChild(s);
      }
      if (n["in"] && n["in"].length) {
        const s = section("Connected from");
        const list = el("div", "ve-ex-chips");
        for (let i = 0; i < n["in"].length; i++) { list.appendChild(chip(n["in"][i][0], n["in"][i][1], n["in"][i][2])); }
        s.appendChild(list);
        panel.appendChild(s);
      }
      if (n.f && n.f.length) {
        const dl = el("dl", "ve-ex-facts");
        for (let i = 0; i < n.f.length; i++) { dl.appendChild(el("dt", "", n.f[i][0])); dl.appendChild(el("dd", "", n.f[i][1])); }
        panel.appendChild(dl);
      }
      if (n.l) {
        for (let i = 0; i < n.l.length; i++) {
          const s = section(n.l[i].t);
          const ul = el("ul", "ve-ex-list");
          for (let j = 0; j < n.l[i].i.length; j++) { ul.appendChild(el("li", "", n.l[i].i[j])); }
          s.appendChild(ul);
          panel.appendChild(s);
        }
      }
      if (n.doc && n.doc.length) {
        const s = section(n.doc.length === 1 ? "Document" : "Documents");
        for (let i = 0; i < n.doc.length; i++) {
          const b = el("button", "ve-ex-doc-btn", data.docs[n.doc[i]]);
          b.setAttribute("type", "button");
          b.setAttribute("data-doc", n.doc[i]);
          s.appendChild(b);
        }
        panel.appendChild(s);
      }
      if (n.ref && n.ref.length) {
        const s = section("In this document");
        for (let i = 0; i < n.ref.length; i++) {
          const a = el("a", "ve-ex-ref", n.ref[i][0]);
          a.setAttribute("href", n.ref[i][1]);
          s.appendChild(a);
        }
        panel.appendChild(s);
      }
    }

    function renderChrome() { renderCrumbs(); renderPanel(); }

    function openDoc(docId) {
      const src = root.querySelector('.ve-ex-docs [data-doc="' + docId + '"]');
      if (!src) { return; }
      const copy = src.cloneNode(true);
      copy.removeAttribute("id");
      readerBody.replaceChildren(copy);
      reader.hidden = false;
      root.setAttribute("data-reader", docId);
      readerOpen = true;
      const h = readerBody.querySelector(".ve-ex-doc-title");
      if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); }
    }

    function closeReader() {
      if (!readerOpen) { return; }
      reader.hidden = true;
      readerBody.replaceChildren();
      root.removeAttribute("data-reader");
      readerOpen = false;
    }

    function announce(text) { statusEl.textContent = text; }

    /* ---- hover, tooltip ------------------------------------------------------------------------------------------ */
    function hideTip() { tip.hidden = true; }

    function showTip(id, x, y) {
      const n = nodes[id];
      while (tip.firstChild) { tip.removeChild(tip.firstChild); }
      tip.appendChild(el("strong", "", n.n));
      const bits = [];
      if (n.k) { bits.push(n.k); }
      if (n.v) { bits.push(fmt(n.v) + " " + data.unit); }
      if (n.s && data.status[n.s]) { bits.push(data.status[n.s].l); }
      if (bits.length) { tip.appendChild(el("div", "", bits.join(" · "))); }
      if (n.t) { tip.appendChild(el("div", "", n.t.length > 160 ? n.t.slice(0, 157) + "…" : n.t)); }
      tip.appendChild(el("div", "ve-tip-hint", n.c.length ? "Click to zoom in" : "Click to select"));
      tip.hidden = false;
      const w = tip.offsetWidth;
      const h = tip.offsetHeight;
      let left = x + 14;
      let top = y + 14;
      if (left + w > window.innerWidth - 8) { left = Math.max(8, x - w - 14); }
      if (top + h > window.innerHeight - 8) { top = Math.max(8, y - h - 14); }
      tip.style.left = left + "px";
      tip.style.top = top + "px";
    }

    function clearHover() {
      if (hover === null) { return; }
      hover = null;
      for (const id in tiles) { tiles[id].classList.remove("ve-hot"); }
      linksSvg.replaceChildren();
    }

    function tileOf(target) {
      const t = target && target.closest ? target.closest(".ve-n") : null;
      return t && !t.classList.contains("ve-off") && world.contains(t) ? t.getAttribute("data-id") : null;
    }

    function onOver(e) {
      if (moving) { return; }
      const id = tileOf(e.target);
      if (!id) { return; }
      if (hover !== id) {
        hover = id;
        for (const k in tiles) { tiles[k].classList.toggle("ve-hot", k === id); }
        renderLinks();
      }
      showTip(id, e.clientX, e.clientY);
    }

    function onMove(e) {
      if (moving || hover === null || tip.hidden) { return; }
      const w = tip.offsetWidth;
      const h = tip.offsetHeight;
      let left = e.clientX + 14;
      let top = e.clientY + 14;
      if (left + w > window.innerWidth - 8) { left = Math.max(8, e.clientX - w - 14); }
      if (top + h > window.innerHeight - 8) { top = Math.max(8, e.clientY - h - 14); }
      tip.style.left = left + "px";
      tip.style.top = top + "px";
    }

    function onOut(e) {
      const to = e.relatedTarget;
      if (to && tileOf(to) === hover) { return; }
      if (!tileOf(e.target)) { return; }
      clearHover();
      hideTip();
      if (selected) { renderLinks(); }
    }

    /* ---- activation and keyboard -------------------------------------------------------------------------------- */
    function activate(id) {
      if (moving) { return; }
      cursor = id;
      if (nodes[id].c.length) { selected = id; go(id); } else { reveal(id); }
    }

    function onClick(e) {
      const t = e.target;
      if (!t || !t.closest) { return; }
      const go_ = t.closest("[data-go]");
      if (go_ && root.contains(go_)) { e.preventDefault(); const id = go_.getAttribute("data-go"); selected = null; go(id); return; }
      const docBtn = t.closest("[data-doc].ve-ex-doc-btn");
      if (docBtn) { openDoc(docBtn.getAttribute("data-doc")); return; }
      const act = t.closest("[data-act]");
      if (act) {
        const what = act.getAttribute("data-act");
        if (what === "out") { selected = null; up(); } else if (what === "reset") { selected = null; go(data.root); } else if (what === "close-doc") { closeReader(); }
        return;
      }
      const id = tileOf(t);
      if (id) { activate(id); }
    }

    function neighbour(from, dir) {
      const px = stagePx();
      const a = tilePx(from, px);
      const ax = a.x + a.w / 2;
      const ay = a.y + a.h / 2;
      let best = null;
      let bestScore = Infinity;
      const kids = childrenOf(focus);
      for (let i = 0; i < kids.length; i++) {
        if (kids[i] === from) { continue; }
        const b = tilePx(kids[i], px);
        const dx = b.x + b.w / 2 - ax;
        const dy = b.y + b.h / 2 - ay;
        const along = dir === "ArrowRight" ? dx : dir === "ArrowLeft" ? -dx : dir === "ArrowDown" ? dy : -dy;
        const across = dir === "ArrowRight" || dir === "ArrowLeft" ? Math.abs(dy) : Math.abs(dx);
        if (along <= 1) { continue; }
        const score = along + across * 1.6;
        if (score < bestScore) { bestScore = score; best = kids[i]; }
      }
      return best;
    }

    function focusTile(id) {
      cursor = id;
      for (const k in tiles) { tiles[k].setAttribute("tabindex", k === id ? "0" : "-1"); }
      if (tiles[id]) { tiles[id].focus({ preventScroll: true }); }
    }

    function onKey(e) {
      if (e.key === "Escape") {
        if (readerOpen) { closeReader(); e.preventDefault(); return; }
        if (focus !== data.root && root.contains(doc.activeElement)) { selected = null; up(); e.preventDefault(); }
        return;
      }
      if (e.target === stage && !moving && cursor && (e.key === "Enter" || e.key === " " || e.key.indexOf("Arrow") === 0)) { e.preventDefault(); focusTile(cursor); return; }
      const id = tileOf(e.target);
      if (!id || moving) { return; }
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activate(id); return; }
      if (e.key === "Backspace") { e.preventDefault(); selected = null; up(); return; }
      if (e.key === "Home") { e.preventDefault(); selected = null; go(data.root); return; }
      if (e.key.indexOf("Arrow") === 0) {
        e.preventDefault();
        const next = neighbour(id, e.key);
        if (next) { focusTile(next); const n = nodes[next]; announce(n.n + (n.v ? ", " + fmt(n.v) + " " + data.unit : "")); }
      }
    }

    function onFocusIn(e) {
      const id = tileOf(e.target);
      if (!id || moving) { return; }
      cursor = id;
      if (hover !== id) { hover = id; for (const k in tiles) { tiles[k].classList.toggle("ve-hot", k === id); } renderLinks(); }
    }

    function onFocusOut(e) {
      if (tileOf(e.target) && hover === tileOf(e.target)) { clearHover(); if (selected) { renderLinks(); } }
    }

    /* ---- start --------------------------------------------------------------------------------------------------- */
    root.setAttribute("data-ve-js", "1");
    showTiles(childrenOf(focus));
    setCamera(rectOf(focus));
    cursor = childrenOf(focus)[0] || null;
    root.setAttribute("data-settled", "1");
    renderChrome();
    renderOverlay();
    root.addEventListener("click", onClick);
    root.addEventListener("keydown", onKey);
    root.addEventListener("focusin", onFocusIn);
    root.addEventListener("focusout", onFocusOut);
    world.addEventListener("pointerover", onOver);
    world.addEventListener("pointermove", onMove);
    world.addEventListener("pointerout", onOut);
    if (typeof ResizeObserver !== "undefined") {
      let pending = 0;
      new ResizeObserver(function () {
        if (moving) { return; }
        cancelAnimationFrame(pending);
        pending = requestAnimationFrame(renderOverlay);
      }).observe(stage);
    }
    window.addEventListener("scroll", hideTip, { passive: true });

    const api = { id: data.id, go: go, up: up, state: function () { return { focus: focus, selected: selected, moving: moving, camera: { x: cam.x, y: cam.y, w: cam.w, h: cam.h } }; } };
    window.__veExplorers[data.id] = api;
    return api;
  }

  function init() {
    const roots = doc.querySelectorAll("[data-ve-explorer]");
    for (let i = 0; i < roots.length; i++) { Explorer(roots[i]); }
  }

  if (doc.readyState === "loading") { doc.addEventListener("DOMContentLoaded", init); } else { init(); }
}());
