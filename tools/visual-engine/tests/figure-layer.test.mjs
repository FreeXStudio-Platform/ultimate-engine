import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { renderSVG } from "../adapters/echarts/render.mjs";
import { buildAllThemes } from "../adapters/echarts/theme-adapter.mjs";
import { inkFor, contrastRatio, parseColor, mix, rampAt } from "../adapters/echarts/contrast.mjs";
import { semanticColor, semanticPalette } from "../adapters/echarts/semantic-colors.mjs";
import { stripStyleBlocks, isOwnStroke } from "../adapters/echarts/figure-layer.mjs";
import { boxStats } from "../adapters/echarts/figure-model.mjs";

/**
 * The figure layer's contract (OG-250 … OG-261). These tests read the committed golden JOBS, not the golden SVGs, so
 * they keep asserting the contract after a re-baseline. Browser behaviour (hover, adjacency, tooltips) is exercised by
 * the docgen figure runtime tests; what is checked here is the part that is knowable from the bytes:
 * scope, uniqueness, meaning on every mark, and the hover law.
 */
const HERE = dirname(fileURLToPath(import.meta.url));
const GOLDEN = join(HERE, "..", "renders", "golden");
const job = (id) => JSON.parse(readFileSync(join(GOLDEN, `${id}.job.json`), "utf8"));
const render = (id) => renderSVG(job(id), { allowRestricted: false });

const FAMILIES = [
  "SIM-02-detector-test-matrix", // heatmap
  "SIM-03-stage-reconciliation", // funnel
  "SIM-04-workflow-pipeline",    // graph
  "SIM-08-queue-latency",        // line
  "SIM-09-incident",             // timeline
  "SIM-17-svg",                  // bar_horizontal
];

const cssOf = (svg) => /<style data-ve="[^"]*"><!\[CDATA\[([\s\S]*?)\]\]><\/style>/.exec(svg)?.[1] ?? "";
const rulesOf = (css) => [...css.replace(/\/\*[\s\S]*?\*\//g, "").replace(/@media[^{]*\{/g, "").matchAll(/([^{}]+)\{([^{}]*)\}/g)]
  .map((m) => ({ selector: m[1].trim(), body: m[2].trim() }));
const topLevelSelectors = (selector) => {
  const out = [];
  let depth = 0;
  let cur = "";
  for (const ch of selector) {
    if (ch === "(" || ch === "[") depth++;
    if (ch === ")" || ch === "]") depth--;
    if (ch === "," && depth === 0) { out.push(cur.trim()); cur = ""; } else cur += ch;
  }
  if (cur.trim()) out.push(cur.trim());
  return out;
};

test("every figure is self-scoped: one root contract, one scoped stylesheet, none of ECharts' own CSS", () => {
  for (const id of FAMILIES) {
    const { svg } = render(id);
    const fid = `ve-${id}`;
    const root = /<svg [^>]*>/.exec(svg)[0];
    for (const [name, pattern] of [["data-fig", fid], ["data-fig-kind", "[a-z_]+"], ["data-fig-focus", "(item|series|index|adjacency)"], ["data-fig-legend", "(none|series|item)"], ["class", "ve-fig"]]) {
      assert.match(root, new RegExp(`\\b${name}="${pattern}"`), `${id}: root carries ${name}`);
    }
    assert.equal((svg.match(/<style\b/g) ?? []).length, 1, `${id}: exactly one <style>`);
    assert.doesNotMatch(svg, /zr-cls-/, `${id}: ECharts' hover classes are gone`);
    assert.doesNotMatch(svg, /pointer-events:none\s*[;}]?[^{}]*:hover|:hover[^{}]*\{[^}]*pointer-events:none/, `${id}: no hover rule steals the pointer`);
  }
});

test("every CSS selector a figure ships starts with its own scope — it cannot touch another figure", () => {
  for (const id of FAMILIES) {
    const { svg } = render(id);
    const scope = `svg[data-fig="ve-${id}"]`;
    const rules = rulesOf(cssOf(svg));
    assert.ok(rules.length > 3, `${id}: has rules`);
    for (const r of rules) {
      for (const sel of topLevelSelectors(r.selector)) {
        assert.ok(sel.startsWith(scope), `${id}: unscoped selector "${sel}"`);
      }
    }
  }
});

test("hover law: a hover/focus state never changes hue, never fills, never moves, never takes the pointer", () => {
  for (const id of FAMILIES) {
    const { svg } = render(id);
    for (const r of rulesOf(cssOf(svg))) {
      if (!/:hover|:focus-visible/.test(r.selector)) continue;
      // The one fill a hover rule may set: a faint NEUTRAL wash on a legend item's own (invisible) hit area.
      const legendWash = /\[data-t="legend"\]/.test(r.selector) && /fill\s*:\s*rgba\(/.test(r.body);
      // The ONE declared exception to "never changes hue": in a GRAPH, while a node is hovered, the lines leaving it, entering
      // it or running both ways take the figure's direction palette (`var(--ve-out|in|both)`), because there the hue IS the
      // information. Nothing else may recolour, and the palette may not be anything but those three variables.
      const direction = /data-fig-kind="graph"/.test(svg)
        ? [...r.body.matchAll(/(?:^|;)\s*(?:fill|stroke)\s*:\s*var\(--ve-(?:out|in|both)\)/g)].length : 0;
      const body = direction ? r.body.replace(/(^|;)\s*(?:fill|stroke)\s*:\s*var\(--ve-(?:out|in|both)\)(?:-opacity)?/g, "$1") : r.body;
      if (!legendWash) {
        assert.doesNotMatch(body, /(^|;)\s*(fill|background|color)\s*:\s*(?!none\b)/, `${id}: hover rule "${r.selector}" recolours`);
      }
      assert.doesNotMatch(body, /pointer-events\s*:\s*none/, `${id}: hover rule "${r.selector}" steals the pointer`);
      assert.doesNotMatch(body, /transform\s*:/, `${id}: hover rule "${r.selector}" moves the mark`);
      const subjectIsOpenPath = topLevelSelectors(r.selector).some((sel) => /\[fill="none"\]:(hover|focus-visible)$/.test(sel));
      if (!legendWash && subjectIsOpenPath) {
        assert.match(r.body, /fill\s*:\s*none/, `${id}: an open path stays open on hover`);
      }
    }
  }
});

test("ids are document-unique across figures and every url(#…) resolves inside its own figure", () => {
  const seen = new Map();
  for (const id of FAMILIES) {
    const { svg } = render(id);
    const declared = [...svg.matchAll(/(?<![\w-])id="([^"]+)"/g)].map((m) => m[1]);
    for (const d of declared) {
      assert.ok(!seen.has(d), `id "${d}" is declared by both ${seen.get(d)} and ${id}`);
      seen.set(d, id);
    }
    for (const ref of [...svg.matchAll(/url\(#([^)]+)\)/g)].map((m) => m[1])) {
      assert.ok(declared.includes(ref), `${id}: url(#${ref}) resolves to nothing in this figure`);
    }
  }
});

test("every mark answers: graph nodes and edges carry an id, a title, and their neighbours", () => {
  const { svg } = render("SIM-04-workflow-pipeline");
  const nodes = [...svg.matchAll(/<(?:path|circle|rect|ellipse)\b[^>]*\bdata-k="node"[^>]*>(?:<title>([^<]*)<\/title>)?/g)];
  const edges = [...svg.matchAll(/<(?:path|polyline|line)\b[^>]*\bdata-k="edge"[^>]*>(?:<title>([^<]*)<\/title>)?/g)];
  assert.ok(nodes.length >= 5 && edges.length >= 5, `expected a real graph, got ${nodes.length} nodes / ${edges.length} edges`);
  const ids = new Set(nodes.map((n) => /data-id="([^"]+)"/.exec(n[0])?.[1]));
  for (const n of nodes) {
    assert.match(n[0], /data-id="[^"]+"/, "node has an id");
    assert.match(n[0], /data-nb="[^"]*"/, "node lists its neighbours");
    assert.ok(n[1] && n[1].length > 0, "node has a title (tooltip, screen reader, no-JS fallback)");
  }
  for (const e of edges) {
    const ends = /data-en="([^"]+)"/.exec(e[0])?.[1]?.split(" ") ?? [];
    assert.equal(ends.length, 2, "edge names its two ends");
    for (const end of ends) assert.ok(ids.has(end), `edge end "${end}" is a node of this figure`);
    assert.ok(e[1] && e[1].length > 0, "edge has a title");
  }
});

test("the AI-only figure record describes the same marks the SVG draws", () => {
  const { svg, figure } = render("SIM-04-workflow-pipeline");
  assert.equal(figure.schema, "ultimate-engine/figure/1");
  assert.equal(figure.id, "SIM-04-workflow-pipeline");
  assert.equal(figure.kind, "graph");
  assert.ok(figure.how_to_read.length > 20);
  assert.ok(figure.reader_question);
  const drawnIds = new Set([...svg.matchAll(/\bdata-id="([^"]+)"/g)].map((m) => m[1]));
  const recorded = figure.marks.filter((m) => m.kind === "node" || m.kind === "edge");
  assert.ok(recorded.length > 0);
  for (const m of recorded) {
    assert.ok(m.id && m.label !== undefined && m.description, `mark ${JSON.stringify(m.id)} is self-describing`);
    assert.ok(drawnIds.has(m.id), `recorded mark ${m.id} is drawn`);
  }
  assert.equal(figure.provenance.svg.sha256.length, 64);
  assert.equal(figure.provenance.job.sha256.length, 64);
});

test("rendering is deterministic: same job, same bytes, same figure record", () => {
  for (const id of ["SIM-04-workflow-pipeline", "SIM-02-detector-test-matrix"]) {
    const a = render(id);
    const b = render(id);
    assert.equal(a.svg, b.svg);
    assert.deepEqual(a.figure, b.figure);
  }
});

test("labels carry no halo and sit on their fill in a readable ink", () => {
  const { svg } = render("SIM-02-detector-test-matrix");
  assert.doesNotMatch(svg, /<text\b[^>]*\bstroke=/, "no label outline");
  assert.doesNotMatch(svg, /<text\b[^>]*stroke-width/, "no label outline width");
});

test("contrast: chosen ink always clears WCAG AA against the fill, literal colours only", () => {
  assert.equal(inkFor("#000000"), "#FFFFFF");
  assert.equal(inkFor("#ffffff"), "#0B0E14");
  assert.equal(inkFor("var(--fg)"), null, "a non-literal fill cannot be measured");
  assert.equal(inkFor(undefined), null);
  for (let r = 0; r <= 255; r += 51) for (let g = 0; g <= 255; g += 51) for (let b = 0; b <= 255; b += 51) {
    const fill = `rgb(${r},${g},${b})`;
    const ratio = contrastRatio(parseColor(fill), parseColor(inkFor(fill)));
    assert.ok(ratio >= 4.5, `${fill} → ${inkFor(fill)} is only ${ratio.toFixed(2)}:1`);
  }
  assert.equal(mix("#000000", "#ffffff", 0.5), "#808080");
  assert.equal(rampAt(["#000000", "#ffffff"], 0), "rgb(0,0,0)");
  assert.equal(rampAt(["#000000", "#ffffff"], 1), "rgb(255,255,255)");
  assert.equal(rampAt(["#zzz"], 0.5), null);
});

test("semantic colours: severity and status words keep their meaning, other labels keep the palette", () => {
  const theme = buildAllThemes()["project-theme"];
  assert.equal(semanticColor("Critical", theme), theme.severity.crit);
  assert.equal(semanticColor("low", theme), theme.severity.low, "low is BLUE in the Atlas scale");
  assert.equal(semanticColor("Medium", theme), theme.severity["med-hi"]);
  assert.ok(semanticColor("Unrated", theme), "Unrated is a neutral grey, never a severity colour");
  assert.notEqual(semanticColor("Unrated", theme), theme.severity.crit);
  assert.equal(semanticColor("Parser", theme), null);
  assert.ok(semanticPalette(["Critical", "High", "Medium", "Low", "Info"], theme));
  assert.equal(semanticPalette(["Parser", "Runtime", "Gate"], theme), null);
  assert.equal(semanticPalette(["Critical", "Parser", "Runtime", "Gate", "Other"], theme), null, "one hit is not a severity chart");
});

test("style stripping reaches a fixed point: deleting one block cannot splice another into existence (CodeQL js/incomplete-multi-character-sanitization)", () => {
  const BLOCK = /<style\b[^>]*>[\s\S]*?<\/style>/;
  const spliced = "<svg><sty<style>a</style>le>b</style><g/></svg>";
  // premise: ONE pass (cut every block out, join what is left) really does leave a live <style> behind, so the loop is
  // load-bearing. Written as split/join on purpose: this is the broken shape being demonstrated, not code to call.
  const onePass = spliced.split(new RegExp(BLOCK.source, "g")).join("");
  assert.match(onePass, /<style\b/);
  assert.equal(stripStyleBlocks(spliced), "<svg><g/></svg>");
  const deep = "<svg>" + "<sty".repeat(6) + "<style>x</style>" + "le>y</style>".repeat(6) + "<g/></svg>";
  assert.doesNotMatch(stripStyleBlocks(deep), /<style\b/);
  // ordinary ECharts output: untouched apart from the stylesheet
  assert.equal(stripStyleBlocks('<svg><style>.a{fill:red}</style><path d="M0 0"/></svg>'), '<svg><path d="M0 0"/></svg>');
  assert.equal(stripStyleBlocks("<svg><path/></svg>"), "<svg><path/></svg>");
});

test("a mark that draws a stroke in its own colour keeps it on hover and pin: a blue point must not turn black (OG-269)", () => {
  // classification: a COLOUR is an own stroke; white, greys and unparseable values are separators
  for (const c of ["#4A7FC1", "rgb(232, 150, 64)", "#3DA875", "#C0282A"]) assert.equal(isOwnStroke(c), true, c);
  for (const c of ["#fff", "#FFFFFF", "rgb(255,255,255)", "#5C6578", "#9AA3B2", "none", "var(--fg)", undefined]) assert.equal(isOwnStroke(c), false, String(c));
  // the line chart's point symbols are white-filled rings in the series colour: they carry data-sk="own"
  const { svg } = render("SIM-08-queue-latency");
  const own = svg.match(/<path[^>]*\bdata-sk="own"[^>]*>/g) ?? [];
  assert.ok(own.length > 0, "the line chart's symbols are classified as drawing their own stroke");
  for (const tag of own) assert.match(tag, /\bstroke="#[0-9A-Fa-f]{6}"/, "an own-stroke mark names a colour");
  // hover/focus/pin rules that target own-stroke marks change width, brightness and opacity — never the stroke COLOUR
  const targetsOwn = (selector) => selector.replace(/:not\(\[data-sk="own"\]\)/g, "").includes('[data-sk="own"]');
  const rules = rulesOf(cssOf(svg)).filter((r) => targetsOwn(r.selector) && /:hover|:focus-visible|\.ve-pin/.test(r.selector));
  assert.ok(rules.length >= 2, "there are hover and pin rules for own-stroke marks");
  for (const r of rules) {
    assert.doesNotMatch(r.body, /(^|;)\s*stroke\s*:/, `own-stroke rule must not repaint the stroke: ${r.selector}`);
    assert.match(r.body, /stroke-width/, `own-stroke rule thickens the stroke: ${r.selector}`);
  }
  // and the separator rule still exists for marks without a coloured stroke of their own (bars, slices, tiles)
  const sep = rulesOf(cssOf(svg)).filter((r) => /:not\(\[data-sk="own"\]\)/.test(r.selector) && /:hover/.test(r.selector));
  assert.ok(sep.length >= 1 && sep.every((r) => /stroke\s*:/.test(r.body)), "marks without their own stroke keep the ink outline");
});

// OG-274 — a boxplot row is five statistics. ECharts hands the model [categoryIndex, min, q1, median, q3, max] (six
// numbers: probed on echarts 6.1.0), the documented INPUT is [min, q1, median, q3, max]; reading the last five works for
// both, and the category is the row's own position.
test("boxStats reads the five statistics from either shape of row", () => {
  assert.deepEqual(boxStats([1, 2, 3, 4, 5]), { min: 1, q1: 2, med: 3, q3: 4, max: 5 });
  assert.deepEqual(boxStats([0, 1, 2, 3, 4, 5]), { min: 1, q1: 2, med: 3, q3: 4, max: 5 });
  assert.deepEqual(boxStats([7, 134, 245.5, 280, 706.5, 2326]), { min: 134, q1: 245.5, med: 280, q3: 706.5, max: 2326 });
});

test("a rendered boxplot names each category with its own median, middle half and range", () => {
  const boxJob = {
    visual_id: "box-two-categories", reader_question: "How is each measure distributed?", classification: "public",
    data_shape: "boxplot", selected_visual: "boxplot", title: "Two spreads", units: ["ms"],
    text_summary: "Category a has median 3 and category b has median 4; b sits one unit higher throughout.",
    data: { categories: ["a", "b"], values: [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6]] },
  };
  const svg = renderSVG(boxJob, { allowRestricted: false }).svg;
  const titles = [...svg.matchAll(/<title>([\s\S]*?)<\/title>/g)].map((m) => m[1]);
  const a = titles.find((t) => t.startsWith("a\n") || t.startsWith("a&#10;") || /^a(\n|\s)/.test(t));
  const b = titles.find((t) => /^b(\n|\s)/.test(t));
  assert.ok(a && b, `both boxes carry a title: ${JSON.stringify(titles)}`);
  assert.match(a, /median: 3/);
  assert.match(a, /middle half: 2 – 4/);
  assert.match(a, /range: 1 – 5/);
  assert.match(b, /median: 4/);
  assert.match(b, /range: 2 – 6/);
});
