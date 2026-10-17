import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { renderSVG, THEMES, ENGINE_ROOT } from "../adapters/echarts/render.mjs";
import { buildAllThemes, categoricalPalette, loadTokens, themeDiskRecord } from "../adapters/echarts/theme-adapter.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(readFileSync(join(HERE, "..", "fixtures", "normal", "detector-coverage-heatmap.json"), "utf8"));
// P8-083: THEMES is imported from the canonical list (adapters/echarts/validate.mjs) rather than
// hardcoded here, so this test can never silently fall behind the way it did when "document-theme"
// was added to validation/rendering but this file's own local 4-value copy was not updated.

/** Extract the semantic payload of an option — everything the reskin law locks. */
function semanticChecksum(option) {
  return JSON.stringify({
    series: (option.series ?? []).map((s) => ({ type: s.type, data: s.data, stack: s.stack ?? null })),
    dataset: option.dataset ?? null,
    xAxis: option.xAxis ? { type: option.xAxis.type, data: option.xAxis.data ?? null } : null,
    yAxis: option.yAxis ? { type: option.yAxis.type, data: option.yAxis.data ?? null } : null,
    visualMap: option.visualMap ? { min: option.visualMap.min, max: option.visualMap.max } : null,
  });
}

test("reskin law: all approved themes produce identical semantics, distinct appearance where intended", () => {
  const results = THEMES.map((theme) => renderSVG({ ...fixture, theme }));
  const checksums = results.map((r) => semanticChecksum(r.option));
  for (const c of checksums) assert.equal(c, checksums[0], "semantic drift between themes");
  const svgs = new Set(results.map((r) => r.meta.svg_sha256));
  // P8-125: `project-theme` is a DECLARED alias of `project-theme-dark` — byte-identical by
  // construction (theme-adapter.mjs buildAllThemes(), P8-123) — so the true distinct-SVG count is
  // exactly one less than THEMES.length, not the old ">= 2" (which a reskin layer that changed
  // appearance for only 2 of 5 themes would also have satisfied, despite this test's own name
  // promising "all themes produce ... different appearance").
  assert.equal(svgs.size, THEMES.length - 1,
    `expected exactly ${THEMES.length - 1} distinct renders across ${THEMES.length} themes ` +
    `(one alias pair) — reskin layer produced ${svgs.size}: a theme stopped changing appearance, ` +
    "or an undocumented new alias appeared");
});

test("themes derive from docgen tokens — no invented colors", () => {
  const tokens = loadTokens();
  const themes = buildAllThemes();
  const palette = categoricalPalette(tokens);
  assert.deepEqual(themes["project-theme"].color, palette);
  assert.equal(themes["project-theme"].severity.crit, tokens.severity.crit);
  assert.equal(themes["project-theme-light"].textStyle.color, tokens.inks_light.bone);
  assert.equal(themes["print-theme"].backgroundColor, "#FFFFFF");
});

test("severity lattice reserved for severity semantics", () => {
  const themes = buildAllThemes();
  const sev = themes["project-theme"].severity;
  assert.equal(sev.crit, "#C0282A");
  assert.equal(sev.low, "#4A7FC1");
  assert.equal(sev.info, "#3DA875");
  // decorative palette must not silently include unexpected values
  assert.equal(themes["project-theme"].color.length, 6);
});

// P8-082: themes/*.json is a WRITE-ONLY tracked snapshot (nothing in this engine reads it back —
// see themeDiskRecord()'s comment in theme-adapter.mjs); without a guard, a tracked file could
// drift silently out of sync with what `npm run build:themes` would actually produce today, and
// nothing would notice. This asserts the committed bytes are exactly what the generator emits.
test("themes/*.json on disk matches the generator, byte for byte (drift guard)", () => {
  const themesDir = join(ENGINE_ROOT, "themes");
  const themes = buildAllThemes();
  for (const [name, theme] of Object.entries(themes)) {
    const expected = JSON.stringify(themeDiskRecord(theme), null, 2) + "\n";
    const actual = readFileSync(join(themesDir, `${name}.json`), "utf8");
    assert.equal(actual, expected, `themes/${name}.json is stale — re-run \`npm run build:themes\``);
  }
});
