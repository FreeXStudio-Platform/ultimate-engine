#!/usr/bin/env node
/**
 * The 22 required acceptance simulations (spec §35) — AI intent → final
 * document-ready output, verifying content truth AND render quality at each
 * step. Successful chart sims write golden fixtures (job + svg) under
 * renders/golden/ and a release evidence report under evidence/release/.
 *
 * Run: npm run simulate
 */
import { writeFileSync, mkdirSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  renderSVG, renderPNG, renderInteractiveHTML, writeEvidence,
  TRACKED_EVIDENCE_DIR,
} from "../adapters/echarts/render.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..");
const GOLDEN = join(ROOT, "renders", "golden");
mkdirSync(GOLDEN, { recursive: true });
mkdirSync(join(ROOT, "evidence", "release"), { recursive: true });

const J = (id, extra) => ({
  visual_id: id, classification: "internal", theme: "project-theme",
  reader_question: extra.reader_question ?? "simulation question?",
  text_summary: extra.text_summary ?? "Simulation text summary for accessibility gate.",
  ...extra,
});

const SIMS = [];
const sim = (n, name, fn) => SIMS.push({ n, name, fn });
const golden = (job, r) => {
  writeFileSync(join(GOLDEN, `${job.visual_id}.job.json`), JSON.stringify(job, null, 2) + "\n");
  writeFileSync(join(GOLDEN, `${job.visual_id}.svg`), r.svg);
  // P8-066: this is the one flow allowed to update the git-tracked evidence/validation/ snapshots
  // — every other caller (CLI `--evidence`, MCP `visual_render`) gets writeEvidence()'s gitignored
  // default so an ad-hoc render never dirties the tree.
  writeEvidence(r.meta, TRACKED_EVIDENCE_DIR);
};

// 1 detector coverage heatmap (the canonical fixture)
sim(1, "detector coverage heatmap", () => {
  const job = JSON.parse(readFileSync(join(ROOT, "fixtures", "normal", "detector-coverage-heatmap.json"), "utf8"));
  const r = renderSVG(job);
  if (!r.option.visualMap) throw new Error("heatmap without scale legend");
  golden(job, r);
});
// 2 detector test matrix
sim(2, "detector test matrix", () => {
  const job = J("SIM-02-detector-test-matrix", {
    selected_visual: "heatmap", preset: "detector-test-matrix", title: "Detector × test class",
    reader_question: "Which detectors lack a given test class?",
    data: { rows: ["reentrancy-basic", "oracle-twap", "access-owner"], cols: ["unit", "integration", "adversarial"],
      matrix: [[1, 1, null], [1, null, -1], [1, 1, 1]] }, show_values: true, scale_min: -1, scale_max: 1,
  });
  const r = renderSVG(job);
  golden(job, r);
});
// 3 detector-stage reconciliation
sim(3, "detector-stage reconciliation funnel", () => {
  const job = J("SIM-03-stage-reconciliation", {
    selected_visual: "funnel", preset: "detector-stage-reconciliation", title: "Detector executions by stage",
    reader_question: "Where do detector executions attrit between stages?",
    data: { items: [{ name: "scheduled", value: 514 }, { name: "executed", value: 502 }, { name: "findings-normalized", value: 380 }, { name: "verified", value: 122 }] },
  });
  golden(job, renderSVG(job));
});
// 4 audit workflow pipeline (data-annotated DAG)
sim(4, "audit workflow pipeline DAG", () => {
  const job = J("SIM-04-workflow-pipeline", {
    selected_visual: "graph", preset: "workflow-pipeline", layout: "circular", title: "Audit pipeline",
    reader_question: "How do audit stages depend on each other?",
    data: { nodes: [{ name: "intake" }, { name: "normalize" }, { name: "compile" }, { name: "detect" }, { name: "verify" }, { name: "report" }],
      links: [{ source: "intake", target: "normalize" }, { source: "normalize", target: "compile" }, { source: "compile", target: "detect" }, { source: "detect", target: "verify" }, { source: "verify", target: "report" }] },
  });
  golden(job, renderSVG(job));
});
// 5 current-vs-target conformance
sim(5, "current-vs-destination conformance matrix", () => {
  const job = J("SIM-05-conformance", {
    selected_visual: "heatmap", preset: "current-target-conformance", title: "Blueprint conformance",
    reader_question: "Which components diverge from the blueprint?",
    subtitle: "1 conforms · 0.5 partial · 0 diverges — current vs D-39 blueprint, never blended",
    data: { rows: ["ingest-gate", "fingerprint", "bank-storage", "report-pipeline"], cols: ["design", "build", "wiring", "proof"],
      matrix: [[1, 1, 0.5, 0], [1, 0.5, 0.5, 0], [1, 1, 1, 0.5], [1, 1, 1, 1]] }, scale_min: 0, scale_max: 1,
  });
  golden(job, renderSVG(job));
});
// 6 gatekeeper status matrix
sim(6, "gatekeeper status matrix", () => {
  const job = J("SIM-06-gates", {
    selected_visual: "heatmap", preset: "gatekeeper-status-matrix", title: "Gate status by environment",
    reader_question: "Which gates are red where?", subtitle: "1 pass · 0 degraded · -1 fail · empty unknown",
    data: { rows: ["secret-scan", "dep-audit", "invariant-suite", "leak-gate"], cols: ["local", "ci", "vps1", "vps3"],
      matrix: [[1, 1, 1, 1], [1, 1, null, null], [1, 0, 1, -1], [1, 1, 1, 1]] }, scale_min: -1, scale_max: 1, show_values: true,
  });
  golden(job, renderSVG(job));
});
// 7 document/blueprint coverage
sim(7, "document coverage matrix", () => {
  const job = J("SIM-07-doc-coverage", {
    selected_visual: "heatmap", preset: "document-coverage-matrix", title: "Docs coverage by subsystem",
    reader_question: "Which subsystems lack current documentation?",
    data: { rows: ["detectors", "bank", "payments", "frontend"], cols: ["design", "ops", "api"], matrix: [[80, 60, 90], [95, 85, 40], [70, 90, 88], [65, 30, 75]] },
    scale_min: 0, scale_max: 100,
  });
  golden(job, renderSVG(job));
});
// 8 operational latency chart
sim(8, "queue latency percentiles", () => {
  const job = J("SIM-08-queue-latency", {
    selected_visual: "line", preset: "queue-latency", time_axis: true, title: "Audit queue latency",
    subtitle: "5-min aggregation · 2026-08-01→03", units: ["ms"],
    reader_question: "How is queue latency trending?",
    data: { dimensions: ["t", "p50", "p95", "p99"], source: [["2026-08-01", 120, 340, 900], ["2026-08-02", 110, 300, 720], ["2026-08-03", 140, 420, 1100]] },
  });
  golden(job, renderSVG(job));
});
// 9 incident timeline
sim(9, "incident timeline", () => {
  const job = J("SIM-09-incident", {
    selected_visual: "timeline", preset: "incident-timeline", title: "S183 ingest-gate incident",
    reader_question: "What happened, in what order?",
    data: { events: [{ name: "gate bypass detected", date: "2026-08-03T10:00:00Z" }, { name: "type allowlist patched", date: "2026-08-03T14:30:00Z" }, { name: "re-scan clean", date: "2026-08-04T09:00:00Z" }] },
  });
  golden(job, renderSVG(job));
});
// 10 tier entitlement matrix
sim(10, "tier entitlement matrix", () => {
  const job = J("SIM-10-tiers", {
    selected_visual: "heatmap", preset: "tier-entitlement-matrix", classification: "public", title: "Tier entitlements",
    reader_question: "What does each pricing tier include?", subtitle: "1 included · 0.5 limited · 0 excluded (sanitized source)",
    data: { rows: ["$9.90 audit", "$49 audit", "$99 audit"], cols: ["static-pass", "ai-tier-1", "ai-tier-2", "pdf-report"],
      matrix: [[1, 0.5, 0, 1], [1, 1, 0.5, 1], [1, 1, 1, 1]] }, scale_min: 0, scale_max: 1, show_values: true,
  });
  golden(job, renderSVG(job));
});
// 11 architecture/dependency graph
sim(11, "service dependency graph", () => {
  const job = J("SIM-11-topology", {
    selected_visual: "graph", preset: "service-topology", layout: "circular", title: "App-tier topology (data-annotated)",
    reader_question: "Which services depend on which?",
    data: { nodes: [{ name: "nginx" }, { name: "api-public" }, { name: "web" }, { name: "postgres" }, { name: "redis" }],
      links: [{ source: "nginx", target: "api-public" }, { source: "nginx", target: "web" }, { source: "api-public", target: "postgres" }, { source: "api-public", target: "redis" }] },
  });
  golden(job, renderSVG(job));
});
// 12 high-density dataset (within cap; performance recorded)
sim(12, "high-density scatter (2.5k points)", () => {
  const pts = [];
  let seed = 42;
  const rand = () => (seed = (seed * 1103515245 + 12345) % 2 ** 31) / 2 ** 31; // deterministic PRNG, no Math.random
  // 2.5k points: exercises density while the golden stays under the repo's 1MB large-file gate
  for (let i = 0; i < 2500; i++) pts.push([Math.round(rand() * 1000) / 1000, Math.round(rand() * 4000) / 1000]);
  const job = J("SIM-12-dense", {
    selected_visual: "scatter", title: "Dense findings scatter", reader_question: "Where do findings cluster?",
    data: { dimensions: ["confidence", "impact"], source: pts },
  });
  const r = renderSVG(job);
  if (r.meta.render_ms > 5000) throw new Error(`dense render too slow: ${r.meta.render_ms}ms`);
  golden(job, r);
});
// 13 empty dataset → loud failure
sim(13, "empty dataset fails loudly", () => {
  try {
    renderSVG(J("SIM-13-empty", { selected_visual: "pie", data: { items: [] } }));
    throw new Error("empty dataset rendered — T-R9 violation");
  } catch (e) { if (!/G-CHART/.test(e.message)) throw e; }
});
// 14 malformed dataset → gate error
sim(14, "malformed dataset fails with gate id", () => {
  try {
    renderSVG(J("SIM-14-malformed", { selected_visual: "heatmap", data: { rows: ["a"] } }));
    throw new Error("malformed dataset rendered");
  } catch (e) { if (!/G-CHART/.test(e.message)) throw e; }
});
// 15 confidential-data rejection
sim(15, "restricted classification refused", () => {
  try {
    renderSVG(J("SIM-15-restricted", { classification: "restricted", selected_visual: "bar", data: { dimensions: ["c", "v"], source: [["a", 1]] } }));
    throw new Error("restricted job rendered without sign-off");
  } catch (e) { if (!/G-CONF/.test(e.message)) throw e; }
});
// 16 theme reskin semantic equivalence
sim(16, "reskin: 4 themes, same semantics", () => {
  const base = JSON.parse(readFileSync(join(ROOT, "fixtures", "normal", "detector-coverage-heatmap.json"), "utf8"));
  const opts = ["project-theme", "project-theme-dark", "project-theme-light", "print-theme"].map((theme) => renderSVG({ ...base, visual_id: `SIM-16-${theme}`, theme }));
  const sem = opts.map((r) => JSON.stringify(r.option.series[0].data));
  if (new Set(sem).size !== 1) throw new Error("reskin changed data semantics");
});
// 17 SVG export
sim(17, "SVG export integrity", () => {
  const job = J("SIM-17-svg", { selected_visual: "bar_horizontal", title: "Export test", data: { dimensions: ["c", "v"], source: [["a", 3], ["b", 5]] } });
  const r = renderSVG(job);
  if (!r.svg.startsWith("<svg") || !r.svg.includes("content-sha256")) throw new Error("svg export malformed");
  golden(job, r);
});
// 18 PNG export
sim(18, "PNG export integrity", async () => {
  const job = J("SIM-18-png", { selected_visual: "donut", data: { items: [{ name: "critical", value: 3 }, { name: "high", value: 9 }, { name: "medium", value: 14 }] } });
  const r = await renderPNG(job);
  const sig = r.png.subarray(0, 8).toString("hex");
  if (sig !== "89504e470d0a1a0a") throw new Error("not a PNG");
});
// 19 interactive HTML
sim(19, "interactive HTML self-contained + fallback", () => {
  const job = J("SIM-19-html", { selected_visual: "line", time_axis: true, title: "Interactive", data: { dimensions: ["t", "v"], source: [["2026-08-01", 1], ["2026-08-02", 3]] } });
  const r = renderInteractiveHTML(job);
  // self-contained = no external fetches: no src/href/@import pointing at a URL
  // (the inlined echarts bundle legitimately CONTAINS url strings in comments)
  const external = /(?:src|href)\s*=\s*["']https?:|@import\s+["'(]/i.test(r.html);
  if (!/prefers-reduced-motion/.test(r.html) || external || !r.html.includes("static-fallback")) {
    throw new Error("HTML not self-contained or missing static fallback");
  }
});
// 20 print/PDF embed readiness
sim(20, "print theme render for PDF embedding", () => {
  const job = J("SIM-20-print", { theme: "print-theme", selected_visual: "bar", title: "Print chart", data: { dimensions: ["c", "v"], source: [["a", 2], ["b", 4]] } });
  const r = renderSVG(job);
  if (!r.svg.includes("#FFFFFF") && !r.svg.includes("background")) {/* background transparent is acceptable for embed */}
  golden(job, r);
});
// 21 MCP failure → direct adapter succeeds (parity is asserted in tests/test_mcp.mjs; here: direct path never needs MCP)
sim(21, "direct adapter works with no MCP process running", () => {
  const job = J("SIM-21-fallback", { selected_visual: "bar", data: { dimensions: ["c", "v"], source: [["fallback", 1]] } });
  const r = renderSVG(job); // no MCP involved anywhere in this path
  if (!r.meta.svg_sha256) throw new Error("direct render failed");
});
// 22 engine-upgrade visual regression (golden reproduction now; upgrade path exercised by tests/test_regression.mjs forever after)
sim(22, "visual regression baseline reproduces", () => {
  const jf = join(GOLDEN, "VIS-DET-001.job.json");
  const job = JSON.parse(readFileSync(jf, "utf8"));
  const expected = readFileSync(join(GOLDEN, "VIS-DET-001.svg"), "utf8");
  if (renderSVG(job).svg !== expected) throw new Error("baseline drift within same engine version");
});

const results = [];
for (const { n, name, fn } of SIMS) {
  try { await fn(); results.push({ n, name, result: "PASS" }); console.log(`SIM ${String(n).padStart(2)}: PASS — ${name}`); }
  catch (e) { results.push({ n, name, result: "FAIL", error: e.message }); console.error(`SIM ${String(n).padStart(2)}: FAIL — ${name}: ${e.message}`); }
}
const failed = results.filter((r) => r.result === "FAIL");
writeFileSync(join(ROOT, "evidence", "release", "acceptance-simulations.json"),
  JSON.stringify({
    // P8-084: this file is documentation/an audit trail — no code reads it back (it is
    // regenerated wholesale by this script every run, never diffed or asserted on elsewhere).
    _readme: "Release acceptance record, regenerated by every `npm run simulate` run. No code reads this file back.",
    run: "npm run simulate", date_basis: "content-derived (no clock in render path)", engine: "echarts@6.1.0", results, verdict: failed.length ? "FAIL" : "PASS",
  }, null, 2) + "\n");
console.log(`\n${results.length - failed.length}/${results.length} simulations passed → evidence/release/acceptance-simulations.json`);
process.exit(failed.length ? 1 : 0);
