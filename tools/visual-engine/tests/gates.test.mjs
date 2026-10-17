import { test } from "node:test";
import assert from "node:assert/strict";
import { validateVisualJob, VisualJobError } from "../adapters/echarts/validate.mjs";

const base = {
  visual_id: "T-1", reader_question: "test question?", classification: "internal",
  selected_visual: "bar", data: { dimensions: ["c", "v"], source: [["a", 1], ["b", 2]] },
};

test("valid job passes", () => {
  const r = validateVisualJob(base);
  assert.equal(r.ok, true);
});

test("G-STRUCT: missing reader_question fails", () => {
  assert.throws(() => validateVisualJob({ ...base, reader_question: undefined }), /G-STRUCT/);
});

// P8-081: schemas/visual-job.schema.json declares `visual_id.pattern` and `reader_question.minLength`
// but nothing enforced them (no jsonschema/ajv in this repo) — validateVisualJob() only checked
// presence/type. These counter-examples pin the code-level enforcement added for that finding.
test("G-STRUCT: visual_id must match the safe-id pattern (schemas/visual-job.schema.json)", () => {
  assert.throws(() => validateVisualJob({ ...base, visual_id: "bad id with spaces" }), /G-STRUCT/);
  // the widest input that must still be REFUSED: any single disallowed character, including the
  // ones a path-traversal attempt would need, since visual_id becomes a filename downstream
  // (cli.mjs/server.mjs `.replace(/[^A-Za-z0-9._-]/g, "_")` — this gate now refuses before that
  // silent substitution ever runs).
  assert.throws(() => validateVisualJob({ ...base, visual_id: "../etc/passwd" }), /G-STRUCT/);
  // the widest input that must still PASS: every character class the pattern allows, in one id.
  assert.equal(validateVisualJob({ ...base, visual_id: "A.b_9-Z" }).ok, true);
});

test("G-STRUCT: reader_question needs at least 8 characters (schemas/visual-job.schema.json)", () => {
  assert.throws(() => validateVisualJob({ ...base, reader_question: "short?" }), /G-STRUCT/); // 6 chars
  assert.throws(() => validateVisualJob({ ...base, reader_question: "7chars?" }), /G-STRUCT/); // boundary: 7 chars, still under
  assert.equal(validateVisualJob({ ...base, reader_question: "8 chars?" }).ok, true); // boundary: exactly 8, must pass
});

test("G-STRUCT: unknown visual routes reader to routing policy", () => {
  assert.throws(() => validateVisualJob({ ...base, selected_visual: "hologram" }), /ENGINE_ROUTING_POLICY/);
});

test("G-CONF: restricted refused by default, allowed with explicit sign-off flag", () => {
  assert.throws(() => validateVisualJob({ ...base, classification: "restricted" }), /G-CONF/);
  const r = validateVisualJob({ ...base, classification: "restricted" }, { allowRestricted: true });
  assert.equal(r.ok, true);
});

test("NO_CHART is first-class and requires a reason", () => {
  assert.throws(() => validateVisualJob({ ...base, selected_visual: "none" }), /no_chart_reason/);
  const r = validateVisualJob({ ...base, selected_visual: "none", no_chart_reason: "two exact numbers" });
  assert.equal(r.no_chart, true);
});

test("G-SEC: script tag, js url, function literal, handler all rejected", () => {
  for (const evil of ["<script>x</script>", "javascript:alert(1)", "function(){}", "x => {steal()}", "onload=x"]) {
    assert.throws(() => validateVisualJob({ ...base, title: evil }), /G-SEC/, evil);
  }
});

test("G-SEC: external URL rejected in option-bound fields", () => {
  assert.throws(() => validateVisualJob({ ...base, title: "see https://evil.example" }), /G-SEC/);
});

test("G-SIZE: cell cap and dimension caps enforced", () => {
  const big = { ...base, data: { dimensions: ["c", "v"], source: Array.from({ length: 26000 }, (_, i) => [String(i), i, i]) } };
  assert.throws(() => validateVisualJob(big), /G-SIZE/);
  assert.throws(() => validateVisualJob({ ...base, width: 9000 }), /G-SIZE/);
});

test("G-CHART: pie >6 slices fails (docgen law)", () => {
  const pie = { ...base, selected_visual: "pie", data: { items: Array.from({ length: 7 }, (_, i) => ({ name: `s${i}`, value: 1 })) } };
  assert.throws(() => validateVisualJob(pie), /G-CHART/);
});

test("G-CHART: negative bar values need allow_negative (zero-baseline law)", () => {
  const j = { ...base, data: { dimensions: ["c", "v"], source: [["a", -5]] } };
  assert.throws(() => validateVisualJob(j), /G-CHART/);
  assert.equal(validateVisualJob({ ...j, allow_negative: true }).ok, true);
});

test("G-CHART: sankey conservation — dangling endpoint and zero flow fail", () => {
  const s = (links) => ({ ...base, selected_visual: "sankey", data: { nodes: [{ name: "a" }, { name: "b" }], links } });
  assert.throws(() => validateVisualJob(s([{ source: "a", target: "ghost", value: 5 }])), /dangling/);
  assert.throws(() => validateVisualJob(s([{ source: "a", target: "b", value: 0 }])), /G-CHART/);
});

test("G-CHART: radar needs ≥3 axes", () => {
  const r = { ...base, selected_visual: "radar", data: { axes: [{ name: "a", max: 1 }, { name: "b", max: 1 }], series: [] } };
  assert.throws(() => validateVisualJob(r), /G-CHART/);
});

test("missing text_summary is a warning (Gate G7 pre-flag), not a failure", () => {
  const r = validateVisualJob(base);
  assert.ok(r.warnings.some((w) => w.includes("text_summary")));
});

test("VisualJobError carries its gate id", () => {
  try { validateVisualJob({ ...base, title: "<script>" }); assert.fail("should throw"); }
  catch (e) { assert.ok(e instanceof VisualJobError); assert.equal(e.gate, "G-SEC"); }
});
