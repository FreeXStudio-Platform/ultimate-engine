/**
 * Figure layer — makes a rendered chart safe to inline next to other charts, and makes every mark answer.
 *
 * WHY THIS EXISTS (measured 2026-10-10 on a 28-chart report; see docs/process/OPEN_GATES.md OG-250…):
 *
 *   1. ECharts' SSR output embeds a `<style>` block of `.zr-cls-N:hover{fill:…}` rules, and `normalizeSVG()`
 *      renumbers the class names from 0 in EVERY chart so that each file is byte-stable. Inlined into one HTML
 *      page, 28 charts therefore shared the same 8 class names with 28 different bodies; the cascade picked one
 *      winner for all of them. That produced the "green goes black / blue flashes / blank tiles" hover, filled
 *      graph edges (a lens-shaped blue region between two points of an open curve), and `:hover{pointer-events:none}`
 *      rules that made a hovered mark un-hoverable and so flicker.
 *   2. ECharts computes the hover colour by lightening the mark's `fill`; with the document theme the fill is
 *      `var(--fg)` / `var(--mute)`, which it cannot parse, so the "lifted" colour came out black or white.
 *   3. Clip-path and gradient ids (`zr-c0`, `zr-g0`) were the same in every chart, so `url(#zr-g0)` in a sankey
 *      resolved to the heat-map's gradient earlier in the document.
 *   4. Labels sat above their shapes and took the pointer, so moving across a tile alternated between shape and
 *      text hover — flicker, and a blank tile when the text's hover rule won.
 *   5. Nothing told the reader WHAT a dot was: the SVG had no title, no tooltip, no adjacency.
 *
 * WHAT IT DOES (one pass over the finished SVG string, deterministic):
 *   - removes ECharts' CSS and class names entirely (it owns no part of the hover design any more);
 *   - scopes every `id`/`url(#…)`/`href="#…"` to the figure (`<figure-id>-c0`), so ids are document-unique;
 *   - renames the `ecmeta_*` attributes to `data-*`, adds `data-id` / `data-nb` / `data-en` from the figure model;
 *   - writes a `<title>` into every mark (native tooltip, screen-reader name, no-JS fallback);
 *   - emits ONE scoped `<style>`: outline-and-brighten hover that never recolours, open paths never fill,
 *     text never intercepts the pointer, and — with `:has()` — adjacency / series / legend focus that works
 *     with no script at all. docgen's figure runtime upgrades the same attributes to rich tooltips and pinning.
 *
 * Law (docs/design/FIGURE_SYSTEM.md §4): a hover state may change brightness, outline, thickness and opacity.
 * It may never change a mark's hue, never fill an open path, never move a mark, never take the pointer from it.
 */

import { parseColor } from "./contrast.mjs";

/**
 * A stroke that is a COLOUR of its own — a line symbol's ring, a box-plot outline, a bubble's rim — as opposed to a
 * separator (the white seam between pie slices, a grey hairline). On hover a separator may be replaced by an ink
 * outline; a coloured stroke must keep its colour, or a blue point turns black when you touch it (`OG-269`).
 */
export function isOwnStroke(stroke) {
  const rgb = parseColor(stroke);
  if (!rgb) return false;
  return Math.max(...rgb) - Math.min(...rgb) >= 46; // chroma of about 0.18 of full scale: greys and white are separators
}

const esc = (s) => String(s ?? "")
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** Prefix every id declared in the SVG, and every reference to one. Idempotent for a given scope. */
export function scopeSvgIds(svg, scope) {
  return svg.replace(/(\bid="|url\(#|href="#)zr-/g, `$1${scope}-`);
}

const MARK_TAG = /<(path|rect|polyline|polygon|circle|ellipse|line)\b([^>]*\bdata-(?:s|t)="[^>]*)>/g;

function attr(attrs, name) {
  const m = new RegExp(`\\b${name}="([^"]*)"`).exec(attrs);
  return m ? m[1] : undefined;
}

function centreOf(attrs) {
  const t = attr(attrs, "transform");
  if (!t) return null;
  let m = /^translate\(\s*(-?[\d.]+)[ ,]+(-?[\d.]+)\s*\)$/.exec(t);
  if (m) return [Number(m[1]), Number(m[2])];
  m = /^matrix\(([^)]*)\)$/.exec(t);
  if (m) { const v = m[1].split(/[ ,]+/).map(Number); if (v.length === 6) return [v[4], v[5]]; }
  return null;
}

function endPoint(d) {
  const nums = (d ?? "").match(/-?\d*\.?\d+(?:e-?\d+)?/gi);
  if (!nums || nums.length < 2) return null;
  return [Number(nums[nums.length - 2]), Number(nums[nums.length - 1])];
}

/**
 * Delete every <style> block. Repeated to a fixed point: removing one block can splice the text around it into
 * another (`<sty<style>x</style>le>y</style>` becomes `<style>y</style>` after one pass), so one pass is not enough.
 */
export function stripStyleBlocks(svg) {
  let out = svg;
  for (let before = ""; before !== out; ) {
    before = out;
    out = out.replace(/<style\b[^>]*>[\s\S]*?<\/style>/g, "");
  }
  return out;
}

/**
 * Rewrite one chart's SVG. `model` comes from figure-model.mjs; `fid` is the figure scope (unique per document).
 * Returns the decorated SVG string.
 */
export function decorateSvg(svg, { fid, model, ink, ground, faint }) {
  let out = svg;
  // 1. ECharts' own CSS and class names: gone. Nothing below depends on them.
  out = stripStyleBlocks(out);
  out = out.replace(/\sclass="zr-cls-\d+"/g, "");
  // 2. Document-unique ids.
  out = scopeSvgIds(out, fid);
  // 3. Meta attributes → data-*.
  out = out
    .replace(/\secmeta_series_index=/g, " data-s=")
    .replace(/\secmeta_data_index=/g, " data-i=")
    .replace(/\secmeta_ssr_type=/g, " data-t=")
    .replace(/\secmeta_data_type=/g, " data-k=")
    .replace(/\secmeta_silent="true"/g, "");

  // 4. Tree edges carry no ECharts data at all: pair each curve with its child node by geometry.
  const nodeCentres = [];
  if (model.kind === "tree") {
    for (const m of out.matchAll(MARK_TAG)) {
      if (attr(m[2], "data-k") === "main") {
        const c = centreOf(m[2]);
        if (c) nodeCentres.push({ c, key: `${attr(m[2], "data-s")}|main|${attr(m[2], "data-i")}` });
      }
    }
  }
  const nearestNode = (pt) => {
    let best = null;
    for (const n of nodeCentres) {
      const d = Math.hypot(n.c[0] - pt[0], n.c[1] - pt[1]);
      if (d < 2.5 && (!best || d < best.d)) best = { d, key: n.key };
    }
    return best?.key ?? null;
  };

  // 5. Per-mark attributes and <title>.
  const radarCount = new Map();
  out = out.replace(MARK_TAG, (whole, tag, rawAttrs) => {
    // Tolerate `<path .../>`: a <title> must sit INSIDE the element, so open it up first.
    const selfClosed = rawAttrs.endsWith("/");
    const attrs = selfClosed ? rawAttrs.slice(0, -1) : rawAttrs;
    const close = selfClosed ? `</${tag}>` : "";
    const t = attr(attrs, "data-t");
    const k = attr(attrs, "data-k");
    const s = attr(attrs, "data-s");
    const i = attr(attrs, "data-i");
    let extra = "";
    let title = "";
    if (t === "legend") {
      const label = model.legendMode === "series" ? model.series[Number(i)]?.name : model.items.filter((x) => x.kind === "slice" || x.kind === "series")[Number(i)]?.label;
      if (label) title = label;
      return `<${tag}${attrs}>${title ? `<title>${esc(title)}</title>` : ""}${close}`;
    }
    if (k === "series") {
      const name = model.series[Number(s)]?.name;
      if (name) title = name;
      return `<${tag}${attrs}${extra}>${title ? `<title>${esc(title)}</title>` : ""}${close}`;
    }
    if (k === "tedge") {
      // the curve is drawn in its own translated frame: add the translation before comparing with node centres
      const end = endPoint(attr(attrs, "d")) ?? [NaN, NaN];
      const shift = centreOf(attrs) ?? [0, 0];
      const key = nearestNode([end[0] + shift[0], end[1] + shift[1]]);
      const child = key ? model.byKey.get(key) : null;
      if (child) {
        extra += ` data-s="${child.series}" data-k="edge" data-id="e${child.index}" data-en="${child.parent ? `${child.parent} ` : ""}${child.id}"`;
        title = `${child.parent ? `${model.items.find((x) => x.id === child.parent)?.label} → ` : ""}${child.label}`;
        return `<${tag}${attrs.replace(/\sdata-k="tedge"/, "")}${extra}>${title ? `<title>${esc(title)}</title>` : ""}${close}`;
      }
      return `<${tag}${attrs.replace(/\sdata-k="tedge"/, "")}>${close}`;
    }
    const item = model.byKey.get(`${s}|${k ?? "undefined"}|${i}`);
    if (!item) return `<${tag}${attrs}${extra}>${close}`;
    extra += ` data-id="${esc(item.id)}"`;
    if (isOwnStroke(attr(attrs, "stroke"))) extra += ' data-sk="own"';
    if (item.kind === "node" && model.kind === "tree") {
      const kin = [...(item.ancestors ?? []), ...model.items.filter((x) => (x.ancestors ?? []).includes(item.id)).map((x) => x.id)];
      extra += ` data-nb="${kin.join(" ")}"`;
      // an edge belongs to this node's kin when both of its ends are in {self, kin}
      extra += ` data-eg="${model.items.filter((x) => x.kind === "node" && x.parent && (x.id === item.id || kin.includes(x.id)) && (x.parent === item.id || kin.includes(x.parent))).map((x) => `e${x.index}`).join(" ")}"`;
    } else if (item.kind === "node" && item.neighbors) {
      extra += ` data-nb="${item.neighbors.join(" ")}" data-eg="${item.edges.join(" ")}"`;
    } else if (item.kind === "edge") {
      extra += ` data-en="${item.ends.join(" ")}"`;
    }
    let tip = item.tip;
    if (item.kind === "series" && Array.isArray(item.axes) && tag !== "polyline") {
      const n = radarCount.get(item.id) ?? 0;
      radarCount.set(item.id, n + 1);
      const ax = item.axes[n];
      if (ax) tip = [item.label, `${ax.axis}: ${ax.value}`];
    }
    title = tip.join("\n");
    return `<${tag}${attrs}${extra}>${title ? `<title>${esc(title)}</title>` : ""}${close}`;
  });

  // 6. Root element: scope + kind. `tabindex` is added by the runtime, never baked in (a static SVG
  //    with hundreds of tab stops is an accessibility regression, not a feature).
  out = out.replace(/<svg /, `<svg data-fig="${esc(fid)}" data-fig-kind="${esc(model.kind)}" data-fig-focus="${esc(model.focus)}" data-fig-legend="${esc(model.legendMode)}" class="ve-fig" `);
  const css = figureCss(fid, model, { ink, ground, faint });
  out = out.replace(/(<svg [^>]*>)/, `$1<style data-ve="${esc(fid)}"><![CDATA[${css}]]></style>`);
  return out;
}

/** Paint a lit edge in a direction colour: the line takes it as a stroke, its arrowhead (a filled shape) as a fill. */
function directionRules(selector, dir) {
  return [
    `${selector}[fill="none"]{stroke:var(--ve-${dir});stroke-opacity:1}`,
    `${selector}:not([fill="none"]){fill:var(--ve-${dir});fill-opacity:1}`,
  ];
}

/**
 * The scoped stylesheet. Every selector starts with `svg[data-fig="<id>"]`, so nothing here can touch another
 * figure — and nothing another figure ships can touch this one.
 */
export function figureCss(fid, model, { ink = "currentColor", faint = "rgba(128,128,128,.28)" } = {}) {
  const S = `svg[data-fig="${fid}"]`;
  const NOJS = `${S}:not([data-ve-js])`;
  const mark = '[data-s]:not([data-k="series"]):not([data-k="edge"])';
  const r = [];
  r.push(`/* ve-fig v1 · scoped to ${fid} · never recolours, never fills an open path, never steals the pointer */`);
  // Labels never take the pointer (they sit on top of the shapes) and never carry a halo.
  r.push(`${S} text,${S} tspan{pointer-events:none;stroke:none}`);
  r.push(`${S} [data-s],${S} [data-t="legend"][fill="none"]{cursor:pointer}`);
  r.push(`${S} [data-s]{transition:opacity .14s ease,filter .14s ease,stroke-width .14s ease}`);
  r.push(`@media (prefers-reduced-motion:reduce){${S} [data-s]{transition:none}}`);
  // Filled marks: outline + brighten. Same hue, so it reads as "this one", on any theme.
  // `vector-effect:non-scaling-stroke`: symbols are drawn in unit space and scaled 4-48x by a transform, so a
  // plain `stroke-width:1.6` would become a 38px ring on a large node. This keeps the outline at 1.6 screen px.
  const filled = `${mark}:not([fill="none"])`;
  r.push(`${S} ${filled}:not([data-sk="own"]):hover,${S} ${filled}:not([data-sk="own"]):focus-visible{stroke:${ink};stroke-width:1.6px;vector-effect:non-scaling-stroke;stroke-opacity:.95;filter:brightness(1.16) saturate(1.1);outline:none}`);
  // A filled mark that draws a stroke in its OWN colour (a line symbol's ring, a box-plot outline) keeps that colour:
  // it thickens and brightens, it is never repainted ink (`OG-269`: a hovered blue point turned black).
  r.push(`${S} ${filled}[data-sk="own"]:hover,${S} ${filled}[data-sk="own"]:focus-visible{stroke-width:2.6px;vector-effect:non-scaling-stroke;stroke-opacity:1;filter:brightness(1.12) saturate(1.15);outline:none}`);
  // Open paths (edges, lines, radar outlines): thicken, never fill — the lens-shaped fill was this rule's absence.
  r.push(`${S} [data-s][fill="none"]:hover,${S} [data-s][fill="none"]:focus-visible{fill:none;stroke-width:3.4px;vector-effect:non-scaling-stroke;stroke-opacity:1;filter:none;outline:none}`);
  r.push(`${S} [data-s][fill="none"]{pointer-events:visibleStroke}`);
  // The hit area of a thin line is its stroke; widen it without changing how it looks.
  // Legend entry: tint its hit area, never its text.
  r.push(`${S} [data-t="legend"][fill="none"]:hover{fill:${faint};fill-opacity:.55}`);

  const dim = (sel, o = 0.2) => `${sel}{opacity:${o}}`;
  if (model.focus === "item") {
    // Tiles, arcs and cells carry their label ON TOP as a separate element that does not dim with them, so a hard fade
    // leaves ink on a vanished fill. Those families fade gently; bars, dots and slices (no inside label) fade hard.
    const labelled = ["treemap", "sunburst", "heatmap", "matrix", "funnel"].includes(model.kind);
    r.push(dim(`${NOJS}:has(${mark}:hover) ${mark}:not(:hover)`, labelled ? 0.7 : 0.42));
  } else if (model.focus === "index") {
    const n = model.items.length;
    for (let i = 0; i < n; i += 1) r.push(dim(`${NOJS}:has([data-s][data-i="${i}"]:hover) [data-s]:not([data-i="${i}"])`, 0.22));
  } else if (model.focus === "series") {
    for (const s of model.series) {
      r.push(dim(`${NOJS}:has([data-s="${s.index}"]:hover) [data-s]:not([data-s="${s.index}"])`, 0.22));
    }
  } else if (model.focus === "adjacency") {
    const nodes = model.items.filter((x) => x.kind === "node");
    const edges = model.items.filter((x) => x.kind === "edge" || (model.kind === "tree" && x.kind === "node" && x.parent));
    // CSS-only adjacency needs one rule per node/edge: fine for the diagrams people read, wasteful for 1,000
    // nodes — those rely on the runtime (which does it generically) and drop the no-script fallback.
    if (nodes.length + edges.length <= 160) {
      const litSel = (ids) => `:is(${ids.map((i) => `[data-id="${i}"]`).join(",")})`;
      const rule = (hover, lit, litEdges) => {
        r.push(dim(`${hover} :is([data-k="node"],[data-k="main"]):not(${litSel(lit)})`, 0.3));
        r.push(dim(`${hover} [data-k="edge"]:not(${litSel(lit)})`, 0.1));
        if (litEdges.length) r.push(`${hover} ${litSel(litEdges)}[data-k="edge"]{stroke-opacity:1;stroke-width:3px;vector-effect:non-scaling-stroke;opacity:1}`);
      };
      for (const n of nodes) {
        const nb = model.kind === "tree" ? (n.ancestors ?? []).concat(nodes.filter((x) => (x.ancestors ?? []).includes(n.id)).map((x) => x.id)) : n.neighbors;
        const eg = model.kind === "tree"
          ? nodes.filter((x) => x.parent && (x.id === n.id || nb.includes(x.id)) && (x.parent === n.id || nb.includes(x.parent))).map((x) => `e${x.index}`)
          : n.edges;
        const hover = `${NOJS}:is(:has([data-k="node"][data-id="${n.id}"]:hover),:has([data-k="main"][data-id="${n.id}"]:hover))`;
        rule(hover, [n.id, ...nb, ...eg], eg);
        // Direction (graphs only): the lines that leave the hovered node, enter it, or run both ways take the direction colours.
        if (model.kind === "graph") {
          for (const [dir, ids] of [["out", n.outEdges], ["in", n.inEdges], ["both", n.bothEdges]]) {
            if (ids?.length) r.push(...directionRules(`${hover} ${litSel(ids)}`, dir));
          }
        }
      }
      for (const e of edges) {
        const id = e.kind === "edge" ? e.id : `e${e.index}`;
        const ends = e.kind === "edge" ? e.ends : [e.parent, e.id];
        rule(`${NOJS}:has([data-k="edge"][data-id="${id}"]:hover)`, [id, ...ends], [id]);
      }
    }
  }
  // Legend focus (series legends isolate a series; pie/funnel legends isolate a data item).
  if (model.legendMode === "series") {
    for (const s of model.series) {
      r.push(dim(`${NOJS}:has([data-t="legend"][fill="none"][data-i="${s.index}"]:hover) [data-s]:not([data-s="${s.index}"])`, 0.18));
    }
  } else if (model.legendMode === "item") {
    const n = model.items.filter((x) => x.kind === "slice" || x.kind === "series").length;
    for (let i = 0; i < n; i += 1) {
      r.push(dim(`${NOJS}:has([data-t="legend"][fill="none"][data-i="${i}"]:hover) [data-s]:not([data-i="${i}"])`, 0.2));
    }
  }
  // Runtime-driven focus (set by docgen's figure runtime): same look, any size of graph.
  r.push(`${S}[data-ve-js][data-ve-on] [data-s]:not(.ve-on):not([data-t="legend"]){opacity:.2}`);
  r.push(`${S}[data-ve-js] [data-s].ve-on[data-k="edge"]{stroke-opacity:1;stroke-width:3px;vector-effect:non-scaling-stroke}`);
  r.push(`${S}[data-ve-js] [data-s].ve-on[data-k="edge"]:not([fill="none"]){fill-opacity:1}`); // an arrowhead is a filled shape
  if (model.kind === "graph") {
    // The direction palette. Law (docs/design/FIGURE_SYSTEM.md section 4): a hover state never changes a mark's hue --
    // with ONE declared exception, because here the hue IS the information: while a node is focused, the lines leaving it
    // are blue, the lines entering it pink and a two-way link white, and the figure's reading guide says so. Cyan and pink
    // are not any module's conformance colour, so a lit line can never be mistaken for a status.
    r.push(`${S}{--ve-out:#4CC9F0;--ve-in:#F58AC0;--ve-both:#FFFFFF}`);
    // `:is([data-theme="light"] *)` says "this figure sits inside a light page" while the selector still STARTS with the figure.
    r.push(`${S}:is([data-theme="light"] *){--ve-out:#0A7AA1;--ve-in:#B8337D;--ve-both:#0B0E14}`);
    for (const dir of ["out", "in", "both"]) r.push(...directionRules(`${S}[data-ve-js] [data-s].ve-${dir}[data-k="edge"]`, dir));
  }
  r.push(`${S} .ve-pin:not([fill="none"]):not([data-sk="own"]){stroke:${ink};stroke-width:2.2px;vector-effect:non-scaling-stroke;stroke-opacity:1}`);
  r.push(`${S} .ve-pin[data-sk="own"]{stroke-width:3.2px;vector-effect:non-scaling-stroke;stroke-opacity:1;filter:brightness(1.12) saturate(1.15)}`);
  r.push(`${S} .ve-pin[fill="none"]{stroke-width:3.8px;vector-effect:non-scaling-stroke;stroke-opacity:1}`);
  return r.join("\n");
}
