import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  renderSVG, renderPNG, renderInteractiveHTML, listPresets, listCapabilities, explainSelection,
} from "../adapters/echarts/render.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(readFileSync(join(HERE, "..", "fixtures", "normal", "detector-coverage-heatmap.json"), "utf8"));

test("build-twice determinism (docgen discipline) on the heatmap fixture", () => {
  const a = renderSVG(fixture).svg;
  const b = renderSVG(fixture).svg;
  assert.equal(a, b);
});

test("SVG carries role, aria-label, and provenance stamp with content hash", () => {
  const { svg, meta } = renderSVG(fixture);
  assert.match(svg, /role="img"/);
  assert.match(svg, /aria-label="/);
  assert.ok(svg.includes(`content-sha256:${meta.svg_sha256}`));
  assert.ok(svg.includes("generated-by visual-engine"));
});

test("heatmap always has its scale legend (visualMap) — docgen law", () => {
  const { option } = renderSVG(fixture);
  assert.ok(option.visualMap, "visualMap missing");
  assert.equal(option.visualMap.min, 0);
  assert.equal(option.visualMap.max, 100);
});

test("PNG export rasterizes the canonical SVG", async () => {
  const r = await renderPNG(fixture);
  assert.ok(r.png.length > 10_000);
  assert.equal(r.meta.png_sha256.length, 64);
});

test("interactive HTML is self-contained with a static fallback", () => {
  const { html } = renderInteractiveHTML(fixture);
  assert.ok(html.includes("static-fallback"), "static fallback div missing");
  assert.ok(html.includes("prefers-reduced-motion"), "reduced-motion media query missing");
  assert.ok(!/src\s*=\s*["']https?:/.test(html), "external script/src found — must be self-contained");
  assert.ok(html.length > 500_000, "echarts not inlined");
  assert.ok(html.includes(fixture.text_summary), "text summary not in figcaption");
});

test("every preset with a fixture-compatible family is loadable and typed", () => {
  const presets = listPresets();
  assert.equal(Object.keys(presets).length, 22);
  for (const p of Object.values(presets)) {
    assert.ok(p.id && p.visual && p.family && p.summary, `preset ${p.id} incomplete`);
  }
});

test("capabilities report matches implementation", () => {
  const caps = listCapabilities();
  assert.equal(caps.engine_version, "6.1.0");
  assert.ok(caps.visuals.includes("heatmap"));
  assert.ok(!caps.visuals.includes("none"));
  assert.equal(caps.presets.length, 22);
});

test("routing explanation sends document diagrams to docgen", () => {
  const r = explainSelection({ selected_visual: "state_diagram" });
  assert.equal(r.engine, "docgen");
  const e = explainSelection({ selected_visual: "heatmap" });
  assert.equal(e.engine, "echarts");
});

test("graph builder refuses non-deterministic force layout", () => {
  const job = {
    visual_id: "T-G", reader_question: "layout test?", classification: "internal",
    selected_visual: "graph", layout: "circular",
    data: { nodes: [{ name: "a" }, { name: "b" }], links: [{ source: "a", target: "b" }] },
  };
  const { option } = renderSVG(job);
  // The ring is laid out by the builder (so each label can face away from it) and handed to ECharts as fixed positions:
  // never the force layout, whose result depends on the iteration it stopped at.
  assert.notEqual(option.series[0].layout, "force");
  assert.equal(option.series[0].layout, "none");
  assert.ok(option.series[0].data.every((n) => Number.isFinite(n.x) && Number.isFinite(n.y)), "every node has a fixed position");
  const twice = renderSVG(job).svg;
  assert.equal(renderSVG(job).svg, twice);
  assert.throws(() => renderSVG({ ...job, layout: "force" }), /./, "an explicit force layout is refused");
});

test("empty dataset fails loudly, not silently (T-R9)", () => {
  assert.throws(() => renderSVG({
    visual_id: "T-E", reader_question: "empty dataset?", classification: "internal",
    selected_visual: "pie", data: { items: [] },
  }), /G-CHART/);
});

test("malformed dataset fails with a gate id", () => {
  assert.throws(() => renderSVG({
    visual_id: "T-M", reader_question: "malformed?", classification: "internal",
    selected_visual: "heatmap", data: { rows: ["a"], cols: ["b"] }, // no matrix
  }), /G-CHART/);
});
