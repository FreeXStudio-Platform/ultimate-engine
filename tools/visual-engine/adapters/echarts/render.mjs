/**
 * Direct ECharts renderer — the non-MCP path (spec §9). CI, batch, offline,
 * fallback, and tests all run through here; the MCP facade is a thin wrapper
 * over these same functions, so the project never depends on an MCP process.
 *
 * Guarantees:
 *  - deterministic SVG (animation off, ids normalized, TZ forced to UTC so
 *    time-axis layout never depends on the host machine's timezone, floats
 *    as emitted by ECharts SSR which is stable for a pinned version) →
 *    build-twice byte-identical AND cross-machine byte-identical, same
 *    discipline as tools/docgen
 *  - every render stamped `generated-by visual-engine` with a
 *    content sha256, matching the docgen provenance convention
 *  - evidence JSON per render (Gate G9)
 */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, basename } from "node:path";
import * as echarts from "echarts";
import { validateVisualJob, VisualJobError, SUPPORTED_VISUALS, THEMES } from "./validate.mjs";
import { buildOption, refineOption } from "./option-builder.mjs";

// Force UTC for every render, everywhere this module runs. ECharts' time axis
// computes "nice" tick boundaries and formats labels using the PROCESS'S LOCAL
// system timezone (Intl/Date) — a render on a +03:30 laptop and the identical
// render in UTC CI produced genuinely different tick positions and SVG bytes
// for a time-axis job (found 2026-08-10: PR #111's own first CI run, on a
// timeline preset — TZ=UTC locally reproduced CI's exact output byte-for-byte,
// confirming the cause). Determinism must not depend on WHERE the process
// happens to run; this line makes that true by construction rather than by
// coincidence of the machine's configured timezone. Set at module load, well
// before any renderSVG() call performs the actual date/axis computation.
process.env.TZ = "UTC";
import { buildAllThemes, opaqueGround } from "./theme-adapter.mjs";
import { interactiveHTML } from "./html-template.mjs";
import { installDataGetter, collectFigureModel, buildFigureJson } from "./figure-model.mjs";
import { decorateSvg } from "./figure-layer.mjs";

/** The document-unique scope for one figure: `ve-<visual_id>`. docgen refuses two figures with one scope. */
export function figureScope(visualId) {
  return `ve-${String(visualId).replace(/[^A-Za-z0-9_-]/g, "_")}`;
}

const HERE = dirname(fileURLToPath(import.meta.url));
export const ENGINE_ROOT = join(HERE, "..", "..");
const PRESETS_DIR = join(ENGINE_ROOT, "presets");
// P8-066: the documented CLI/MCP render path (AI_AGENT_SKILL.md's `render ... --evidence`) used to
// write here UNCONDITIONALLY, dirtying a git-tracked golden snapshot on every ad-hoc render. This
// directory is the DEFAULT for writeEvidence() and lives under renders/current/, which is already
// gitignored (repo-root .gitignore) — so an ad-hoc render's evidence no longer touches the tree.
// The tracked evidence/validation/ snapshots below are reserved for `npm run simulate`'s golden
// flow, which now passes TRACKED_EVIDENCE_DIR explicitly (tests/run_simulations.mjs).
const DEFAULT_EVIDENCE_DIR = join(ENGINE_ROOT, "renders", "current", "evidence");
export const TRACKED_EVIDENCE_DIR = join(ENGINE_ROOT, "evidence", "validation");

export const ENGINE_VERSION = JSON.parse(readFileSync(join(ENGINE_ROOT, "package.json"), "utf8")).version;
export const ECHARTS_VERSION = JSON.parse(
  readFileSync(join(ENGINE_ROOT, "node_modules", "echarts", "package.json"), "utf8"),
).version;

let _themes;
export function themes() {
  if (!_themes) {
    _themes = buildAllThemes();
    for (const [name, t] of Object.entries(_themes)) echarts.registerTheme(name, t);
  }
  return _themes;
}

let _presets;
export function listPresets() {
  if (!_presets) {
    _presets = {};
    if (existsSync(PRESETS_DIR)) {
      for (const f of readdirSync(PRESETS_DIR).filter((f) => f.endsWith(".json")).sort()) {
        const p = JSON.parse(readFileSync(join(PRESETS_DIR, f), "utf8"));
        _presets[p.id] = p;
      }
    }
  }
  return _presets;
}

export function listCapabilities() {
  return {
    engine: "echarts",
    engine_version: ECHARTS_VERSION,
    adapter_version: ENGINE_VERSION,
    visuals: SUPPORTED_VISUALS.filter((v) => v !== "none"),
    themes: THEMES,
    presets: Object.keys(listPresets()),
    formats: ["svg", "png", "html"],
    no_chart_supported: true,
    routing_policy: "ENGINE_ROUTING_POLICY.json — documents/diagrams stay on tools/docgen; app UI stays on Recharts",
  };
}

export { validateVisualJob, VisualJobError, THEMES };

function sha256(s) { return createHash("sha256").update(s).digest("hex"); }

/**
 * Normalize zrender instance/global counters so repeat renders are
 * byte-identical (build-twice determinism, docgen discipline). Two sources of
 * drift: the per-instance prefix `zr<N>-`, and global counters like
 * `cls-<N>` / `gradient-<N>` / `clip-<N>` that keep incrementing across
 * echarts.init() calls in one process. Both are renumbered by first
 * appearance, keeping intra-document references (class ↔ style, url(#id))
 * consistent.
 */
function normalizeSVG(svg) {
  let out = svg.replace(/zr\d+-/g, "zr-");
  for (const kind of ["cls", "gradient", "clip", "shadow", "pattern"]) {
    const seen = new Map();
    out = out.replace(new RegExp(`zr-${kind}-(\\d+)`, "g"), (_, n) => {
      if (!seen.has(n)) seen.set(n, seen.size);
      return `zr-${kind}-${seen.get(n)}`;
    });
  }
  return out;
}

function resolvePreset(job) {
  if (!job.preset) return undefined;
  const preset = listPresets()[job.preset];
  if (!preset) throw new VisualJobError("G-STRUCT", `unknown preset "${job.preset}" — see presets/`);
  if (preset.visual && preset.visual !== job.selected_visual) {
    throw new VisualJobError("G-STRUCT",
      `preset "${job.preset}" is for visual "${preset.visual}", job selected "${job.selected_visual}"`);
  }
  return preset;
}

/** Core: job → { svg, option, meta } (throws on any gate failure). */
export function renderSVG(rawJob, opts = {}) {
  const { job, warnings, no_chart } = validateVisualJob(rawJob, opts);
  if (no_chart) {
    return { no_chart: true, reason: job.no_chart_reason, warnings, meta: { visual_id: job.visual_id } };
  }
  const theme = themes()[job.theme];
  const preset = resolvePreset(job);
  let option = buildOption(job, theme, preset);

  const started = performance.now();
  const chart = echarts.init(null, job.theme, { renderer: "svg", ssr: true, width: job.width, height: job.height });
  let svg;
  let model;
  try {
    chart.setOption(option);
    // Geometry that exists only after layout (a treemap's tile sizes) is read from the live model and written back: one
    // deterministic second pass, never a guess. See refineOption() in option-builder.mjs.
    const refined = refineOption(job, theme, chart, option);
    if (refined) { option = refined; chart.setOption(option, true); }
    // After init (ECharts registers its own getter there), before the render that reads it.
    installDataGetter();
    svg = chart.renderToSVGString();
    model = collectFigureModel(chart, job); // needs the live model: read it before dispose()
  } finally {
    chart.dispose();
  }
  svg = normalizeSVG(svg);
  // Figure layer: scoped ids and CSS, data-* attributes, <title> per mark. See figure-layer.mjs for the why.
  svg = decorateSvg(svg, {
    fid: figureScope(job.visual_id),
    model,
    ink: theme?.semantic?.inks?.bone ?? "currentColor",
    faint: theme?.semantic?.hairlineStrong ?? "rgba(128,128,128,.28)",
  });

  // Accessibility + provenance on the final artifact.
  // FULL XML escaping, not just quotes. Escaping only `"` left `&` and `<` raw inside an attribute,
  // so any title containing "R&D", "a < b" or an HTML-ish fragment produced a NON-WELL-FORMED SVG —
  // written to disk, reported as success, and rejected by every strict XML parser downstream. The
  // ampersand must be escaped FIRST or it would double-escape the entities added after it.
  const escapeXmlAttr = (value) =>
    String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&apos;");
  const label = escapeXmlAttr(job.accessibility?.aria_label ?? job.title ?? job.reader_question);
  // `data-engine` lets an embedding document target chart SVGs in CSS. It needs one because a
  // chart paints no ground of its own (backgroundColor is "transparent", so it inherits the
  // document theme) — which meant docgen's decorative blueprint grid showed THROUGH the plot
  // area: graph paper behind every bar and radar. Nothing else distinguishes an engine SVG
  // from a native docgen one once both are inlined.
  svg = svg.replace("<svg ", `<svg data-engine="echarts" role="img" aria-label="${label}" `);
  const hash = sha256(svg);
  svg += `\n<!-- generated-by visual-engine v${ENGINE_VERSION} · echarts@${ECHARTS_VERSION} · theme:${job.theme} · content-sha256:${hash} -->\n`;

  const meta = {
    visual_id: job.visual_id,
    selected_visual: job.selected_visual,
    preset: job.preset ?? null,
    theme: job.theme,
    classification: job.classification,
    engine: `echarts@${ECHARTS_VERSION}`,
    adapter: `visual-engine@${ENGINE_VERSION}`,
    width: job.width,
    height: job.height,
    svg_sha256: hash,
    option_sha256: sha256(JSON.stringify(option)),
    job_sha256: sha256(JSON.stringify(rawJob)),
    render_ms: Math.round(performance.now() - started),
    warnings,
  };
  const figure = buildFigureJson({ model, job, meta, svgSha256: hash });
  return { svg, option, meta, warnings, figure };
}

export async function renderPNG(rawJob, opts = {}) {
  const result = renderSVG(rawJob, opts);
  if (result.no_chart) return result;
  const warnings = result.meta?.warnings ?? [];
  const { Resvg } = await import("@resvg/resvg-js");
  // System-font rasterization: PNG is a convenience export; SVG is canonical
  // (EXPORT_POLICY.md). Determinism of PNG is per-host, not cross-host.
  // OG-50: the ground follows the THEME. This was the literal `"#060608"` for every theme, so a
  // light-theme PNG came out near-black with light-theme ink on it — invisible in the SVG path,
  // which paints `transparent` and inherits, and invisible in source. `document-theme` has no
  // answer here (a document chart follows the host page's runtime palette, which a raster cannot
  // observe), so an explicit `opts.background` is required and its absence is recorded as a
  // warning rather than silently resolved to whichever ground happens to be the default.
  const warnings2 = [...warnings];
  let background = opts.background;
  if (background === undefined) {
    background = opaqueGround(result.meta.theme);
    if (background === null) {
      background = opaqueGround("project-theme-light");
      warnings2.push(
        "document-theme PNG exported without an explicit `background`: a document chart follows " +
          "the host page's palette, which a raster cannot inherit. Defaulted to the light ground " +
          "(the document default); pass opts.background to choose deliberately.",
      );
    }
  }
  const png = new Resvg(result.svg, {
    fitTo: { mode: "width", value: (rawJob.width ?? 800) * (opts.scale ?? 2) },
    background,
  }).render().asPng();
  return {
    ...result,
    png,
    warnings: warnings2,
    meta: { ...result.meta, png_sha256: sha256(png), png_bytes: png.length, png_background: background, warnings: warnings2 },
  };
}

export function renderInteractiveHTML(rawJob, opts = {}) {
  const result = renderSVG(rawJob, opts); // validation + option build (+ static meta)
  if (result.no_chart) return result;
  const theme = themes()[result.meta.theme];
  const html = interactiveHTML({
    job: { title: rawJob.title, reader_question: rawJob.reader_question, text_summary: rawJob.text_summary ?? rawJob.accessibility?.text_summary },
    option: result.option,
    theme,
    themeName: result.meta.theme,
    // OG-50, the same defect one export away: the page chrome around the chart was a hardcoded
    // dark body, so a light-theme interactive export framed light-theme ink in near-black.
    ground: opaqueGround(result.meta.theme) ?? opaqueGround("project-theme-light"),
    width: rawJob.width ?? 800,
    height: rawJob.height ?? 480,
    staticSVG: result.svg,
    versions: { echarts: ECHARTS_VERSION, adapter: ENGINE_VERSION },
  });
  return { ...result, html, meta: { ...result.meta, html_sha256: sha256(html) } };
}

export async function renderBatch(jobs, opts = {}) {
  const out = [];
  for (const job of jobs) {
    try {
      out.push(await renderPNG(job, opts));
    } catch (e) {
      out.push({ error: e.message, gate: e.gate ?? null, visual_id: job?.visual_id ?? null });
    }
  }
  return out;
}

/**
 * Persist render evidence (Gate G9). Writes under `dir` (default DEFAULT_EVIDENCE_DIR, gitignored
 * — see the comment on that constant). Only `tests/run_simulations.mjs`'s golden flow passes
 * `TRACKED_EVIDENCE_DIR` explicitly, to update the git-tracked snapshots on purpose.
 */
export function writeEvidence(meta, dir = DEFAULT_EVIDENCE_DIR) {
  mkdirSync(dir, { recursive: true });
  const safe = basename(String(meta.visual_id)).replace(/[^A-Za-z0-9._-]/g, "_");
  const path = join(dir, `${safe}.json`);
  // `render_ms` is a wall-clock measurement and is deliberately NOT persisted. These files are
  // tracked evidence whose own release record declares `date_basis: content-derived (no clock in
  // the render path)` — persisting a timing made 7 of them change on EVERY run (6ms -> 5ms), so the
  // working tree was permanently dirty and a real regression would hide in that noise. The value is
  // still returned on the in-memory result, which is where the simulation's >5000ms threshold
  // reads it (tests/run_simulations.mjs). Evidence records what was produced, not how fast.
  const { render_ms, ...rest } = meta;   // eslint-disable-line no-unused-vars
  // P8-084: this file is generated output nobody reads back in code (an audit/Gate-G9 trail for
  // humans) — labelled so it does not read as an unmaintained or enforced artifact.
  const durable = {
    _readme: "Gate G9 render-evidence record, written by writeEvidence() (adapters/echarts/render.mjs). " +
      "Documentation/audit trail only — no code in this engine reads this file back; shape is " +
      "schemas/render-result.schema.json (also unvalidated, see its own _status).",
    ...rest,
  };
  writeFileSync(path, JSON.stringify(durable, null, 2) + "\n");
  return path;
}

/** Routing explanation for agents (visual.explain_selection). */
export function explainSelection(job) {
  const v = job?.selected_visual;
  const docgenFamilies = ["flowchart", "state_diagram", "system_map", "dependency_graph", "sequence", "isometric3d", "geo_map", "layered_workflow", "sankey_document"];
  if (docgenFamilies.includes(v)) {
    return { engine: "docgen", reason: `"${v}" is a document/diagram family — authoritative renderer is tools/docgen (deterministic SVG, Atlas tokens, collision validation). See ENGINE_ROUTING_POLICY.json.` };
  }
  if (SUPPORTED_VISUALS.includes(v)) {
    return { engine: "echarts", reason: `"${v}" is a data-chart family owned by the visual-engine ECharts adapter.`, preset_hint: Object.values(listPresets()).find((p) => p.visual === v)?.id ?? null };
  }
  return { engine: null, reason: `Unknown family "${v}". Consult knowledge/CHART_SELECTION_DECISION_TREE.json, or return NO_CHART.` };
}
