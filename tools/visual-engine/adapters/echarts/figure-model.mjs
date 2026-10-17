/**
 * Figure model — what every mark on a rendered chart MEANS.
 *
 * ECharts' server-side SVG carries no meaning: a bar is a `<rect>`, a graph node is a `<path>`, and the only
 * handle back to the data is a pair of numbers (`series_index`, `data_index`). The browser therefore had nothing
 * to show on hover or click, adjacency could not be highlighted, and an AI reading the picture saw only
 * geometry. This module interrogates the LIVE ECharts model — the same object that just drew the chart — and
 * turns every mark into one record: id, label, value, a plain-language tooltip, and its neighbours.
 *
 * Three consumers read this one model (one fact, one place):
 *   - figure-layer.mjs   writes `<title>` + `data-*` onto the SVG and generates the scoped hover/focus CSS;
 *   - buildFigureJson()  writes the AI-only `<visual_id>.figure.json` sidecar;
 *   - docgen             renders the "how to read" guide and the numbered key under the figure.
 *
 * Determinism: nothing here reads a clock, a random source or the host locale (numbers are formatted with an
 * explicit "en-US"), so two renders of one job produce byte-identical models.
 *
 * `getECData` is an ECharts-internal import. echarts is pinned to an exact version in package.json and
 * VERSION_LOCK.json, and tests/figure-layer.test.mjs fails loudly if the import or the meta contract moves.
 */
import * as echarts from "echarts";
import { getECData } from "echarts/lib/util/innerStore.js";

/** Plain-language "how to read this" per chart family. Shown under the figure and written to the JSON. */
export const HOW_TO_READ = {
  bar: "Each bar is one category and its height is the value. Hover a bar for the exact figure; the rest fade.",
  bar_grouped: "Bars are grouped by category, one colour per series. Hover a bar for its value; use the legend to isolate a series.",
  bar_stacked: "Bars are stacked: each coloured segment is one series and the full height is their total. Hover a segment for its share.",
  bar_horizontal: "Each bar is one category and its length is the value. Hover a bar for the exact figure.",
  line: "Each line is one series over time or category. Hover a point for the exact value and the change since the previous point.",
  line_step: "A step line: the value holds until the next point. Hover a point for the exact value.",
  area: "A filled line: the shaded area is the quantity over time. Hover a point for the exact value.",
  area_stacked: "Stacked areas: each band is one series and the top edge is the running total. Hover a point for the value and the total.",
  pie: "Each slice is one part of the whole. Hover a slice for its value and share.",
  donut: "Each ring segment is one part of the whole. Hover a segment for its value and share.",
  scatter: "Each dot is one item placed by its two measures. Hover a dot to see what it is and its exact values.",
  bubble: "Each bubble is one item: position gives two measures, bubble size gives a third. Hover a bubble to see what it is.",
  heatmap: "Each cell is one row/column pair; colour is the value, read against the scale on the right. Hover a cell for the exact figure.",
  matrix: "Each cell is one row/column pair; colour is the value. Hover a cell for the exact figure.",
  sankey: "Bands are flows between nodes; band width is the quantity. Hover a node or band to light up everything connected to it.",
  funnel: "Each stage is one step; width is how many remain. Hover a stage for its count and the share of the first stage.",
  graph: "Each circle is a node; a line leaves the node whose colour it carries and ends in an arrowhead at the node it enters. Hover a node: the lines leaving it turn blue, the lines entering it turn pink and a two-way link turns white, so you can read who it calls and who calls it. A dashed outline marks a node with no connection in the data.",
  tree: "Each dot is a node and each line a parent-to-child link. Hover a node to light up its path to the root and its branch.",
  treemap: "Each tile is one item; tile area is its size. Hover a tile for its path, size and share of its parent.",
  sunburst: "Rings are levels of a hierarchy; arc length is the size. Hover an arc for its path, size and share of its parent.",
  boxplot: "Each box shows a spread: whiskers are min and max, the box is the middle half, the bar is the median. Hover for the five numbers.",
  radar: "Each polygon is one series measured on every axis; farther from the centre is higher. Hover a point for its axis value.",
  timeline: "Each dot is one event placed on the time axis. Hover a dot for its name and date.",
  scorecard: "Each bar is one status with its count. Hover a bar for the exact figure.",
};

/**
 * Which sibling marks stay lit while one is hovered.
 *   item       only the hovered mark;           series     every mark of the hovered mark's series;
 *   index      every mark sharing its data index (radar: one polygon + its points, within one ECharts series);
 *   adjacency  the mark, its neighbours and the connections between them.
 */
const FOCUS = {
  bar: "item", bar_grouped: "item", bar_stacked: "item", bar_horizontal: "item", scorecard: "item",
  line: "series", line_step: "series", area: "series", area_stacked: "series",
  pie: "item", donut: "item", funnel: "item",
  scatter: "item", bubble: "item", heatmap: "item", matrix: "item", boxplot: "item", timeline: "item",
  treemap: "item", sunburst: "item",
  radar: "index",
  graph: "adjacency", tree: "adjacency", sankey: "adjacency",
};

/** What a legend entry stands for. Pie/funnel legends list DATA ITEMS; every other legend lists SERIES. */
const LEGEND = { pie: "item", donut: "item", funnel: "item", radar: "item" };

const NUM = new Intl.NumberFormat("en-US", { maximumFractionDigits: 3 });
export const fmtNum = (v) => (typeof v === "number" && Number.isFinite(v) ? NUM.format(v) : String(v ?? ""));
const pct = (part, whole) => (whole > 0 ? `${((100 * part) / whole).toFixed(1)}%` : "");
const text = (v) => String(v ?? "");

/**
 * Register the SSR data getter that stamps `ecmeta_*` attributes on rendered elements.
 *
 * ECharts registers its own getter inside `echarts.init({ssr:true})`, so this MUST be called after init and
 * before `renderToSVGString()`. Beyond ECharts' two numbers it adds `data_type` (node / edge / main), and it
 * tags the elements ECharts leaves anonymous: the whole-series line/area shapes (series-level, no data index)
 * and the tree's parent→child curves (no ECharts data at all).
 */
export function installDataGetter() {
  echarts.zrender.registerSSRDataGetter((el) => {
    const d = getECData(el);
    const entries = [];
    if (d.dataIndex != null) {
      entries.push(["series_index", d.seriesIndex], ["data_index", d.dataIndex]);
      if (d.ssrType) entries.push(["ssr_type", d.ssrType]);
      if (d.dataType) entries.push(["data_type", d.dataType]);
    } else if (d.seriesIndex != null && (el.type === "ec-polygon" || el.type === "ec-polyline")) {
      entries.push(["series_index", d.seriesIndex], ["ssr_type", "chart"], ["data_type", "series"]);
    } else if (el.type === "bezier-curve") {
      entries.push(["ssr_type", "chart"], ["data_type", "tedge"]);
    }
    if (entries.length === 0) return undefined;
    // zrender only ever calls `.each(cb)` on the returned object (zrender/lib/svg/graphic.js setMetaData).
    return { each(cb, ctx) { for (const [k, v] of entries) cb.call(ctx, v, k); } };
  });
}

/** ECharts names an unnamed series "series\u0000<index>"; that is not a label a reader should ever see. */
function seriesLabel(s) {
  return s.name && !/^series[\u0000 ]?\d+$/i.test(s.name) ? s.name : "";
}

/** Walk a data tree node up to (but excluding) the virtual root: ["docs", "docs/design", "≤7 days"]. */
function pathOf(node) {
  const names = [];
  for (let n = node; n && n.parentNode; n = n.parentNode) names.unshift(text(n.name));
  return names;
}

function treeItems(series, kind, push) {
  const data = series.getData();
  const tree = data.tree;
  const total = Number(series.getData().tree?.root?.getValue?.() ?? 0);
  for (let i = 0; i < data.count(); i += 1) {
    const node = tree?.getNodeByDataIndex(i);
    if (!node || !node.parentNode) continue; // index 0 is ECharts' virtual root: not a mark
    const path = pathOf(node);
    const value = Number(node.getValue?.() ?? 0);
    const parentValue = Number(node.parentNode.getValue?.() ?? 0);
    const kids = node.children?.length ?? 0;
    const ancestors = [];
    for (let a = node.parentNode; a && a.parentNode; a = a.parentNode) ancestors.push(`n${a.dataIndex}`);
    const lines = [path[path.length - 1] || "(root)"];
    if (path.length > 1) lines.push(`path: ${path.join(" › ")}`);
    if (kind !== "tree") {
      lines.push(`size: ${fmtNum(value)}${parentValue > 0 && node.parentNode.parentNode ? ` · ${pct(value, parentValue)} of ${path[path.length - 2]}` : total > 0 ? ` · ${pct(value, total)} of all` : ""}`);
    }
    if (kids > 0) lines.push(`${kids} child${kids === 1 ? "" : "ren"}`);
    push({
      key: `${series.seriesIndex}|main|${i}`, id: `n${i}`, kind: "node", series: series.seriesIndex, index: i,
      label: path[path.length - 1] || "", value: kind === "tree" ? null : value, path, depth: path.length,
      tip: lines, ancestors, parent: node.parentNode.parentNode ? `n${node.parentNode.dataIndex}` : null,
    });
  }
}

function graphItems(series, kind, push) {
  const g = series.getGraph?.();
  if (!g) return;
  const nodeName = (n) => text(n.id ?? n.name);
  const incident = new Map(); // node dataIndex -> [{edge, other, dir}]
  const edgeIds = [];
  for (const e of g.edges) {
    const a = e.node1.dataIndex;
    const b = e.node2.dataIndex;
    const value = e.getValue?.();
    const rec = { edge: e.dataIndex, a, b, value: typeof value === "number" && Number.isFinite(value) ? value : null };
    edgeIds.push(rec);
    for (const [from, to, dir] of [[a, b, "out"], [b, a, "in"]]) {
      if (!incident.has(from)) incident.set(from, []);
      incident.get(from).push({ ...rec, other: to, dir });
    }
  }
  const names = new Map(g.nodes.map((n) => [n.dataIndex, nodeName(n)]));
  const pairs = new Set(edgeIds.map((e) => `${e.a}>${e.b}`)); // a link that also runs the other way is TWO-WAY
  for (const n of g.nodes) {
    const inc = incident.get(n.dataIndex) ?? [];
    const outs = inc.filter((x) => x.dir === "out").map((x) => names.get(x.other));
    const ins = inc.filter((x) => x.dir === "in").map((x) => names.get(x.other));
    const raw = series.getRawValue(n.dataIndex);
    const note = text(series.getData().getRawDataItem?.(n.dataIndex)?.note ?? "");
    const lines = [nodeName(n)];
    if (kind === "sankey") {
      const outV = inc.filter((x) => x.dir === "out").reduce((s, x) => s + (x.value ?? 0), 0);
      const inV = inc.filter((x) => x.dir === "in").reduce((s, x) => s + (x.value ?? 0), 0);
      if (inV) lines.push(`in: ${fmtNum(inV)}`);
      if (outV) lines.push(`out: ${fmtNum(outV)}`);
      if (!inV && !outV) lines.push("no flows");
    } else {
      if (typeof raw === "number") lines.push(`value: ${fmtNum(raw)}`);
      lines.push(`${inc.length} connection${inc.length === 1 ? "" : "s"}`);
      if (inc.length === 0) lines.push("isolated: no connection in the data");
      if (outs.length) lines.push(`→ ${outs.slice(0, 8).join(", ")}${outs.length > 8 ? `, +${outs.length - 8} more` : ""}`);
      if (ins.length) lines.push(`← ${ins.slice(0, 8).join(", ")}${ins.length > 8 ? `, +${ins.length - 8} more` : ""}`);
      if (note) lines.push(note);
    }
    // Which of this node's lines leave it, which enter it and which run both ways: the direction colours read these.
    const dirOf = (x) => (pairs.has(`${x.b}>${x.a}`) && x.a !== x.b ? "both" : x.dir === "out" ? "out" : "in");
    const edgeIdsOf = (d) => inc.filter((x) => dirOf(x) === d).map((x) => `e${x.edge}`);
    push({
      key: `${series.seriesIndex}|node|${n.dataIndex}`, id: `n${n.dataIndex}`, kind: "node", series: series.seriesIndex,
      index: n.dataIndex, label: nodeName(n), value: typeof raw === "number" ? raw : null, tip: lines,
      degree: inc.length, neighbors: [...new Set(inc.map((x) => `n${x.other}`))], edges: inc.map((x) => `e${x.edge}`),
      out: outs, in: ins, ...(kind === "graph" ? { outEdges: edgeIdsOf("out"), inEdges: edgeIdsOf("in"), bothEdges: edgeIdsOf("both"), isolated: inc.length === 0, ...(note ? { note } : {}) } : {}),
    });
  }
  for (const rec of edgeIds) {
    const from = names.get(rec.a);
    const to = names.get(rec.b);
    const lines = [`${from} → ${to}`];
    if (rec.value != null) lines.push(`value: ${fmtNum(rec.value)}`);
    push({
      key: `${series.seriesIndex}|edge|${rec.edge}`, id: `e${rec.edge}`, kind: "edge", series: series.seriesIndex,
      index: rec.edge, label: `${from} → ${to}`, value: rec.value, tip: lines, from: `n${rec.a}`, to: `n${rec.b}`,
      ends: [`n${rec.a}`, `n${rec.b}`],
    });
  }
}

/** One series of a dataset-driven chart: bar / line / area / scatter / bubble / timeline / scorecard. */
function tableItems(series, job, kind, push, totals) {
  const data = series.getData();
  const dims = job.data?.dimensions ?? [];
  const col = Math.max(1, dims.indexOf(series.name));
  const names = Array.isArray(job.data?.names) ? job.data.names : null;
  const notes = Array.isArray(job.data?.notes) ? job.data.notes : null;
  const unit = job.units?.[0] ? ` ${job.units[0]}` : "";
  let prev = null;
  for (let i = 0; i < data.count(); i += 1) {
    const raw = series.getRawValue(i);
    const row = Array.isArray(raw) ? raw : [raw];
    let label;
    let lines;
    let value;
    if (kind === "scatter" || kind === "bubble") {
      label = names?.[i] ?? (text(data.getName(i)) || `point ${i + 1}`);
      value = Number(row[1]);
      lines = [label, `${dims[0] ?? "x"}: ${fmtNum(row[0])}`, `${dims[1] ?? "y"}: ${fmtNum(row[1])}`];
      if (kind === "bubble") lines.push(`${job.data?.size_label ?? "size"}: ${fmtNum(row[2])}`);
    } else if (kind === "timeline") {
      label = text(data.getName(i)) || `event ${i + 1}`;
      value = null;
      lines = [label, `when: ${text(row[0])}`];
    } else {
      label = text(row[0] ?? data.getName(i));
      value = Number(row[col]);
      lines = [label, `${series.name || dims[col] || "value"}: ${fmtNum(value)}${unit}`];
      const t = totals?.get(i);
      if (t && t.count > 1) {
        lines.push(`total: ${fmtNum(t.sum)}${unit}`, `share: ${pct(value, t.sum)}`);
      } else if ((kind === "line" || kind === "line_step" || kind === "area") && prev != null && Number.isFinite(prev)) {
        const d = value - prev;
        lines.push(`change: ${d >= 0 ? "+" : ""}${fmtNum(d)}${unit} vs previous`);
      }
      prev = value;
    }
    if (notes?.[i]) lines.push(text(notes[i]));
    push({
      key: `${series.seriesIndex}|undefined|${i}`, id: `s${series.seriesIndex}.${i}`, kind: "point", series: series.seriesIndex,
      index: i, label, value: Number.isFinite(value) ? value : null, tip: lines, seriesName: series.name,
    });
  }
}

function sliceItems(series, kind, push) {
  const data = series.getData();
  let total = 0;
  let first = 0;
  for (let i = 0; i < data.count(); i += 1) {
    const v = Number(series.getRawValue(i)) || 0;
    total += v;
    if (i === 0) first = v;
  }
  for (let i = 0; i < data.count(); i += 1) {
    const v = Number(series.getRawValue(i)) || 0;
    const name = text(data.getName(i));
    const lines = [name, `value: ${fmtNum(v)}`];
    if (kind === "funnel") lines.push(i === 0 ? "first stage" : `${pct(v, first)} of the first stage`);
    else lines.push(`share: ${pct(v, total)}`);
    push({
      key: `${series.seriesIndex}|undefined|${i}`, id: `s${series.seriesIndex}.${i}`, kind: "slice", series: series.seriesIndex,
      index: i, label: name, value: v, tip: lines,
    });
  }
}

function heatItems(series, job, push) {
  const rows = job.data?.rows ?? [];
  const cols = job.data?.cols ?? [];
  const data = series.getData();
  for (let i = 0; i < data.count(); i += 1) {
    const [c, r, v] = series.getRawValue(i);
    const unit = job.units?.[0] ? ` ${job.units[0]}` : "";
    push({
      key: `${series.seriesIndex}|undefined|${i}`, id: `s${series.seriesIndex}.${i}`, kind: "cell", series: series.seriesIndex,
      index: i, label: `${text(rows[r])} × ${text(cols[c])}`, value: typeof v === "number" ? v : null,
      tip: [text(rows[r]), text(cols[c]), `value: ${typeof v === "number" ? fmtNum(v) : "no data"}${unit}`],
    });
  }
}

/**
 * The five numbers of one boxplot row. The documented input is [min, q1, median, q3, max]; ECharts hands the live model
 * the same row with the category index in front (six numbers — probed on echarts 6.1.0). Taking the LAST five reads
 * either shape the same way, so neither a future ECharts nor a caller passing the bare row shifts every statistic (OG-274).
 */
export function boxStats(raw) {
  const [min, q1, med, q3, max] = raw.slice(-5);
  return { min, q1, med, q3, max };
}

function boxItems(series, job, push) {
  const cats = job.data?.categories ?? [];
  const data = series.getData();
  for (let i = 0; i < data.count(); i += 1) {
    const { min, q1, med, q3, max } = boxStats(series.getRawValue(i));
    const name = text(cats[i] ?? data.getName(i)); // a row sits at its own position on the category axis
    push({
      key: `${series.seriesIndex}|undefined|${i}`, id: `s${series.seriesIndex}.${i}`, kind: "box", series: series.seriesIndex,
      index: i, label: name, value: med,
      tip: [name, `median: ${fmtNum(med)}`, `middle half: ${fmtNum(q1)} – ${fmtNum(q3)}`, `range: ${fmtNum(min)} – ${fmtNum(max)}`],
    });
  }
}

function radarItems(series, job, push) {
  const axes = job.data?.axes ?? [];
  const data = series.getData();
  for (let i = 0; i < data.count(); i += 1) {
    const vals = series.getRawValue(i);
    const name = text(data.getName(i));
    const lines = [name, ...axes.map((a, k) => `${text(a.name)}: ${fmtNum(vals[k])}`)];
    push({
      key: `${series.seriesIndex}|undefined|${i}`, id: `s${series.seriesIndex}.${i}`, kind: "series", series: series.seriesIndex,
      index: i, label: name, value: vals.reduce((s, v) => s + (Number(v) || 0), 0), tip: lines,
      axes: axes.map((a, k) => ({ axis: text(a.name), value: vals[k] ?? null })),
    });
  }
}

/** Collect the model from a live chart. Call after `renderToSVGString()` and before `chart.dispose()`. */
export function collectFigureModel(chart, job) {
  const kind = job.selected_visual;
  const gm = chart.getModel();
  const items = [];
  const byKey = new Map();
  const push = (it) => { items.push(it); byKey.set(it.key, it); };
  const seriesList = [];
  const stackTotals = new Map();
  const tableKinds = ["bar", "bar_grouped", "bar_stacked", "bar_horizontal", "scorecard", "line", "line_step", "area", "area_stacked", "scatter", "bubble", "timeline"];

  if ((kind === "bar_stacked" || kind === "area_stacked" || job.stack) && tableKinds.includes(kind)) {
    gm.eachSeries((s) => {
      const dims = job.data?.dimensions ?? [];
      const col = Math.max(1, dims.indexOf(s.name));
      const d = s.getData();
      for (let i = 0; i < d.count(); i += 1) {
        const row = s.getRawValue(i);
        const t = stackTotals.get(i) ?? { sum: 0, count: 0 };
        t.sum += Number(row[col]) || 0;
        t.count += 1;
        stackTotals.set(i, t);
      }
    });
  }

  gm.eachSeries((s) => {
    seriesList.push({ index: s.seriesIndex, name: seriesLabel(s), type: s.subType });
    if (s.subType === "graph" || s.subType === "sankey") graphItems(s, kind, push);
    else if (s.subType === "tree" || s.subType === "treemap" || s.subType === "sunburst") treeItems(s, kind, push);
    else if (s.subType === "pie" || s.subType === "funnel") sliceItems(s, kind, push);
    else if (s.subType === "heatmap") heatItems(s, job, push);
    else if (s.subType === "boxplot") boxItems(s, job, push);
    else if (s.subType === "radar") radarItems(s, job, push);
    else tableItems(s, job, kind, push, stackTotals);
  });

  const legendMode = chart.getModel().getComponent("legend", 0) ? (LEGEND[kind] ?? "series") : "none";
  return {
    kind,
    focus: FOCUS[kind] ?? "item",
    legendMode,
    series: seriesList,
    items,
    byKey,
    howToRead: HOW_TO_READ[kind] ?? "Hover any mark for its exact values.",
  };
}

/**
 * The AI-only sidecar: one normalised, self-describing record of the figure — what it is, what it answers,
 * every mark with its value and connections, and how to read it. No geometry, no colours: meaning only.
 */
export function buildFigureJson({ model, job, meta, svgSha256 }) {
  return {
    schema: "ultimate-engine/figure/1",
    id: job.visual_id,
    kind: model.kind,
    title: job.title ?? null,
    subtitle: job.subtitle ?? null,
    reader_question: job.reader_question ?? null,
    summary: job.text_summary ?? job.accessibility?.text_summary ?? null,
    classification: job.classification,
    how_to_read: model.howToRead,
    units: job.units ?? null,
    series: model.series,
    legend: model.legendMode === "none" ? [] : (model.legendMode === "series"
      ? model.series.map((s, i) => ({ index: i, label: s.name }))
      : model.items.filter((x) => x.kind === "slice" || (model.kind === "radar" && x.kind === "series")).map((x, i) => ({ index: i, label: x.label }))),
    marks: model.items.map((it) => {
      const { key, tip, ...rest } = it; // eslint-disable-line no-unused-vars
      return { ...rest, description: tip.join("; ") };
    }),
    provenance: {
      engine: meta.engine,
      adapter: meta.adapter,
      theme: meta.theme,
      // Nested under a bare `sha256` key on purpose: docgen's leak-gate waives a 64-hex run only when the word
      // `sha256` stands alone beside it, and `svg_sha256` does not (the underscore joins the words).
      svg: { sha256: svgSha256 },
      job: { sha256: meta.job_sha256 },
      data_sources: job.data_source_ids ?? null,
    },
  };
}
