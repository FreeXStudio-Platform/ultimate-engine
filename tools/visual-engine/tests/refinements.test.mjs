import { test } from "node:test";
import assert from "node:assert/strict";
import * as echarts from "echarts";
import { renderSVG } from "../adapters/echarts/render.mjs";
import { themes } from "../adapters/echarts/render.mjs";
import { VisualJobError } from "../adapters/echarts/validate.mjs";
import { contrastRatio, parseColor } from "../adapters/echarts/contrast.mjs";
import { fitStripLabel, fitTileLabel, textWidthPx } from "../adapters/echarts/option-builder.mjs";

/**
 * The 2026-10-10 operator review of the report's charts (OG-278 … OG-282): a treemap whose names sat in a corner and broke
 * mid-word, a graph whose lines were one colour and whose left-hand names sat on top of its lines, a radar whose web had
 * vanished, a boxplot that was a hollow outline. Every case below is a defect that was measured, written so that reverting
 * its fix turns it red.
 */
const base = (over) => ({ visual_id: "T-REF", reader_question: "what does this chart show here?", classification: "internal", ...over });

const ringJob = (n, extra = {}) => base({
  selected_visual: "graph", title: "A ring", width: 620, height: 560,
  data: {
    nodes: Array.from({ length: n }, (_, i) => ({ name: `module-${i}`, symbolSize: 24, itemStyle: { color: ["#3DA875", "#EDB84A", "#C0282A"][i % 3] } })),
    links: Array.from({ length: n - 1 }, (_, i) => ({ source: `module-${i}`, target: `module-${i + 1}` })),
  },
  ...extra,
});

// ---------------------------------------------------------------- graph: where the names go

test("every name faces away from the ring: right half right, left half left, a node at a pole above or below", () => {
  const { option } = renderSVG(ringJob(14));
  const nodes = option.series[0].data;
  const mid = (Math.min(...nodes.map((n) => n.x)) + Math.max(...nodes.map((n) => n.x))) / 2;
  const half = (Math.max(...nodes.map((n) => n.x)) - Math.min(...nodes.map((n) => n.x))) / 2;
  const sides = new Set();
  for (const n of nodes) {
    const dx = (n.x - mid) / half;
    const want = Math.abs(dx) < 0.16 ? (n.y < 0 ? "top" : "bottom") : dx > 0 ? "right" : "left";
    assert.equal(n.label.position, want, `${n.name} at dx=${dx.toFixed(2)}`);
    sides.add(n.label.position);
  }
  assert.deepEqual([...sides].sort(), ["bottom", "left", "right", "top"], "a ring of 14 has both poles occupied");
});

test("the ring takes the proportions of its box, so the view's fit is uniform and the symbols stay round", () => {
  for (const [w, h] of [[620, 560], [900, 500], [500, 800]]) {
    const { option } = renderSVG(ringJob(10, { width: w, height: h }));
    const s = option.series[0];
    const xs = s.data.map((n) => n.x);
    const ys = s.data.map((n) => n.y);
    const ring = (Math.max(...xs) - Math.min(...xs)) / (Math.max(...ys) - Math.min(...ys));
    const box = (w - s.left - s.right) / (h - s.top - s.bottom);
    assert.ok(Math.abs(ring / box - 1) < 0.06, `${w}x${h}: ring ${ring.toFixed(3)} vs box ${box.toFixed(3)}`);
  }
});

test("a long name on one side does not take room from the other", () => {
  const job = ringJob(8);
  job.data.nodes[1].name = "a-very-long-module-name-on-the-right";
  job.data.links = [{ source: "a-very-long-module-name-on-the-right", target: "module-2" }];
  const { option } = renderSVG(job);
  const s = option.series[0];
  assert.ok(s.right > s.left + 60, `right margin ${s.right} should dwarf left ${s.left}`);
});

test("a graph asking for a layout the schema does not declare is refused, not passed to ECharts", () => {
  assert.throws(() => renderSVG(ringJob(4, { layout: "force" })), (e) => e instanceof VisualJobError && /force/.test(e.message));
  for (const layout of ["circular", "none", "preset"]) {
    const job = ringJob(4, { layout });
    if (layout !== "circular") job.data.nodes.forEach((n, i) => { n.x = i * 40; n.y = (i % 2) * 40; });
    assert.doesNotThrow(() => renderSVG(job), layout);
  }
});

// ---------------------------------------------------------------- graph: colour and direction

test("a line takes the colour of the module it leaves (ECharts 6 ignores lineStyle.color 'source')", () => {
  const { option, svg } = renderSVG(ringJob(6));
  const colourOf = new Map(option.series[0].data.map((n) => [n.name, n.itemStyle.color]));
  for (const l of option.series[0].links) assert.equal(l.lineStyle.color, colourOf.get(l.source), `${l.source} -> ${l.target}`);
  const strokes = new Set([...svg.matchAll(/<path[^>]*data-k="edge"[^>]*>/g)].map((m) => /\sstroke="([^"]+)"/.exec(m[0])?.[1]).filter(Boolean).map((c) => c.toUpperCase()));
  assert.ok(strokes.size >= 3, `the edges of a three-colour graph are drawn in ${strokes.size} colour(s): ${[...strokes]}`);
});

const mutualJob = () => base({
  selected_visual: "graph", title: "Directions", width: 620, height: 520,
  data: {
    nodes: [{ name: "a" }, { name: "b" }, { name: "c" }, { name: "d", note: "d is a leaf imported by everyone, so nothing lists it" }],
    links: [{ source: "a", target: "b" }, { source: "b", target: "a" }, { source: "a", target: "c" }],
  },
});

test("each node knows which of its lines leave it, enter it or run both ways, and which nodes stand alone", () => {
  const { figure } = renderSVG(mutualJob());
  const mark = (name) => figure.marks.find((m) => m.kind === "node" && m.label === name);
  const a = mark("a");
  const c = mark("c");
  const d = mark("d");
  assert.equal(a.bothEdges.length, 2, "a<->b is one two-way pair: both of its lines");
  assert.equal(a.outEdges.length, 1, "a -> c leaves a");
  assert.equal(a.inEdges.length, 0);
  assert.equal(c.inEdges.length, 1);
  assert.equal(c.outEdges.length + c.bothEdges.length, 0);
  assert.equal(d.isolated, true);
  assert.equal(a.isolated, false);
  assert.match(d.description, /isolated: no connection in the data/);
  assert.match(d.description, /d is a leaf imported by everyone/, "the node's own note travels with it");
});

test("an isolated node is outlined in dashes whatever the reason it is alone", () => {
  const { svg } = renderSVG(mutualJob());
  const nodes = [...svg.matchAll(/<path[^>]*data-k="node"[^>]*>/g)].map((m) => m[0]);
  const dashed = nodes.filter((n) => /stroke-dasharray/.test(n));
  assert.equal(dashed.length, 1, "exactly the one node nothing connects to");
});

test("the direction palette is declared once, for both themes, and is no module's status colour", () => {
  const { svg } = renderSVG(mutualJob());
  const css = /<style data-ve="[^"]*"><!\[CDATA\[([\s\S]*?)\]\]><\/style>/.exec(svg)[1];
  const dark = /svg\[data-fig="[^"]+"\]\{--ve-out:(#[0-9A-Fa-f]{6});--ve-in:(#[0-9A-Fa-f]{6});--ve-both:(#[0-9A-Fa-f]{6})\}/.exec(css);
  const light = /\[data-theme="light"\] \*\)\{--ve-out:(#[0-9A-Fa-f]{6});--ve-in:(#[0-9A-Fa-f]{6});--ve-both:(#[0-9A-Fa-f]{6})\}/.exec(css);
  assert.ok(dark && light, "a dark and a light declaration, each starting with the figure's own selector");
  const status = new Set(["#3DA875", "#EDB84A", "#C0282A", "#E03638", "#9AA3B2", "#1E3A6E", ...themes()["document-theme"].color.map((c) => c.toUpperCase())]);
  for (const [name, ground, set] of [["dark", [6, 6, 8], dark], ["light", [250, 251, 252], light]]) {
    const colours = set.slice(1).map((c) => c.toUpperCase());
    assert.equal(new Set(colours).size, 3, `${name}: three different colours`);
    for (const c of colours) {
      assert.ok(!status.has(c), `${name}: ${c} is a status or palette colour, so a lit line could be mistaken for one`);
      assert.ok(contrastRatio(parseColor(c), ground) >= 3, `${name}: ${c} is a graphic that must reach 3:1 against the page`);
    }
  }
});

test("the reading guide tells the reader what the colours mean", () => {
  const { figure } = renderSVG(mutualJob());
  assert.match(figure.how_to_read, /lines leaving it turn blue/);
  assert.match(figure.how_to_read, /entering it turn pink/);
  assert.match(figure.how_to_read, /two-way link turns white/);
  assert.match(figure.how_to_read, /dashed outline marks a node with no connection/);
});

// ---------------------------------------------------------------- treemap: what a tile prints

const hasNoMidWordBreak = (name, text) => {
  const lines = text.split("\n");
  if (lines.length === 1) return true;
  // every break falls where the name has a space, underscore, hyphen or slash: nothing is cut inside a word
  const rebuilt = lines.join("");
  return rebuilt.replace(/\s/g, "") === String(name).replace(/\s/g, "");
};

test("a name is never broken inside a word, and every line fits the tile", () => {
  const names = ["analysis", "dynamic", "blue_team", "red_team", "services", "platform", "Platform, truth & observability", "audit-orchestration", "api", "db", "configuration"];
  for (const name of names) {
    for (const w of [20, 36, 48, 64, 90, 130, 240]) {
      for (const h of [14, 22, 34, 48, 70, 120, 230]) {
        const fit = fitTileLabel(name, w, h);
        if (!fit) continue;
        assert.ok(hasNoMidWordBreak(name, fit.text), `${name} in ${w}x${h}: ${JSON.stringify(fit.text)}`);
        for (const line of fit.text.split("\n")) {
          assert.ok(textWidthPx(line, fit.fontSize) <= w - 10 + 0.01, `${name} in ${w}x${h}: "${line}" at ${fit.fontSize}px is ${textWidthPx(line, fit.fontSize).toFixed(1)}px wide`);
        }
        assert.ok(fit.text.split("\n").length * Math.round(fit.fontSize * 1.25) <= h - 8 + 0.01 || /…$/.test(fit.text), `${name} in ${w}x${h}: too tall`);
      }
    }
  }
});

test("a tile that cannot hold a readable name prints nothing instead of a stray letter", () => {
  assert.equal(fitTileLabel("evolution", 16, 120), null, "too narrow for any text");
  assert.equal(fitTileLabel("integrations", 60, 12), null, "too short for any text");
  assert.equal(fitTileLabel("observability", 30, 40), null, "a third of the word would survive: say nothing, the tooltip names it");
});

test("a name wraps at its underscore, shrinks before it is cut, and a big tile earns a bigger name", () => {
  assert.deepEqual(fitTileLabel("red_team", 64, 50), { text: "red_\nteam", fontSize: 13 });
  const services = fitTileLabel("services", 56, 100);
  assert.equal(services.text, "services");
  assert.ok(services.fontSize < 13, "11px fits where 13px did not");
  const big = fitTileLabel("analysis", 245, 230);
  assert.ok(big.fontSize > 13 && big.fontSize <= 18, `a 245x230 tile prints at ${big.fontSize}px`);
  assert.equal(fitTileLabel("api", 263, 70).fontSize, 13, "a wide, shallow tile does not balloon");
});

test("a group's header takes two lines when it does not fit one and the group is tall enough", () => {
  const name = "Platform, truth & observability";
  assert.equal(fitStripLabel(name, 400, 300).lines, 1);
  const two = fitStripLabel(name, 150, 160);
  assert.equal(two.lines, 2);
  assert.ok(hasNoMidWordBreak(name, two.text));
  const short = fitStripLabel(name, 150, 60);
  assert.equal(short.lines, 1, "a short group keeps a one-line strip");
  assert.match(short.text, /…$/);
  assert.equal(fitStripLabel("Configuration", 20, 200), null, "nothing readable fits a sliver");
});

test("every label the engine writes into a treemap fits the tile it sits in (checked on the live layout)", () => {
  const children = (prefix, n, v) => Array.from({ length: n }, (_, i) => ({ name: `${prefix}_${i}`, value: v + i * 37 }));
  const job = base({
    selected_visual: "treemap", title: "Sizes", width: 620, height: 520,
    data: { root: { name: "src", children: [
      { name: "Analysis engine", children: [{ name: "analysis", value: 75558 }, { name: "dynamic", value: 4200 }, { name: "parse", value: 3100 }] },
      { name: "Platform, truth & observability", children: [{ name: "platform", value: 7200 }, { name: "truth", value: 6100 }, ...children("tiny", 4, 40)] },
      { name: "Async execution", children: [{ name: "workers", value: 8358 }] },
      { name: "Not mapped to a module", children: [{ name: "red_team", value: 3200 }, ...children("x", 3, 30)] },
    ] } },
  });
  const { option } = renderSVG(job);
  const chart = echarts.init(null, null, { renderer: "svg", ssr: true, width: job.width, height: job.height });
  try {
    chart.setOption(option, true);
    const root = chart.getModel().getSeriesByIndex(0).getData().tree.root;
    let checked = 0;
    const walk = (items, nodes) => items.forEach((item, i) => {
      const box = nodes[i].getLayout();
      if (Array.isArray(item.children) && item.children.length) { walk(item.children, nodes[i].children); return; }
      if (!item.label || item.label.show === false) return;
      const fs = item.label.fontSize;
      const lines = String(item.label.formatter).split("\n");
      for (const line of lines) assert.ok(textWidthPx(line, fs) <= box.width - 10 + 0.5, `${item.name}: "${line}" at ${fs}px is wider than its ${box.width.toFixed(0)}px tile`);
      assert.ok(lines.length * item.label.lineHeight <= box.height - 8 + 0.5, `${item.name}: ${lines.length} lines in a ${box.height.toFixed(0)}px tile`);
      checked += 1;
    });
    walk(option.series[0].data, root.children);
    assert.ok(checked >= 5, `only ${checked} labels were checked`);
  } finally {
    chart.dispose();
  }
});

// ---------------------------------------------------------------- radar and boxplot

test("the radar's web is visible and still quieter than the data", () => {
  const job = base({
    selected_visual: "radar", title: "Findings", width: 620, height: 460,
    data: { axes: [{ name: "a", max: 15 }, { name: "b", max: 15 }, { name: "c", max: 15 }, { name: "d", max: 15 }],
      series: [{ name: "Open", values: [10, 11, 4, 9] }, { name: "Partial", values: [5, 7, 3, 1] }] },
  });
  const { option } = renderSVG(job);
  const web = option.radar;
  for (const [name, o] of [["spokes", web.axisLine.lineStyle.opacity], ["rings", web.splitLine.lineStyle.opacity]]) {
    assert.ok(o >= 0.35 && o <= 0.6, `${name} at ${o}: faint enough to sit under the data, strong enough to be seen (was 0.22 / 0.16)`);
  }
  const series = option.series[0].data[0];
  assert.ok(series.lineStyle.width >= 3 && series.areaStyle.opacity <= 0.25, "the data keeps its weight");
  assert.equal(web.splitArea.show, true, "a hair of banding between rings");
});

test("a boxplot candle is a lit body with a lighter rim, not a hollow outline", () => {
  const job = base({
    selected_visual: "boxplot", title: "Spread", width: 620, height: 420,
    data: { categories: ["a", "b"], values: [[8, 69, 92, 92, 98], [0, 34, 63, 68, 98]] },
  });
  const { option, svg } = renderSVG(job);
  const style = option.series[0].itemStyle;
  assert.equal(style.color.type, "linear");
  assert.equal(style.color.colorStops.length, 2);
  const [top, bottom] = style.color.colorStops.map((s) => /rgba\((\d+),(\d+),(\d+),([\d.]+)\)/.exec(s.color));
  assert.ok(Number(top[4]) > Number(bottom[4]), "lit from the top, settling toward the bottom");
  const lum = (rgb) => 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
  assert.ok(lum(parseColor(style.borderColor)) > lum([top[1], top[2], top[3]].map(Number)), "the rim is lighter than the body");
  assert.match(svg, /<linearGradient/, "the gradient reaches the SVG");
  assert.ok(![...svg.matchAll(/(?<![\w-])id="([^"]+)"/g)].some((m) => !m[1].startsWith("ve-T-REF")), "its id is scoped to the figure like every other");
});

// ---------------------------------------------------------------- the census report's first reading (OG-292)

const areasJob = (names, extra = {}) => base({
  selected_visual: "bar_stacked", title: "Documents per area", width: 620, height: 560, stack: true,
  data: { dimensions: ["Area", "Updated", "Outdated"], source: names.map((n, i) => [n, 3 + i, 1 + (i % 4)]) }, ...extra,
});

test("a category axis shows every name: twelve long names are tilted, not thinned to three", () => {
  const names = ["docs/plan", "docs/archive", "docs/process", "(root)", "docs/design", "docs", "docs/framework", "skills/chart-engine", "skills/doc-lifecycle", "skills/document-engine", "skills/graph-engine", "skills/mermaid-engine"];
  const { option, svg } = renderSVG(areasJob(names));
  assert.equal(option.xAxis.axisLabel.interval, 0, "interval 0 shows every label; the default hides the ones that overlap");
  assert.ok(option.xAxis.axisLabel.rotate > 0, "names wider than their slot are tilted");
  const shown = names.filter((n) => svg.includes(n.length > 24 ? n.slice(0, 20) : n));
  assert.equal(shown.length, names.length, `every one of the ${names.length} names is in the picture; missing: ${names.filter((n) => !shown.includes(n)).join(", ")}`);
});

test("names that already fit their slots are drawn exactly as before: shown, not tilted", () => {
  const { option } = renderSVG(areasJob(["a", "b", "c", "d"]));
  assert.equal(option.xAxis.axisLabel.interval, 0);
  assert.equal(option.xAxis.axisLabel.rotate, undefined);
});

test("a long series keeps the thinned default: sixty dates are not a row of labels", () => {
  const { option } = renderSVG(areasJob(Array.from({ length: 40 }, (_, i) => `2026-09-${String(i + 1).padStart(2, "0")}`)));
  assert.equal(option.xAxis.axisLabel, undefined);
});

test("a horizontal bar chart shows every category too", () => {
  const { option } = renderSVG(base({ selected_visual: "bar_horizontal", title: "t", width: 620, height: 420, data: { dimensions: ["Area", "n"], source: Array.from({ length: 14 }, (_, i) => [`a-fairly-long-area-name-${i}`, i + 1]) } }));
  assert.equal(option.yAxis.axisLabel.interval, 0);
});

// ---------------------------------------------------------------- graph: a long name cannot swallow the canvas (found in review of the host's vendoring PR)

test("a graph name too long for its side is truncated and the plotting box stays positive; a canvas too small for any box is refused", () => {
  const long = "x".repeat(100);
  const job = base({
    selected_visual: "graph", title: "Long", width: 300, height: 420,
    data: { nodes: ["a", "b", "c", long].map((name) => ({ name, symbolSize: 24 })), links: [{ source: "a", target: "b" }, { source: "b", target: "c" }, { source: "c", target: long }] },
  });
  const { option } = renderSVG(job);
  const g = option.series[0];
  assert.ok(g.left + g.right <= 0.76 * 300 + 1, `the margins (${g.left} + ${g.right}) leave a plotting box on a 300 px canvas`);
  const xs = g.data.map((d) => d.x);
  assert.ok(Math.max(...xs) >= Math.min(...xs), "node coordinates are not reversed");
  const longNode = g.data.find((d) => d.name === long);
  assert.equal(longNode.label.overflow, "truncate", "the name that does not fit says so with an ellipsis");
  const short = g.data.find((d) => d.name === "a");
  assert.equal(short.label.overflow, undefined, "a name that fits is left exactly as it was");
  assert.throws(() => renderSVG(base({ ...job, width: 60 })), (err) => err instanceof VisualJobError, "no plotting box at all is refused, not drawn reversed");
});
