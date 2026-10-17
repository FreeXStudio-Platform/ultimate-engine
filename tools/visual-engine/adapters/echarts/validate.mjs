/**
 * Visual-job validation + security gates.
 *
 * Every render request passes through validateVisualJob() before any ECharts
 * code sees it. Fail-closed: an invalid or unsafe job throws VisualJobError
 * with a gate id — it never degrades to a partial render (T-R9: silent
 * success is a defect class).
 *
 * Gates implemented here (see SECURITY_POLICY.md):
 *   G-STRUCT  required fields, known visual family, known theme/preset
 *   G-SEC     no executable option content, no external URLs, no HTML
 *   G-SIZE    dataset / dimension caps
 *   G-CONF    classification gate (restricted jobs refused by default)
 *   G-CHART   chart-family laws shared with docgen (pie≤6, bar zero-baseline,
 *             heatmap legend, sankey conservation)
 */

export class VisualJobError extends Error {
  constructor(gate, message) {
    super(`[${gate}] ${message}`);
    this.gate = gate;
  }
}

export const SUPPORTED_VISUALS = [
  "bar", "bar_horizontal", "bar_stacked", "bar_grouped",
  "line", "line_step", "area", "area_stacked",
  "pie", "donut",
  "scatter", "bubble",
  "heatmap", "matrix",
  "sankey", "funnel",
  "graph", "tree", "treemap", "sunburst",
  "boxplot", "radar", "timeline", "scorecard",
  "none",
];

export const CLASSIFICATIONS = ["public", "internal", "confidential", "restricted"];
// "document-theme" carries CSS custom properties instead of literal ink hex, for SVG that is
// inlined into a docgen document and must follow that document's live theme.
export const THEMES = [
  "project-theme",
  "project-theme-dark",
  "project-theme-light",
  "print-theme",
  "document-theme",
];

const LIMITS = {
  maxCells: 50_000,
  maxNodes: 1_500,
  maxEdges: 5_000,
  maxSeries: 24,
  maxWidth: 4_000,
  maxHeight: 4_000,
  minWidth: 100,
  minHeight: 100,
  maxStringLen: 500,
  maxPieSlices: 6, // docgen law: charts.py _PIE_MAX_SLICES
};

// P8-081: schemas/visual-job.schema.json declared these two constraints but nothing enforced
// them — the schema is documentation-only (no jsonschema/ajv anywhere in this repo), so a job
// with a space in `visual_id` or a 2-character `reader_question` passed validateVisualJob()
// clean. Mirrored here as the single enforcement point; kept literal (not read from the schema
// file) because this engine has no schema-loading machinery and adding one to read two constants
// would be a second enforcer of the same rule (T-R9 in reverse). Keep both in sync by hand.
const VISUAL_ID_PATTERN = /^[A-Za-z0-9._-]+$/; // schemas/visual-job.schema.json: visual_id.pattern
const READER_QUESTION_MIN_LENGTH = 8; // schemas/visual-job.schema.json: reader_question.minLength

// Executable / injection surface. ECharts option content must be data-only.
const FORBIDDEN_KEYS = new Set(["formatter_fn", "renderItem", "__proto__", "constructor", "prototype"]);
const FORBIDDEN_PATTERNS = [
  // Matches an OPENING or a CLOSING script tag. The pattern was `/<\s*script/i`, which misses
  // `</script >` entirely — and a closing tag is all an attacker needs when the string is
  // interpolated into an existing inline <script> block, as html-template.mjs does: it breaks
  // out of the script and everything after it is markup.
  [/<\s*\/?\s*script/i, "script tag"],
  [/javascript\s*:/i, "javascript: URL"],
  [/data:\s*text\/html/i, "data:text/html URL"],
  [/https?:\/\//i, "external URL"],
  [/\bfunction\s*\(/, "function literal"],
  [/=>\s*[{(]/, "arrow function literal"],
  [/on\w+\s*=/i, "inline event handler"],
];
// Fields where a URL-looking string is legitimate provenance metadata, never
// injected into the rendered option.
const METADATA_FIELDS = new Set(["data_source_ids", "parent_ids", "selection_reason", "evidence", "notes"]);

function walkStrings(value, path, cb) {
  if (typeof value === "string") { cb(value, path); return; }
  if (Array.isArray(value)) { value.forEach((v, i) => walkStrings(v, `${path}[${i}]`, cb)); return; }
  if (value && typeof value === "object") {
    for (const [k, v] of Object.entries(value)) {
      if (FORBIDDEN_KEYS.has(k)) throw new VisualJobError("G-SEC", `forbidden key "${k}" at ${path}`);
      walkStrings(v, `${path}.${k}`, cb);
    }
  }
}

function countTreeNodes(node) {
  if (!node || typeof node !== "object") return 0;
  const kids = Array.isArray(node.children) ? node.children : [];
  return 1 + kids.reduce((n, kid) => n + countTreeNodes(kid), 0);
}

// Keys that describe the data rather than BEING it. Everything not named here counts as payload.
// This list is short and stable; the payload list is neither, which is the whole point — an
// allow-list of payload keys ("source", "matrix", "items") silently reported 0 for every family
// whose key was not on it (graph `nodes`/`links`, tree `root`, radar `axes`, timeline `events`),
// and a count of 0 disabled both gates that read it. Deny-listing the metadata instead means a
// family added tomorrow is counted correctly without anyone remembering to update this function.
const DATA_METADATA_KEYS = new Set([
  "dimensions", "rows", "cols", "unit", "units", "map", "projection", "format", "encode",
]);

/**
 * Count payload cells in a job's data, across every shape any builder reads.
 *
 * Two gates depend on this number: G-SIZE's cap, and the emptiness gate. Both were blind on every
 * family whose data shape this function did not recognise.
 */
function countCells(data) {
  if (!data || typeof data !== "object") return 0;
  let n = 0;
  for (const [key, value] of Object.entries(data)) {
    if (DATA_METADATA_KEYS.has(key)) continue;
    if (Array.isArray(value)) {
      n += value.reduce((acc, row) => {
        if (Array.isArray(row)) return acc + row.length;
        if (row && typeof row === "object" && Array.isArray(row.data)) return acc + row.data.length;
        return acc + 1;
      }, 0);
    } else if (value && typeof value === "object") {
      // A tree/treemap root, or any other nested object payload.
      n += countTreeNodes(value);
    } else if (value !== undefined && value !== null && value !== "") {
      n += 1;
    }
  }
  return n;
}

/**
 * Validate a visual job. Returns { ok:true, job, warnings } or throws
 * VisualJobError. `opts.allowRestricted` must be explicitly set by a human-
 * approved caller for restricted-classification jobs (the MCP never sets it).
 */
export function validateVisualJob(job, opts = {}) {
  const warnings = [];
  if (!job || typeof job !== "object") throw new VisualJobError("G-STRUCT", "job must be an object");

  for (const field of ["visual_id", "reader_question", "selected_visual", "classification"]) {
    if (!job[field] || typeof job[field] !== "string") {
      throw new VisualJobError("G-STRUCT", `missing required string field "${field}"`);
    }
  }
  if (!VISUAL_ID_PATTERN.test(job.visual_id)) {
    throw new VisualJobError("G-STRUCT",
      `visual_id "${job.visual_id}" must match ${VISUAL_ID_PATTERN} (letters, digits, ".", "_", "-" only)`);
  }
  if (job.reader_question.length < READER_QUESTION_MIN_LENGTH) {
    throw new VisualJobError("G-STRUCT",
      `reader_question must be at least ${READER_QUESTION_MIN_LENGTH} characters (got ${job.reader_question.length}) — a real question, not a placeholder`);
  }
  if (!SUPPORTED_VISUALS.includes(job.selected_visual)) {
    throw new VisualJobError("G-STRUCT",
      `unknown visual "${job.selected_visual}" — supported: ${SUPPORTED_VISUALS.join(", ")}. ` +
      `Architecture/workflow/state diagrams route to tools/docgen (see ENGINE_ROUTING_POLICY.json).`);
  }
  if (!CLASSIFICATIONS.includes(job.classification)) {
    throw new VisualJobError("G-STRUCT", `classification must be one of ${CLASSIFICATIONS.join("/")}`);
  }

  // G-CONF — confidentiality gate.
  if (job.classification === "restricted" && !opts.allowRestricted) {
    throw new VisualJobError("G-CONF",
      "restricted-classification jobs are refused by default. Direct-adapter callers may pass " +
      "allowRestricted after human sign-off; the MCP facade never renders restricted data.");
  }

  // NO_CHART is a first-class outcome: valid, renders nothing.
  if (job.selected_visual === "none") {
    if (!job.no_chart_reason) {
      throw new VisualJobError("G-STRUCT", 'selected_visual "none" requires "no_chart_reason"');
    }
    return { ok: true, job, warnings, no_chart: true };
  }

  if (!job.data || typeof job.data !== "object") {
    throw new VisualJobError("G-STRUCT", 'missing "data" object');
  }

  const theme = job.theme ?? "project-theme";
  if (!THEMES.includes(theme)) {
    throw new VisualJobError("G-STRUCT", `unknown theme "${theme}" — approved: ${THEMES.join(", ")}`);
  }

  // G-SEC — data-only option content.
  const { data, title, subtitle, units } = job;
  for (const [name, value] of Object.entries({ data, title, subtitle, units })) {
    if (value === undefined) continue;
    walkStrings(value, name, (s, path) => {
      if (s.length > LIMITS.maxStringLen) {
        throw new VisualJobError("G-SIZE", `string too long (${s.length} > ${LIMITS.maxStringLen}) at ${path}`);
      }
      const topField = path.split(/[.[]/)[0];
      for (const [re, what] of FORBIDDEN_PATTERNS) {
        if (re.test(s) && !(what === "external URL" && METADATA_FIELDS.has(topField))) {
          throw new VisualJobError("G-SEC", `${what} in ${path}`);
        }
      }
    });
  }

  // G-SIZE — caps.
  const cells = countCells(job.data);
  // An EMPTY dataset is a failure, not a chart. Only the pie/donut family checked this, so every
  // other family rendered a complete, titled, provenance-stamped chart with no data in it — which
  // survived a docgen --strict build and would land in a published document looking deliberate.
  // README's hard rule 2 ("no partial render and no silent default", T-R9) is only true with this
  // check present for every family, not one.
  if (cells === 0) {
    // G-CHART, not G-STRUCT: "a chart family must have data to chart" is a family law, and the
    // pie/donut branch below — the one family that already enforced it — has always raised
    // G-CHART. Generalising the rule must not also renumber it.
    throw new VisualJobError("G-CHART",
      `data for "${job.selected_visual}" is empty — no rows, items, nodes, axes or tree. ` +
      "A chart with no data is not a chart; if there is genuinely nothing to show, use " +
      'selected_visual "none" with a no_chart_reason (T-R9, README hard rule 2).');
  }
  if (cells > LIMITS.maxCells) {
    throw new VisualJobError("G-SIZE",
      `${cells} data cells > cap ${LIMITS.maxCells}. Aggregate before charting — a chart this dense answers no reader question.`);
  }
  if ((job.data.nodes?.length ?? 0) > LIMITS.maxNodes) {
    throw new VisualJobError("G-SIZE", `${job.data.nodes.length} nodes > cap ${LIMITS.maxNodes} (hairball rule — aggregate or use a matrix)`);
  }
  if ((job.data.links?.length ?? 0) > LIMITS.maxEdges) {
    throw new VisualJobError("G-SIZE", `${job.data.links.length} edges > cap ${LIMITS.maxEdges}`);
  }
  const w = job.width ?? 800, h = job.height ?? 480;
  // Number.isFinite() MUST run before the range comparison below. `<`/`>` against a non-numeric
  // value coerce via ToNumber, and NaN fails EVERY comparison (`NaN < x` and `NaN > x` are both
  // `false`) — so a non-numeric width/height (e.g. the string "0px} </style><svg onload=alert(1)>")
  // silently passed this gate untouched and reached html-template.mjs's <style> block unvalidated:
  // CSS-context HTML injection. `Number.isFinite` (not the global `isFinite`,
  // which coerces its argument first and would still accept a numeric-looking string) rejects NaN,
  // +/-Infinity, and every string — width/height must already BE numbers, not merely coerce to one.
  if (!Number.isFinite(w)) {
    throw new VisualJobError("G-SIZE", `width must be a finite number, got ${JSON.stringify(job.width)}`);
  }
  if (!Number.isFinite(h)) {
    throw new VisualJobError("G-SIZE", `height must be a finite number, got ${JSON.stringify(job.height)}`);
  }
  if (w < LIMITS.minWidth || w > LIMITS.maxWidth || h < LIMITS.minHeight || h > LIMITS.maxHeight) {
    throw new VisualJobError("G-SIZE", `dimensions ${w}x${h} outside ${LIMITS.minWidth}-${LIMITS.maxWidth} px`);
  }

  // G-STRUCT — per-row labels for table-shaped data (scatter / bubble / timeline): without them a dot is an anonymous
  // circle and a reader cannot tell WHAT it is. Optional, but when present they must line up row for row, because a
  // name drawn against the wrong dot is a confident wrong answer (T-R9).
  for (const field of ["names", "notes"]) {
    const arr = job.data[field];
    if (arr === undefined) continue;
    if (!Array.isArray(arr) || arr.some((x) => typeof x !== "string")) {
      throw new VisualJobError("G-STRUCT", `data.${field} must be an array of strings`);
    }
    if (Array.isArray(job.data.source) && arr.length !== job.data.source.length) {
      throw new VisualJobError("G-STRUCT",
        `data.${field} has ${arr.length} entr${arr.length === 1 ? "y" : "ies"} but data.source has ${job.data.source.length} rows — ` +
        "they must correspond one to one, or every name after the first gap is attached to the wrong dot.");
    }
  }
  if (job.data.size_label !== undefined && typeof job.data.size_label !== "string") {
    throw new VisualJobError("G-STRUCT", "data.size_label must be a string (the name of the bubble-size measure)");
  }

  // G-CHART — family laws (shared with docgen where the family overlaps).
  const v = job.selected_visual;
  if ((v === "pie" || v === "donut")) {
    const n = job.data.items?.length ?? 0;
    if (n === 0) throw new VisualJobError("G-CHART", "pie requires data.items");
    if (n > LIMITS.maxPieSlices) {
      throw new VisualJobError("G-CHART", `pie has ${n} slices > ${LIMITS.maxPieSlices} (docgen law) — use a bar`);
    }
    if (job.data.items.some((i) => !(i.value > 0))) {
      throw new VisualJobError("G-CHART", "pie slices must all be positive");
    }
  }
  if (v === "sankey") {
    const links = job.data.links ?? [];
    const nodes = new Set((job.data.nodes ?? []).map((n) => n.name));
    if (!links.length || !nodes.size) throw new VisualJobError("G-CHART", "sankey requires nodes and links");
    for (const l of links) {
      if (!(l.value > 0)) throw new VisualJobError("G-CHART", `sankey flow ${l.source}→${l.target} must be > 0`);
      if (!nodes.has(l.source) || !nodes.has(l.target)) {
        throw new VisualJobError("G-CHART", `sankey link ${l.source}→${l.target} has a dangling endpoint`);
      }
    }
  }
  if ((v === "heatmap" || v === "matrix") && !Array.isArray(job.data.matrix)) {
    throw new VisualJobError("G-CHART", "heatmap requires data.matrix (rows × cols) with data.rows/data.cols labels");
  }
  if (v === "radar") {
    const axes = job.data.axes?.length ?? 0;
    if (axes < 3) throw new VisualJobError("G-CHART", "radar requires ≥3 axes (docgen law)");
  }
  if (v.startsWith("bar") && Array.isArray(job.data.source)) {
    const hasNegative = job.data.source.some((row) =>
      (Array.isArray(row) ? row.slice(1) : []).some((x) => typeof x === "number" && x < 0));
    if (hasNegative && !job.allow_negative) {
      throw new VisualJobError("G-CHART", "bar values are zero-baseline (docgen law); pass allow_negative for signed deltas");
    }
  }

  // Accessibility contract fields.
  if (!job.text_summary && !job.accessibility?.text_summary) {
    warnings.push("no text_summary — required before this visual enters a source-of-truth document (Gate G7)");
  }

  return { ok: true, job: { ...job, theme, width: w, height: h }, warnings };
}
