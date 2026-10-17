/**
 * Normalized visual job → ECharts option.
 *
 * The AI agent supplies a compact job packet (schemas/visual-job.schema.json);
 * this module owns ALL renderer syntax. Agents never hand-write ECharts
 * options for routine work (token-efficiency rule §32).
 *
 * Determinism: no Date.now, no Math.random, no force layouts. Graph presets
 * use circular/preset layouts so output is byte-stable for the regression
 * suite.
 */
import { VisualJobError } from "./validate.mjs";
import { inkFor, mix, parseColor, rampAt } from "./contrast.mjs";
import { semanticPalette } from "./semantic-colors.mjs";

// Theme-derived values. Literal hex in a dark/light/print theme, CSS variables in "document-theme" (an SVG inlined
// into a docgen page follows that page's live theme). Nothing here invents a colour: it all comes from the theme.
const groundOf = (theme) => (theme?._mode === "document" ? "var(--bg)" : theme?.semantic?.grounds?.night ?? "#060608");
const inkOf = (theme) => theme?.semantic?.inks?.bone ?? "currentColor";
const mutedOf = (theme) => theme?.semantic?.inks?.ash ?? "#8A96AE";
/** The theme's display face (titles, tile names): Space Grotesk in the Atlas, undefined where a theme names none. */
const displayFont = (theme) => theme?.title?.textStyle?.fontFamily;
const paletteOf = (theme) => (Array.isArray(theme?.color) && theme.color.length ? theme.color : ["#4A7FC1", "#C98A4B", "#EDB84A", "#3DA875", "#E2683A", "#1E3A6E"]);
/**
 * Word-wrap a subtitle to the chart width. ECharts never wraps `subtext`, so a 120-character provenance line simply ran
 * off the right edge of the SVG ("…dots overlap where v"). ~6.3px per 12px character is the measured average.
 */
function wrapSubtitle(text, width) {
  const max = Math.max(24, Math.floor(((width ?? 640) - 24) / 6.3));
  const lines = [];
  let cur = "";
  for (const word of String(text).split(/\s+/)) {
    if (cur && (cur + " " + word).length > max) { lines.push(cur); cur = word; } else { cur = cur ? `${cur} ${word}` : word; }
  }
  if (cur) lines.push(cur);
  return lines.join("\n");
}
const subLines = (job) => (job.subtitle ? wrapSubtitle(job.subtitle, job.width).split("\n").length : 0);
/** Room for the title (and subtitle) above a series that has no grid of its own. */
const titleTop = (job) => (job.title ? 28 + subLines(job) * 16 + 14 : 10);
/** ECharts draws every label with a 2px contrasting outline by default: on a dark ground that is a white fringe. Off. */
const NOHALO = { textBorderWidth: 0, textShadowBlur: 0 };

/** `#rrggbb` or `rgb(...)` with an alpha, as `rgba(...)` (ECharts gradient stops take no separate opacity). */
function withAlpha(color, alpha) {
  const rgb = parseColor(color);
  return rgb ? `rgba(${Math.round(rgb[0])},${Math.round(rgb[1])},${Math.round(rgb[2])},${alpha})` : color;
}

/** Give a hierarchy explicit colours and the ink that reads on each: top level from the palette, deeper levels lighter. */
function colorizeTree(nodes, palette, depth = 0, base = null) {
  return (nodes ?? []).map((n, i) => {
    const color = depth === 0 ? palette[i % palette.length] : mix(base, "#ffffff", Math.min(0.5, 0.13 * depth));
    const ink = inkFor(color);
    const out = { ...n, itemStyle: { ...(n.itemStyle ?? {}), color } };
    if (ink) out.label = { ...(n.label ?? {}), color: ink }; // parent strips sit on the ground, not on the tile: see treemap()
    if (Array.isArray(n.children)) out.children = colorizeTree(n.children, palette, depth + 1, depth === 0 ? color : base);
    return out;
  });
}

const GRID = { left: 56, right: 24, top: 48, bottom: 40, containLabel: true };

function titleBlock(job) {
  const t = { left: 8, top: 6 };
  if (job.title) t.text = job.title;
  if (job.subtitle) t.subtext = wrapSubtitle(job.subtitle, job.width);
  return job.title || job.subtitle ? { title: t } : {};
}

function datasetOf(job) {
  const { dimensions, source } = job.data;
  if (!Array.isArray(dimensions) || !Array.isArray(source)) {
    throw new VisualJobError("G-STRUCT", `visual "${job.selected_visual}" needs data.dimensions + data.source (table shape)`);
  }

  // ECharts treats a first row of all-strings as a HEADER and silently drops it. A row like
  // ["critical", "12"] — a perfectly ordinary result of a CSV read or a JSON API that quotes its
  // numbers — therefore vanished from the chart, which then rendered normally and wrongly. Refuse
  // rather than guess: the engine cannot know whether the author meant a header or a data row, and
  // a chart that silently omits a category is worse than one that fails to build (T-R9).
  if (source.length > 0 && Array.isArray(source[0]) && source[0].length > 1
      && source[0].every((cell) => typeof cell === "string")) {
    throw new VisualJobError(
      "G-STRUCT",
      `data.source[0] is all strings (${JSON.stringify(source[0])}). ECharts would treat it as a ` +
      `header row and DELETE it from the chart. If it is data, coerce the measure columns to ` +
      `numbers; if it is a header, remove it — data.dimensions already names the columns.`,
    );
  }

  // Duplicate CATEGORY labels collapse onto one axis position and the bars are drawn on top of one
  // another, so three runs scoring 10, 30 and 5 render as a single bar reading 30. Data disappearing
  // behind other data is the worst failure a chart can have, because it looks entirely normal.
  //
  // Scoped to a CATEGORICAL first column on purpose. The first version applied this to every family
  // and broke the scatter golden immediately: on a scatter plot the first column is an X VALUE, and
  // repeated x-values are ordinary data, not a collision. A guard that is right for one chart family
  // and wrong for another is not a guard — it is a false red, and a false red trains people to
  // bypass the gate. The engine's own regression suite caught it in the same run.
  const firstColumnIsCategorical =
    source.length > 1 && Array.isArray(source[0]) &&
    source.every((row) => !Array.isArray(row) || row.length === 0 ||
                          (typeof row[0] === "string" && !Number.isFinite(Number(row[0]))));
  if (firstColumnIsCategorical) {
    const seen = new Map();
    const dupes = [];
    for (const row of source) {
      if (!Array.isArray(row) || row.length === 0) continue;
      const key = String(row[0]);
      if (seen.has(key)) { if (!dupes.includes(key)) dupes.push(key); }
      else seen.set(key, true);
    }
    if (dupes.length > 0) {
      throw new VisualJobError(
        "G-STRUCT",
        `data.source has duplicate category labels in the first column: ` +
        `${JSON.stringify(dupes.slice(0, 5))}. They would collapse onto one axis position and the ` +
        `values would be drawn on top of each other, silently. Aggregate them, or make the labels ` +
        `distinct.`,
      );
    }
  }
  return { dataset: { dimensions, source } };
}

/**
 * Build one series per measure column, each with an EXPLICIT encode.
 *
 * Never rely on ECharts' implicit dataset dimension-to-axis inference — with
 * multiple series sharing one dataset it is order/name-sensitive, silently
 * mis-binds category/time axes (a `time` axis with no encode was seen
 * defaulting to nonsense tick values instead of the actual date column), and
 * its fallback resolution path is a measurable source of cross-platform
 * floating-point drift (macOS arm64 vs Linux x64 CI produced different bytes
 * for the identical job — caught by the golden-regression gate, 2026-08-10).
 * `orientation: "horizontal"` swaps the encode for bar_horizontal's category
 * y-axis; each series gets its OWN x per its OWN measure, never one shared
 * encode across every series (the bar_horizontal bug this replaces).
 */
/**
 * A category axis that never silently drops its labels. ECharts' default (`interval: "auto"`) hides every label that would overlap
 * its neighbour, so a stacked bar of twelve areas drew three names under twelve bars and nothing said so. When every name fits its
 * slot the axis is unchanged in appearance (`interval: 0` only guarantees what auto already did); when one does not, the labels are
 * tilted and the very long ones are cut with an ellipsis (the tooltip and the mark table carry the full name). A long series
 * (more than 24 categories, a time series) keeps the thinned default: showing 60 dates is not reading.
 */
function categoryAxisFit(job, extra = {}, orientation = "vertical") {
  const cats = (job.data?.source ?? []).map((r) => String(r?.[0] ?? ""));
  const base = { type: "category", ...extra };
  if (cats.length === 0 || cats.length > 24) return base;
  const span = orientation === "horizontal" ? (job.height ?? 480) - GRID.top - GRID.bottom : (job.width ?? 640) - GRID.left - GRID.right;
  const slot = span / cats.length;
  const widest = Math.max(...cats.map((c) => textWidthPx(c, 11)));
  if (orientation === "horizontal") {
    return { ...base, axisLabel: { interval: 0, width: 150, overflow: "truncate" } };
  }
  if (widest + 8 <= slot) return { ...base, axisLabel: { interval: 0 } };
  return { ...base, axisLabel: { interval: 0, rotate: 40, width: 130, overflow: "truncate", hideOverlap: false } };
}

function seriesForTable(job, type, { orientation = "vertical", ...extra } = {}) {
  const dims = job.data.dimensions;
  const measures = dims.slice(1);
  return measures.map((name) => ({
    type,
    name,
    encode: orientation === "horizontal" ? { y: dims[0], x: name } : { x: dims[0], y: name },
    ...extra,
  }));
}

/** Named dots: label only the largest few (a label on every one of 100 dots is noise), name ALL of them in the tooltip. */
function pointLabels(job, theme, weight) {
  const names = Array.isArray(job.data?.names) ? job.data.names : null;
  if (!names) return {};
  const top = new Set(names.map((_, i) => i).sort((a, b) => weight(b) - weight(a)).slice(0, 8));
  return {
    label: { show: true, position: "top", fontSize: 10, color: inkOf(theme), ...NOHALO, formatter: (p) => (top.has(p.dataIndex) ? names[p.dataIndex] : "") },
    labelLayout: { hideOverlap: true },
  };
}

const BUILDERS = {
  bar(job) {
    return { ...datasetOf(job), ...titleBlock(job), grid: GRID, legend: legend(job),
      xAxis: categoryAxisFit(job), yAxis: valueAxis(job),
      series: seriesForTable(job, "bar", job.stack ? { stack: "total" } : {}) };
  },
  bar_grouped(job) { return BUILDERS.bar(job); },
  bar_stacked(job) { return BUILDERS.bar({ ...job, stack: true }); },
  bar_horizontal(job) {
    return { ...datasetOf(job), ...titleBlock(job), grid: GRID, legend: legend(job),
      yAxis: categoryAxisFit(job, { inverse: true }, "horizontal"), xAxis: valueAxis(job),
      series: seriesForTable(job, "bar", { orientation: "horizontal", ...(job.stack ? { stack: "total" } : {}) }) };
  },
  line(job) {
    return { ...datasetOf(job), ...titleBlock(job), grid: GRID, legend: legend(job),
      xAxis: job.time_axis ? { type: "time", boundaryGap: false } : categoryAxisFit(job, { boundaryGap: false }), yAxis: valueAxis(job),
      series: seriesForTable(job, "line") };
  },
  line_step(job) {
    const o = BUILDERS.line(job); o.series.forEach((s) => (s.step = "end")); return o;
  },
  area(job) {
    const o = BUILDERS.line(job); o.series.forEach((s) => (s.areaStyle = { opacity: 0.3 })); return o;
  },
  area_stacked(job) {
    const o = BUILDERS.area(job); o.series.forEach((s) => (s.stack = "total")); return o;
  },
  scatter(job, theme) {
    return { ...datasetOf(job), ...titleBlock(job), grid: GRID, legend: legend(job),
      xAxis: { type: "value", name: job.data.dimensions[0], nameLocation: "middle", nameGap: 28 },
      yAxis: { type: "value", name: job.data.dimensions[1], nameLocation: "middle", nameGap: 42 },
      series: [{ type: "scatter", symbolSize: 10, itemStyle: { opacity: 0.82 }, encode: { x: 0, y: 1, tooltip: [0, 1] },
        ...pointLabels(job, theme, (i) => Number(job.data.source[i]?.[1]) || 0) }] };
  },
  bubble(job, theme) {
    const o = BUILDERS.scatter(job, theme);
    const sizes = job.data.source.map((r) => Number(r[2]) || 0);
    const max = Math.max(1, ...sizes);
    o.series[0].symbolSize = (val) => 9 + 30 * Math.sqrt((Number(val[2]) || 0) / max);
    o.series[0].itemStyle = { opacity: 0.78, borderColor: groundOf(theme), borderWidth: 1 };
    Object.assign(o.series[0], pointLabels(job, theme, (i) => sizes[i]));
    return o;
  },
  pie(job, theme, { donut = false } = {}) {
    return { ...titleBlock(job), legend: legend(job),
      series: [{ type: "pie", radius: donut ? ["45%", "70%"] : "70%", center: ["50%", "60%"],
        data: job.data.items, label: { show: true, formatter: "{b}: {c}", color: inkOf(theme), ...NOHALO },
        labelLine: { lineStyle: { color: mutedOf(theme), opacity: 0.6 } },
        itemStyle: { borderColor: groundOf(theme), borderWidth: 2 }, emphasis: { scale: false } }] };
  },
  donut(job, theme) { return BUILDERS.pie(job, theme, { donut: true }); },
  heatmap(job, theme) {
    const { rows, cols, matrix } = job.data;
    // The matrix must match the axes it is drawn against. ECharts plots [col, row, value] points
    // and simply does not draw a point whose index falls outside the category axis, so a matrix
    // with an extra row or a short row lost those cells with no error and no visible gap — and a
    // matrix with FEWER rows than `rows` shifted every value onto the wrong label, which is worse
    // than losing it: the chart is confidently wrong and looks complete. Both are silent
    // wrong-output, the class this engine refuses.
    if (Array.isArray(rows) && Array.isArray(matrix) && matrix.length !== rows.length) {
      throw new VisualJobError("G-CHART",
        `heatmap matrix has ${matrix.length} row(s) but data.rows declares ${rows.length} ` +
        `(${rows.join(", ")}). Every value would be drawn against the wrong row label.`);
    }
    if (Array.isArray(cols) && Array.isArray(matrix)) {
      const bad = matrix.findIndex((row) => Array.isArray(row) && row.length !== cols.length);
      if (bad !== -1) {
        throw new VisualJobError("G-CHART",
          `heatmap matrix row ${bad} has ${matrix[bad].length} cell(s) but data.cols declares ` +
          `${cols.length}. Cells past the axis are dropped from the render without warning.`);
      }
    }
    const flat = matrix.flat().filter((v) => typeof v === "number");
    const lo = job.scale_min ?? Math.min(0, ...flat);
    const hi = job.scale_max ?? Math.max(1, ...flat);
    const ramp = theme?.semantic?.heatRamp ?? ["#0F2040", "#4A7FC1", "#EDB84A"];
    const points = [];
    // Each cell's label ink is chosen from ITS OWN fill (the ramp colour at its value), so a value is readable on
    // the dark end and on the gold end alike — no outline needed, and nothing to change on hover.
    matrix.forEach((row, r) => row.forEach((v, c) => {
      if (typeof v !== "number") { points.push([c, r, v ?? "-"]); return; }
      const ink = inkFor(rampAt(ramp, (v - lo) / (hi - lo || 1)));
      points.push(ink ? { value: [c, r, v], label: { color: ink } } : [c, r, v]);
    }));
    return { ...titleBlock(job),
      grid: { ...GRID, right: 96 },
      xAxis: { type: "category", data: cols, splitArea: { show: true } },
      yAxis: { type: "category", data: rows, inverse: true, splitArea: { show: true } },
      // docgen law: a heatmap never ships without its scale legend.
      visualMap: { min: lo, max: hi, calculable: false, orient: "vertical", right: 8, top: "center", itemWidth: 12, itemHeight: 120,
        text: [String(hi), String(lo)], textStyle: { color: mutedOf(theme), fontSize: 10 }, inRange: { color: ramp } },
      series: [{ type: "heatmap", data: points, label: { show: job.show_values ?? true, fontSize: 10, ...NOHALO } }] };
  },
  matrix(job, theme) { return BUILDERS.heatmap(job, theme); },
  sankey(job, theme) {
    return { ...titleBlock(job),
      series: [{ type: "sankey", data: job.data.nodes, links: job.data.links, top: titleTop(job), bottom: 16, left: 12, right: 150,
        emphasis: { focus: "adjacency" }, nodeAlign: "left", nodeWidth: 14, nodeGap: 10,
        lineStyle: { color: "gradient", curveness: 0.5, opacity: 0.45 }, label: { fontSize: 11, color: inkOf(theme), ...NOHALO } }] };
  },
  funnel(job, theme) {
    return { ...titleBlock(job), legend: legend(job),
      series: [{ type: "funnel", sort: "descending", gap: 2, top: titleTop(job) + 14, bottom: 12,
        itemStyle: { borderColor: groundOf(theme), borderWidth: 1 },
        data: job.data.items,
        // Funnel labels sit OUTSIDE the tile by default, i.e. on the page ground: theme ink, not tile-contrast ink
        // (a dark-on-dark label here was invisible on four of six stages).
        label: { show: true, formatter: "{b}: {c}", color: inkOf(theme), ...NOHALO },
        labelLine: { lineStyle: { color: mutedOf(theme), opacity: 0.6 } } }] };
  },
  graph(job, theme) {
    const nodes = job.data.nodes;
    const n = nodes.length;
    const layout = job.layout ?? "circular";
    // The schema declares three layouts and the builder used to pass ANY string through, so `layout: "force"` -- whose
    // result depends on the iteration it stopped at -- reached ECharts despite a comment saying it never would.
    if (!["circular", "none", "preset"].includes(layout)) {
      throw new VisualJobError("G-STRUCT", `graph layout "${layout}" is not one of circular, none, preset (a force layout is not deterministic)`);
    }
    const fontPx = 11;
    const labelPx = (nd) => String(nd.name).length * fontPx * 0.6;
    const radiusOf = (nd) => (nd.symbolSize ?? 24) / 2;
    const pal = paletteOf(theme);
    // The ring is laid out HERE, not by ECharts, so the label of every node can go to the side of its dot that faces away
    // from the ring. ECharts put every label to the right of its dot: on the left half of the ring those labels sat inside
    // the circle, on top of the lines (the defect the operator reported). Angle i is (i + 0.5) / n of a turn, clockwise from
    // the +x axis (screen y points down). The side is a pure function of the angle: right half right, left half left, and
    // a node at a pole (within ~9 degrees of the vertical) puts its name above or below its dot, where no line runs.
    const turn = (i) => ((i + 0.5) / n) * 2 * Math.PI;
    const unit = layout === "circular" ? nodes.map((_, i) => ({ c: Math.cos(turn(i)), s: Math.sin(turn(i)) })) : null;
    const xs = unit ? [] : nodes.map((nd) => nd.x ?? 0);
    const mid = unit ? 0 : (Math.min(...xs) + Math.max(...xs)) / 2;
    const half = unit ? 1 : Math.max(1e-9, (Math.max(...xs) - Math.min(...xs)) / 2);
    const sideOf = (nd, i) => {
      const dx = unit ? unit[i].c : ((nd.x ?? 0) - mid) / half;
      if (unit && Math.abs(dx) < 0.16) return unit[i].s < 0 ? "top" : "bottom";
      return dx >= 0 ? "right" : "left";
    };
    const sides = nodes.map(sideOf);
    // A name takes the room it needs on its side of the ring, but never more than 38% of the canvas on either side: a name long
    // enough to need more used to push the margins past the whole canvas (a 100-character name on a 300 px graph left a box
    // 414 px wide, negative, and every coordinate reversed). A name that does not fit in that room is truncated with an ellipsis
    // (the full name stays in the tooltip and the marks table).
    const canvasW = job.width ?? 640;
    const maxMargin = Math.floor(canvasW * 0.38);
    const roomFor = (nd) => Math.max(8, maxMargin - radiusOf(nd) - 12);
    const need = (which) => Math.min(maxMargin, Math.max(24, ...nodes.map((nd, i) => (sides[i] === which ? labelPx(nd) + radiusOf(nd) + 12 : 0))));
    const R = Math.max(...nodes.map(radiusOf));
    const left = need("left");
    const right = need("right");
    const top = titleTop(job) + 6 + R + (sides.includes("top") ? 18 : 0);
    const bottom = 18 + R + (sides.includes("bottom") ? 18 : 0);
    // A view fits the NODE CENTRES to the box and stretches x and y independently, which would squash every symbol into an
    // ellipse (symbols are drawn in the stretched frame). Giving the ring the box's own proportions makes the fit uniform,
    // so the ring is as large as the box allows and the nodes stay round.
    const boxW = canvasW - left - right;
    const boxH = (job.height ?? 480) - top - bottom;
    if (!(boxW > 0) || !(boxH > 0)) {
      throw new VisualJobError("G-STRUCT", `the graph's plotting box would be ${Math.round(boxW)} x ${Math.round(boxH)} px after the title, the symbols and the names: the canvas (${canvasW} x ${job.height ?? 480}) is too small for it`);
    }
    const placed = unit
      ? nodes.map((nd, i) => ({ ...nd, x: (boxW / 2) * unit[i].c, y: (boxH / 2) * unit[i].s }))
      : nodes;
    const colorOf = new Map(nodes.map((nd) => [String(nd.id ?? nd.name), nd.itemStyle?.color ?? pal[0]]));
    // A node that no link touches is drawn with a dashed outline in the page ink, whatever the reason it is alone: the
    // reader sees at once that nothing connects to it, and the tooltip says so. (Why it is alone is the job's to say: a node
    // may carry a `note`, which the tooltip and the marks table print.)
    const linked = new Set(job.data.links.flatMap((l) => [String(l.source), String(l.target)]));
    const isolated = (nd) => !linked.has(String(nd.id ?? nd.name));
    return { ...titleBlock(job),
      series: [{ type: "graph", layout: "none", // every layout we accept is a fixed position by the time ECharts sees it
        top, bottom, left, right,
        data: placed.map((nd, i) => ({ ...nd, symbolSize: nd.symbolSize ?? 24,
          ...(isolated(nd) ? { itemStyle: { ...(nd.itemStyle ?? {}), borderType: "dashed", borderWidth: 2, borderColor: inkOf(theme) } } : {}),
          label: { position: sides[i], ...((sides[i] === "left" || sides[i] === "right") && labelPx(nd) > roomFor(nd) ? { width: roomFor(nd), overflow: "truncate" } : {}), ...(nd.label ?? {}) } })),
        // A line takes the colour of the module it LEAVES. ECharts 6 does not honour `lineStyle.color: "source"` (every
        // edge was the default series blue: measured, one stroke on 34 of 34 edges), so the source's colour is written onto
        // each link. At a node, the lines that leave it carry its own colour and the lines that arrive carry their senders'.
        links: job.data.links.map((l) => ({ ...l, lineStyle: { color: colorOf.get(String(l.source)) ?? pal[0], ...(l.lineStyle ?? {}) } })), roam: false,
        label: { show: true, fontSize: fontPx, distance: 6, color: inkOf(theme), ...NOHALO },
        edgeSymbol: ["none", "arrow"], edgeSymbolSize: 8,
        lineStyle: { opacity: 0.55, width: 1.6, curveness: layout === "none" ? 0 : 0.18 } }] };
  },
  tree(job, theme) {
    return { ...titleBlock(job),
      series: [{ type: "tree", data: [job.data.root], orient: "LR", symbol: "circle", symbolSize: 10, top: titleTop(job), bottom: 14, left: 96, right: 150,
        edgeShape: "curve", lineStyle: { color: mutedOf(theme), width: 1.6, opacity: 0.55, curveness: 0.5 },
        itemStyle: { color: paletteOf(theme)[0], borderColor: groundOf(theme), borderWidth: 2 },
        // Parent labels sit ABOVE their dot: at `left` they ran straight through the incoming edge.
        label: { position: "top", verticalAlign: "bottom", align: "center", distance: 7, fontSize: 11, color: inkOf(theme), ...NOHALO },
        leaves: { label: { position: "right", verticalAlign: "middle", align: "left", distance: 8, color: inkOf(theme), ...NOHALO } },
        expandAndCollapse: false, initialTreeDepth: -1 }] };
  },
  treemap(job, theme) {
    const ground = groundOf(theme);
    return { ...titleBlock(job),
      // `root?.children` (not `root.children`): the `?? items` fallback is the documented
      // second input shape for this family, but without the optional chain an items-only job
      // throws TypeError on the missing `root` before the `??` is ever reached — so the
      // fallback was unreachable. No test/preset/fixture covered either hierarchy family.
      series: [{ type: "treemap", data: colorizeTree(job.data.root?.children ?? job.data.items, paletteOf(theme)),
        // Explicit pixel box: ECharts' default `width/height: 80%` silently wins over left/right and left the tiles in a
        // narrow island with a blank band either side.
        left: 8, top: titleTop(job), width: job.width - 16, height: job.height - titleTop(job) - 10, roam: false, nodeClick: false,
        breadcrumb: { show: false }, squareRatio: 1.3,
        // A tile's name sits in the MIDDLE of the tile, in the display face at a weight that holds on a saturated fill, and
        // breaks onto a second line when the tile is wide enough for one: the default (11px regular, pinned top-left) read as
        // a caption stuck to the corner and was the first thing the operator asked to change.
        label: { show: true, position: "inside", align: "center", verticalAlign: "middle", fontSize: TILE_FONT_PX, fontWeight: 600,
          fontFamily: displayFont(theme), overflow: "truncate", lineHeight: 16, ...NOHALO },
        // The strip that names a group sits on the page ground (the tile's own colour is hidden under its children),
        // so its ink follows the THEME; the leaf labels above follow their own tile.
        upperLabel: { show: true, height: 22, fontSize: 12, fontWeight: 700, fontFamily: displayFont(theme), color: inkOf(theme), ...NOHALO },
        itemStyle: { borderColor: ground, borderWidth: 2, gapWidth: 2 },
        levels: [{ itemStyle: { borderColor: ground, borderWidth: 3, gapWidth: 3 } }, { itemStyle: { borderColor: ground, borderWidth: 2, gapWidth: 2 } }] }] };
  },
  sunburst(job, theme) {
    return { ...titleBlock(job),
      series: [{ type: "sunburst", data: colorizeTree(job.data.root?.children ?? job.data.items, paletteOf(theme)), // see treemap above
        radius: ["14%", "84%"], center: ["50%", "56%"], itemStyle: { borderColor: groundOf(theme), borderWidth: 2 },
        label: { rotate: "radial", fontSize: 10, minAngle: 9, ...NOHALO } }] };
  },
  boxplot(job, theme) {
    const pal = paletteOf(theme);
    // A candle: a body that is lit from the top and settles into the series colour at the bottom, drawn in a rim a shade
    // lighter than its own fill. ECharts paints a box white and then (before this) it was a hollow navy outline: the
    // loudest thing on a dark page and then the faintest. The wash is the series blue blended half-way toward the palette
    // green, so the body reads teal-blue against the plain-blue bars of the charts around it without leaving the palette.
    const top = mix(pal[0], pal[3] ?? pal[0], 0.5);
    const rim = mix(top, "#ffffff", 0.38);
    const body = { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: withAlpha(top, 0.88) }, { offset: 1, color: withAlpha(pal[0], 0.38) }] };
    return { ...titleBlock(job), grid: GRID,
      xAxis: { type: "category", data: job.data.categories },
      yAxis: valueAxis(job),
      series: [{ type: "boxplot", data: job.data.values, itemStyle: { color: body, borderColor: rim, borderWidth: 2 }, boxWidth: [14, 46] }] }; // pre-computed [min,q1,med,q3,max]
  },
  radar(job, theme) {
    const pal = paletteOf(theme);
    const ink = mutedOf(theme);
    return { ...titleBlock(job), legend: legend(job),
      // The web behind the data is faded (it was as loud as the data); each series gets its OWN colour, a thicker
      // outline and a translucent fill so two polygons that overlap are still two shapes.
      radar: { indicator: job.data.axes, radius: "58%", center: ["50%", "58%"], splitNumber: 4,
        axisName: { color: inkOf(theme), fontSize: 11 },
        // The web is the scale you read the polygons against, so it has to be SEEN: it was as loud as the data, then (at
        // 0.22 / 0.16) so faint it vanished on a dark page. Rings and spokes now sit at about half the ink, with a hair of
        // banding between rings; the series (3px lines, 20% fills) still clearly outrank it.
        axisLine: { lineStyle: { color: ink, opacity: 0.5, width: 1.2 } }, splitLine: { lineStyle: { color: ink, opacity: 0.42, width: 1.2 } },
        splitArea: { show: true, areaStyle: { color: ["transparent", ink], opacity: 0.045 } } },
      series: [{ type: "radar", symbol: "circle", symbolSize: 7,
        data: job.data.series.map((x, i) => {
          const color = pal[i % pal.length];
          return { name: x.name, value: x.values, lineStyle: { width: 3, color }, itemStyle: { color, borderColor: groundOf(theme), borderWidth: 1 },
            areaStyle: { color, opacity: 0.2 } };
        }) }] };
  },
  timeline(job, theme) {
    const events = job.data.events;
    return { ...titleBlock(job), grid: { ...GRID, top: 64, bottom: 56, right: 72 },
      xAxis: { type: "time" },
      yAxis: { type: "value", show: false, min: -1, max: 1 },
      series: [{ type: "scatter", symbolSize: 12, itemStyle: { opacity: 0.9 },
        data: events.map((e, i) => ({ name: e.name, value: [e.date, i % 2 === 0 ? 0.35 : -0.35] })),
        label: { show: true, formatter: (p) => p.name, position: "top", fontSize: 10, rotate: 0, color: inkOf(theme), ...NOHALO },
        labelLayout: { hideOverlap: true },
        markLine: { silent: true, symbol: "none", label: { show: false },
          data: events.map((e) => ({ xAxis: e.date })), lineStyle: { type: "dashed", opacity: 0.3 } } }] };
  },
  scorecard(job) {
    // Status scorecard = horizontal bar with semantic status colors, value labels.
    return BUILDERS.bar_horizontal(job);
  },
};

function legend(job) {
  const show = job.legend ?? (job.data?.dimensions?.length > 2 || job.data?.items?.length > 1);
  return { show: Boolean(show), top: 8, right: 8, itemWidth: 14, itemHeight: 10, itemGap: 16, textStyle: { fontSize: 12 } };
}

function valueAxis(job) {
  const axis = { type: job.log_scale ? "log" : "value" };
  // `nameLocation: "middle"` (+ a gap clearing the tick labels) is required, not cosmetic:
  // ECharts' default for an axis name is nameLocation "end", which lands it in the top-left
  // corner for a vertical value axis and at the right edge for a horizontal one — the exact
  // spots titleBlock() puts the title ({left: 8, top: 6}) and where the plot area ends. A job
  // declaring BOTH `title` and `units` therefore rendered the unit on top of the title, or
  // outside the SVG box entirely on bar_horizontal. Measured in a browser, three separate
  // figures. The bubble builder above already sets this pair correctly; valueAxis did not,
  // and no shipped preset happened to combine title+units on a valueAxis chart, so nothing
  // caught it. nameGap 46/32: vertical axes need more room for rotated tick labels.
  if (job.units?.[0]) {
    axis.name = job.units[0];
    axis.nameLocation = "middle";
    axis.nameGap = job.selected_visual === "bar_horizontal" || job.selected_visual === "scorecard" ? 32 : 46;
  }
  if (job.scale_min !== undefined) axis.min = job.scale_min;
  if (job.scale_max !== undefined) axis.max = job.scale_max;
  return axis;
}

/** Reserved severity/status colours for labels that already mean something (see semantic-colors.mjs). */
function applySemanticColors(option, job, theme) {
  const series = option.series ?? [];
  if (series.length === 0) return;
  const fam = job.selected_visual;
  if (fam === "pie" || fam === "donut" || fam === "funnel") {
    const items = series[0].data ?? [];
    const sem = semanticPalette(items.map((d) => d.name), theme);
    if (sem) series[0].data = items.map((d, i) => (sem.colors[i] ? { ...d, itemStyle: { ...(d.itemStyle ?? {}), color: sem.colors[i] } } : d));
    return;
  }
  if (!["bar", "bar_grouped", "bar_stacked", "bar_horizontal", "scorecard", "line", "line_step", "area", "area_stacked"].includes(fam)) return;
  if (series.length > 1) {
    const sem = semanticPalette(series.map((x) => x.name), theme);
    if (!sem) return;
    series.forEach((x, i) => {
      const c = sem.colors[i];
      if (!c) return;
      x.itemStyle = { ...(x.itemStyle ?? {}), color: c };
      if (x.type === "line") x.lineStyle = { ...(x.lineStyle ?? {}), color: c };
      if (x.areaStyle) x.areaStyle = { ...x.areaStyle, color: c };
    });
  } else if (series[0].type === "bar") {
    const cats = (job.data?.source ?? []).map((r) => r[0]);
    const sem = semanticPalette(cats, theme);
    if (sem) series[0].itemStyle = { ...(series[0].itemStyle ?? {}), color: (p) => sem.colors[p.dataIndex] ?? p.color };
  }
}

/** Apply semantic severity/status colors when the preset declares them. */
function applySemantics(option, job, preset, theme) {
  const sem = preset?.semantics;
  if (!sem || !theme) return option;
  if (sem.severity_items && Array.isArray(option.series)) {
    for (const s of option.series) {
      if (Array.isArray(s.data)) {
        s.data = s.data.map((d) => {
          const key = (d.severity ?? d.name ?? "").toString().toLowerCase();
          const color = theme.severity?.[key === "critical" ? "crit" : key === "medium" ? "med" : key];
          return color ? { ...d, itemStyle: { ...(d.itemStyle ?? {}), color } } : d;
        });
      }
    }
  }
  return option;
}

/**
 * One place decides the vertical stack: title, subtitle, legend, plot. The title block, the legend and the grid
 * were each positioned by their own constant, so a job with a title AND a subtitle AND a legend drew the subtitle
 * through the legend and the legend through the top value-axis label (measured on a 28-chart report).
 */
function layoutPass(option, job) {
  const titleH = job.title ? 28 : 6;
  const subH = subLines(job) * 16 + (job.subtitle ? 2 : 0);
  const legendOn = option.legend && option.legend.show !== false;
  const legendTop = titleH + subH + 4;
  if (option.legend) option.legend.top = legendTop;
  // A legend wraps when its entries do not fit the width: ~7px per character + swatch and gap per entry.
  const names = (option.series ?? []).flatMap((x) => (x.type === "pie" || x.type === "funnel" ? (x.data ?? []).map((d) => d.name) : [x.name])).filter(Boolean);
  const legendPx = names.reduce((n, t) => n + String(t).length * 7 + 44, 0);
  const legendLines = legendOn ? Math.max(1, Math.ceil(legendPx / Math.max(200, (job.width ?? 640) - 24))) : 0;
  if (legendOn && option.legend) option.legend.width = Math.max(200, (job.width ?? 640) - 24);
  const gridTop = titleH + subH + (legendOn ? 16 + legendLines * 20 : 16);
  if (option.grid && !Array.isArray(option.grid)) option.grid = { ...option.grid, top: Math.max(option.grid.top ?? 0, gridTop) };
}

// ---------------------------------------------------------------------------------------------------------------------
// Second pass: label fitting for a treemap.
//
// A tile's size exists only AFTER ECharts has laid the tree out, and ECharts' own answer to "the name does not fit" is to
// break a word at any letter ("dy / n / a / m / i / c") or to cut it to one letter ("e", "c"): neither is a label. So the
// engine renders once, reads every tile's real size from the live model, and writes into each tile the label that fits it:
// the whole name at the largest size that fits, wrapped at a word boundary (a space, an underscore, a hyphen) when the tile
// has the height for a second line, shortened with an ellipsis when most of it fits, and left out when almost none does (the
// tooltip and the marks table name every tile). The estimate of a glyph's width is a small table calibrated against the
// embedded Space Grotesk 600 (measured in Chromium: 0.51 em on average, 0.37 to 0.64 per name), padded 4% so it errs short.
// ---------------------------------------------------------------------------------------------------------------------
const TILE_FONT_PX = 13;
const TILE_MIN_FONT_PX = 10;
const TILE_MAX_FONT_PX = 18;
const NARROW_GLYPHS = new Set("iljtfr.,:;'|! ()".split(""));
const WIDE_GLYPHS = new Set("mwMW".split(""));
function glyphEm(c) {
  if (NARROW_GLYPHS.has(c)) return 0.32;
  if (WIDE_GLYPHS.has(c)) return 0.82;
  if (c >= "A" && c <= "Z") return 0.66;
  if (c >= "0" && c <= "9") return 0.58;
  if (c === "_") return 0.5;
  if (c === "-") return 0.38;
  if (c === "&") return 0.7;
  return 0.54;
}
/** Estimated width in px of `str` set at `px`. */
export function textWidthPx(str, px) {
  let em = 0;
  for (const c of String(str)) em += glyphEm(c);
  return em * px * 1.04;
}
/** Split a name into wrap units: a space, an underscore, a hyphen or a slash ends a unit (and the mark stays with it). */
function wrapUnits(name) {
  return String(name).match(/[^\s_/-]+[_/-]?|[_/-]+/g)?.map((u) => u.trim()).filter(Boolean) ?? [String(name)];
}
/** Greedy wrap of `units` into lines of at most `maxPx`; null when a single unit is wider than a line. */
function wrapLines(units, px, maxPx) {
  const lines = [];
  let cur = "";
  for (const u of units) {
    const glue = cur && !/[_/-]$/.test(cur) ? " " : "";
    const next = cur ? `${cur}${glue}${u}` : u;
    if (textWidthPx(next, px) <= maxPx) { cur = next; continue; }
    if (!cur || textWidthPx(u, px) > maxPx) return null;
    lines.push(cur);
    cur = u;
  }
  if (cur) lines.push(cur);
  return lines;
}
function ellipsize(name, px, maxPx) {
  let out = String(name);
  while (out.length > 1 && textWidthPx(`${out}…`, px) > maxPx) out = out.slice(0, -1);
  return `${out.trimEnd()}…`;
}
/** What to print in a tile of `w` x `h` px: `{ text, fontSize }`, or null to print nothing. A big tile earns a bigger name. */
export function fitTileLabel(name, w, h) {
  const padX = 5;
  const padY = 4;
  const aw = w - 2 * padX;
  const ah = h - 2 * padY;
  if (aw < 14 || ah < TILE_MIN_FONT_PX + 2) return null;
  const units = wrapUnits(name);
  const biggest = Math.max(TILE_FONT_PX, Math.min(TILE_MAX_FONT_PX, Math.round(Math.sqrt(w * h) / 13)));
  for (let px = biggest; px >= TILE_MIN_FONT_PX; px -= 1) {
    const lines = wrapLines(units, px, aw);
    if (lines && lines.length * Math.round(px * 1.25) <= ah) return { text: lines.join("\n"), fontSize: px };
  }
  // The whole name does not fit at any size. Keep a shortened one only when most of it survives; otherwise say nothing.
  const px = TILE_MIN_FONT_PX;
  const kept = ellipsize(name, px, aw);
  return kept.length - 1 >= Math.min(String(name).length, 4) && kept.length - 1 >= 0.6 * String(name).length && ah >= px + 2
    ? { text: kept, fontSize: px } : null;
}
/**
 * A group's header strip. One line when the name fits (12px bold, then 11px); two lines when it does not and the group is
 * tall enough to give a strip two lines and still show its children; shortened with an ellipsis otherwise; null when
 * nothing readable fits. `lines` tells the caller how tall the strip must be.
 */
export function fitStripLabel(name, w, h) {
  const aw = w - 10;
  for (const px of [12, 11]) if (textWidthPx(name, px) <= aw) return { text: String(name), fontSize: px, lines: 1 };
  if (h >= 100) {
    for (const px of [12, 11]) {
      const lines = wrapLines(wrapUnits(name), px, aw);
      if (lines && lines.length === 2) return { text: lines.join("\n"), fontSize: px, lines: 2 };
    }
  }
  const kept = ellipsize(name, 11, aw);
  return kept.length - 1 >= Math.min(String(name).length, 5) ? { text: kept, fontSize: 11, lines: 1 } : null;
}
const asFormatter = (text) => (/[{}]/.test(text) ? () => text : text);
const STRIP_ONE_LINE_PX = 22;

/**
 * Re-write a treemap option with the label each tile can actually hold. `chart` is the live ECharts instance that has just
 * laid `option` out. Two phases, because a taller header strip moves its group's children: first every group's strip (its
 * width does not depend on anything below it), re-laid-out; then every leaf tile, measured on that final layout.
 * Returns the refined option, or null when the family has nothing to refine.
 */
export function refineOption(job, theme, chart, option) {
  if (job.selected_visual !== "treemap") return null;
  const treeOf = () => chart.getModel().getSeriesByIndex(0)?.getData?.()?.tree;
  let tree = treeOf();
  if (!tree?.root) return null;
  const strips = structuredClone(option);
  const walkGroups = (items, nodes) => {
    (items ?? []).forEach((item, i) => {
      const box = nodes?.[i]?.getLayout?.();
      if (!box || !(Array.isArray(item.children) && item.children.length > 0)) return;
      const fit = fitStripLabel(item.name, box.width, box.height);
      item.upperLabel = fit
        ? { ...(item.upperLabel ?? {}), show: true, fontSize: fit.fontSize, lineHeight: Math.round(fit.fontSize * 1.25),
          height: fit.lines === 2 ? 2 * Math.round(fit.fontSize * 1.25) + 8 : STRIP_ONE_LINE_PX, formatter: asFormatter(fit.text), overflow: "none" }
        : { ...(item.upperLabel ?? {}), show: false };
      walkGroups(item.children, nodes[i].children);
    });
  };
  walkGroups(strips.series[0].data, tree.root.children);
  chart.setOption(strips, true); // lay out again with the final strip heights, then measure the leaves
  tree = treeOf();
  const refined = structuredClone(strips);
  const walkLeaves = (items, nodes) => {
    (items ?? []).forEach((item, i) => {
      const box = nodes?.[i]?.getLayout?.();
      if (!box) return;
      if (Array.isArray(item.children) && item.children.length > 0) { walkLeaves(item.children, nodes[i].children); return; }
      const fit = fitTileLabel(item.name, box.width, box.height);
      item.label = fit
        ? { ...(item.label ?? {}), show: true, fontSize: fit.fontSize, lineHeight: Math.round(fit.fontSize * 1.25), formatter: asFormatter(fit.text), overflow: "none" }
        : { ...(item.label ?? {}), show: false };
    });
  };
  walkLeaves(refined.series[0].data, tree.root.children);
  return refined;
}

export function buildOption(job, theme, preset) {
  const builder = BUILDERS[job.selected_visual];
  if (!builder) {
    throw new VisualJobError("G-ROUTE",
      `no ECharts builder for "${job.selected_visual}" — check ENGINE_ROUTING_POLICY.json for the owning engine`);
  }
  let option = builder(job, theme);
  // Preset defaults merge under the job (job-derived structure wins).
  if (preset?.defaults) option = deepMerge(structuredClone(preset.defaults), option);
  option = applySemantics(option, job, preset, theme);
  if (job.semantic_colors !== false) applySemanticColors(option, job, theme);
  layoutPass(option, job);
  for (const sr of option.series ?? []) {
    sr.label = { ...NOHALO, ...(sr.label ?? {}) };
    if (sr.leaves?.label) sr.leaves.label = { ...NOHALO, ...sr.leaves.label };
    if (sr.upperLabel) sr.upperLabel = { ...NOHALO, ...sr.upperLabel };
  }
  option.animation = false; // SSR determinism; interactive HTML re-enables
  option.aria = { enabled: true, decal: { show: Boolean(job.accessibility?.decal) } };
  if (job.tooltip !== false) option.tooltip = option.tooltip ?? { trigger: "item" };
  return option;
}

function deepMerge(base, over) {
  if (Array.isArray(base) || Array.isArray(over) || typeof base !== "object" || typeof over !== "object" || !base || !over) {
    return over ?? base;
  }
  const out = { ...base };
  for (const [k, v] of Object.entries(over)) out[k] = k in base ? deepMerge(base[k], v) : v;
  return out;
}
