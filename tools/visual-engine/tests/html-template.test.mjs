import { test } from "node:test";
import assert from "node:assert/strict";
import { interactiveHTML } from "../adapters/echarts/html-template.mjs";
// validateVisualJob/VisualJobError are imported here (not just interactiveHTML) for the
// CSS-injection section appended at the end of this file -- see that section's header
// comment for why its validate.mjs counter-examples live in this file instead of
// tests/gates.test.mjs, which is validate.mjs's natural test home.
import { validateVisualJob, VisualJobError } from "../adapters/echarts/validate.mjs";

/**
 * Adversarial coverage for two defects fixed together:
 *
 *  1. GHAS js/incomplete-html-attribute-sanitization — the `esc()` helper (still used for
 *     HTML *text* nodes) escapes only & < > and cannot protect an HTML *attribute* value: a
 *     title containing a literal `"` can close the `aria-label="..."` attribute early and
 *     inject new attributes/elements. Fixed with a new `escapeAttr` used at that one sink.
 *
 *  2. Script-block breakout — job/option/theme strings reach the chart-init `<script>` body
 *     via `JSON.stringify(...)`, which does not escape `<`. A string containing the literal
 *     text `</script>` therefore terminates the real script element early; everything after
 *     it is then parsed as markup, and "attribute escaping alone leaves this exploitable path
 *     open". Fixed by escaping `<`/`>` (and, defensively, U+2028/U+2029) inside
 *     the JSON text before embedding it, which round-trips through JSON.parse unchanged.
 *
 * Every assertion below reads the RENDERED OUTPUT STRING `interactiveHTML(...)` actually
 * produces — never the source of the fix — so this file is meaningful run against either the
 * vulnerable or the fixed version of html-template.mjs (failing-first evidence).
 */

function baseArgs(overrides = {}) {
  return {
    job: {
      title: "Detector coverage",
      reader_question: "How does coverage break down?",
      text_summary: "Coverage summary text.",
      ...overrides.job,
    },
    option: overrides.option ?? { series: [{ name: "s1", type: "bar", data: [1, 2, 3] }] },
    theme: overrides.theme ?? { textStyle: { color: "#EAEEF5" }, title: { subtextStyle: { color: "#8A96AE" } } },
    themeName: overrides.themeName ?? "project-theme",
    width: overrides.width ?? 640,
    height: overrides.height ?? 400,
    staticSVG: overrides.staticSVG ?? '<svg role="img"></svg>',
    versions: overrides.versions ?? { echarts: "6.1.0" },
    ground: overrides.ground ?? "#060608",
  };
}

// Pulls the aria-label attribute's raw text out of the rendered <div id="chart" ...> tag. A
// correctly attribute-escaped value can never contain a literal '"', so this regex always
// captures the FULL escaped value; on the vulnerable code path a hostile '"' closes the
// attribute early and the capture is truncated instead of matching the whole hostile string —
// which the assertions below catch.
function ariaLabelValue(html) {
  const m = html.match(/aria-label="([^"]*)"/);
  assert.ok(m, "aria-label attribute not found in rendered output");
  return m[1];
}

// Isolates the inline chart-init <script> body (the one containing the JSON.stringify embeds)
// from the rest of the document, independent of what the (huge, vendored) inlined ECharts
// library text in the FIRST <script> tag happens to contain.
function chartInitScriptBody(html) {
  // nosemgrep: javascript.lang.security.audit.unknown-value-with-script-tag.unknown-value-with-script-tag -- this helper is the
  // INVERSE of what that rule guards. The rule warns about interpolating an unknown value INTO a
  // <script> tag; this function renders nothing. It takes ALREADY-RENDERED output and slices out
  // the chart-init script body so the assertions below can prove a hostile value could NOT break
  // out of it. Suppressed here, at the three call sites the rule flags, rather than repo-wide:
  // the same rule firing on production rendering code would be a real finding and must stay loud.
  const start = html.indexOf("(function () {");
  const end = html.indexOf("\n</script>\n<!-- generated-by", start);
  assert.ok(start !== -1 && end !== -1, "could not locate the chart-init <script> body");  // nosemgrep: javascript.lang.security.audit.unknown-value-with-script-tag.unknown-value-with-script-tag
  return html.slice(start, end);
}

test("aria-label: a double-quote in the title cannot close the attribute", () => {
  const hostile = 'foo" onmouseover="alert(1)" x="bar';
  const html = interactiveHTML(baseArgs({ job: { title: hostile, reader_question: "" } }));
  const value = ariaLabelValue(html);
  assert.equal(value, "foo&quot; onmouseover=&quot;alert(1)&quot; x=&quot;bar");
  assert.ok(!value.includes('"'), "a raw double-quote survived into the attribute value");
  assert.ok(!html.includes('aria-label="foo" onmouseover='), "the hostile string broke out of the aria-label attribute");
});

test("aria-label: <, >, ', & and a backtick are each escaped in attribute position", () => {
  const cases = [
    ["&", "a&b", "a&amp;b"],
    ["<", "a<b", "a&lt;b"],
    [">", "a>b", "a&gt;b"],
    ["'", "a'b", "a&#39;b"],
    ["`", "a`b", "a&#96;b"], // backtick — IE/legacy unquoted-attribute parsing treats it as a quote
  ];
  for (const [label, input, expected] of cases) {
    const html = interactiveHTML(baseArgs({ job: { title: input, reader_question: "" } }));
    assert.equal(ariaLabelValue(html), expected, `character ${JSON.stringify(label)} not escaped correctly in attribute position`);
  }
});

test("aria-label: & is escaped FIRST, so it is never double-escaped", () => {
  // The input must contain BOTH a raw '<' and a literal "&lt;" for the two orders to differ.
  // This assertion previously fed "&lt;" alone, which carries no raw '<' at
  // all, so '&'-first and '&'-last both yield "&amp;lt;" -- it passed under the inverse edit and
  // could never fail for the reason its name gives.
  //
  //   input            a<&lt;b
  //   '&' FIRST  ->  '&'->&amp;   a<&amp;lt;b   then '<'->&lt;   a&lt;&amp;lt;b   <- correct
  //   '&' LAST   ->  '<'->&lt;    a&lt;&lt;b     then '&'->&amp;  a&amp;lt;&amp;lt;b
  //
  // The '&' introduced by the '<' replacement is what gets double-escaped in the wrong order.
  const html = interactiveHTML(baseArgs({ job: { title: "a<&lt;b", reader_question: "" } }));
  assert.equal(ariaLabelValue(html), "a&lt;&amp;lt;b");
});

test("aria-label: a raw '<' from a hostile title never survives into attribute position", () => {
  const html = interactiveHTML(baseArgs({ job: { title: "<b>bold</b>", reader_question: "" } }));
  const value = ariaLabelValue(html);
  assert.ok(!value.includes("<"), "a raw '<' survived into the aria-label attribute value");
  assert.equal(value, "&lt;b&gt;bold&lt;/b&gt;");
});

test("script embed: a series name of </script><img src=x onerror=1> cannot close the data script", () => {
  const hostileSeriesName = "</script><img src=x onerror=1>";
  const html = interactiveHTML(baseArgs({
    option: { series: [{ name: hostileSeriesName, type: "bar", data: [1, 2, 3] }] },
  }));
  const body = chartInitScriptBody(html);
  assert.ok(!/<\/script/i.test(body), "the injected series name closed the chart-init <script> element early");  // nosemgrep: javascript.lang.security.audit.unknown-value-with-script-tag.unknown-value-with-script-tag

  // The value must still round-trip through JSON.parse unchanged — escaping must be
  // correctness-preserving, not merely destructive.
  const m = body.match(/chart\.setOption\((.*)\);/);
  assert.ok(m, "could not locate the chart.setOption(...) call in the chart-init script body");
  const roundTripped = JSON.parse(m[1]);
  assert.equal(roundTripped.series[0].name, hostileSeriesName);
});

test("script embed: themeName and theme are also protected (registerTheme + echarts.init calls)", () => {
  const html = interactiveHTML(baseArgs({
    themeName: "</script><script>alert(1)</script>",
    theme: { textStyle: { color: "</script><img src=x onerror=2>" } },
  }));
  const body = chartInitScriptBody(html);
  assert.ok(!/<\/script/i.test(body), "themeName or theme closed the chart-init <script> element early");  // nosemgrep: javascript.lang.security.audit.unknown-value-with-script-tag.unknown-value-with-script-tag

  // registerTheme(themeName, theme) and echarts.init(el, themeName, ...) both embed themeName —
  // neither call site may be left on the unescaped path.
  assert.ok(body.includes("echarts.registerTheme("), "registerTheme call missing from script body");
  assert.ok(body.includes("echarts.init("), "echarts.init call missing from script body");
});

test("html output is otherwise unchanged in shape (self-contained, static fallback present)", () => {
  const html = interactiveHTML(baseArgs());
  assert.ok(html.includes("static-fallback"));
  assert.ok(html.includes("prefers-reduced-motion"));
  assert.ok(html.startsWith("<!DOCTYPE html>"));
});

/**
 * CSS-context HTML injection via a non-numeric width/height (pre-existing, not caused by the
 * attribute/script-escaping fix above -- found while independently verifying that fix).
 *
 * `interactiveHTML(...)` interpolated `width`/`height` directly into the <style> block with NO
 * escaping at all:
 *
 *   main { max-width: ${width + 48}px; ... }
 *   #chart { width: ${width}px; height: ${height}px; ... }
 *
 * validate.mjs's G-SIZE range check (`w < minWidth || w > maxWidth || ...`) uses `<`/`>`, and
 * EVERY such comparison is `false` for `NaN` -- so a non-numeric width/height (a STRING) passed
 * validation untouched. Proof:
 *
 *   width: "0px} </style><svg onload=alert(1)>"
 *
 * rendered that string raw inside the <style> element, closing it and injecting markup. Fixed in
 * two layers: validate.mjs now requires Number.isFinite() before the range comparison (G-SIZE),
 * and html-template.mjs no longer trusts the validator alone (defence in depth, the same stance
 * already taken for the attribute and script sinks above) -- it coerces width/height to numbers
 * and fails closed on a non-finite value, and gives the CSS-interpolated colour values
 * (ground/theme.textStyle.color/theme.title.subtextStyle.color) a narrow CSS-value allowlist
 * rather than (incorrectly) reusing escapeAttr, which does not neutralise a CSS sink.
 *
 * The validate.mjs counter-examples near the end of this section live HERE rather than in
 * tests/gates.test.mjs -- validate.mjs's natural test home (it already imports
 * validateVisualJob/VisualJobError and covers every other gate, including G-SIZE) -- because
 * gates.test.mjs is outside this piece's touchable file set for this task.
 */

const CSS_INJECTION_PAYLOAD = "0px} </style><svg onload=alert(1)>";

test("CSS injection via width: a non-numeric width is rejected before it can reach the <style> block", () => {
  let html;
  try {
    html = interactiveHTML(baseArgs({ width: CSS_INJECTION_PAYLOAD }));
  } catch (e) {
    // The chosen fix fails CLOSED: interactiveHTML refuses to build any HTML at all from a
    // non-finite width, so there is no rendered output for the injection to appear in --
    // strictly stronger than merely sanitizing it. Still assert the refusal is the one this
    // fix installs (not some unrelated crash) and names the offending field.
    assert.match(e.message, /width\/height must be finite numbers/i, `unexpected throw: ${e.message}`);
    return;
  }
  // Written to hold even if a future revision changes the strategy from "throw" to
  // "coerce-and-render": the injection must still be impossible either way.
  assert.ok(!html.includes("</style><svg"), "the hostile width closed the <style> block and injected markup");
  assert.ok(!/<svg[^>]*onload=/i.test(html), "the hostile width injected a live onload handler");
});

test("CSS injection via height: the same hostile shape through height is rejected too", () => {
  try {
    interactiveHTML(baseArgs({ height: CSS_INJECTION_PAYLOAD }));
    assert.fail("expected interactiveHTML to reject a non-numeric height");
  } catch (e) {
    assert.match(e.message, /width\/height must be finite numbers/i);
  }
});

test("CSS injection via width: NaN, Infinity and -Infinity are rejected too, not just strings", () => {
  for (const bad of [NaN, Infinity, -Infinity]) {
    assert.throws(
      () => interactiveHTML(baseArgs({ width: bad })),
      /width\/height must be finite numbers/i,
      `width=${String(bad)} must be rejected`,
    );
  }
});

test("CSS injection via colour: a hostile ground/ink/inkMuted value cannot escape the <style> block and falls back to the default", () => {
  const cases = [
    ["ground", { ground: CSS_INJECTION_PAYLOAD }, "#060608"],
    [
      "theme.textStyle.color (ink)",
      { theme: { textStyle: { color: CSS_INJECTION_PAYLOAD }, title: { subtextStyle: { color: "#8A96AE" } } } },
      "#EAEEF5",
    ],
    [
      "theme.title.subtextStyle.color (inkMuted)",
      { theme: { textStyle: { color: "#EAEEF5" }, title: { subtextStyle: { color: CSS_INJECTION_PAYLOAD } } } },
      "#8A96AE",
    ],
  ];
  for (const [label, overrides, expectedFallback] of cases) {
    const html = interactiveHTML(baseArgs(overrides));
    assert.ok(!html.includes(CSS_INJECTION_PAYLOAD), `[${label}] the hostile colour value was interpolated raw`);
    assert.ok(!html.includes("</style><svg"), `[${label}] the hostile colour value closed the <style> block`);
    assert.ok(!/<svg[^>]*onload=/i.test(html), `[${label}] the hostile colour value injected a live onload handler`);
    assert.ok(html.includes(expectedFallback), `[${label}] expected the safe default colour ${expectedFallback} instead`);
  }
});

test("CSS colour guard: a legitimate document-theme var(--custom-property) value is preserved, not overwritten", () => {
  // RESKINNING_AND_THEME_POLICY.md / theme-adapter.mjs: "document-theme" legitimately sets ink
  // and hairline values to CSS custom-property references (`var(--fg)`, `var(--mute)`) so a
  // chart inlined into a docgen document follows that document's live theme. A guard that
  // rejected this shape would silently regress that capability -- a worse bug than the one
  // being fixed (per this piece's own instructions: "a guard that breaks legitimate input is a
  // worse bug than the one it fixes").
  const html = interactiveHTML(baseArgs({
    ground: "var(--fg)",
    theme: { textStyle: { color: "var(--fg)" }, title: { subtextStyle: { color: "var(--mute)" } } },
  }));
  assert.ok(html.includes("background: var(--fg)"), "a legitimate var(--fg) ground value was replaced by the guard");
  assert.ok(html.includes("color: var(--fg)"), "a legitimate var(--fg) ink value was replaced by the guard");
  assert.ok(html.includes("color: var(--mute)"), "a legitimate var(--mute) inkMuted value was replaced by the guard");
});

test("regression guard: normal numeric width/height and normal #rrggbb colours render correctly, unchanged", () => {
  const html = interactiveHTML(baseArgs());
  // baseArgs() defaults: width 640, height 400, ground #060608, ink #EAEEF5, inkMuted #8A96AE.
  assert.ok(html.includes("max-width: 688px;"), "width + 48 for `main` no longer computes correctly (640+48)");
  assert.ok(html.includes("width: 640px; height: 400px;"), "#chart width/height no longer render the plain numeric values");
  assert.ok(html.includes("background: #060608; color: #EAEEF5;"), "ground/ink defaults were altered by the guard");
  assert.ok(html.includes("color: #8A96AE;"), "inkMuted default was altered by the guard");
});

// ---------------------------------------------------------------------------------------------
// validate.mjs G-SIZE counter-examples (see the section header above for why these live here).
// ---------------------------------------------------------------------------------------------

const VALID_JOB_FOR_G_SIZE = {
  visual_id: "T-css-injection-width",
  reader_question: "Does width validation reject a non-numeric value?",
  classification: "internal",
  selected_visual: "bar",
  data: { dimensions: ["c", "v"], source: [["a", 1], ["b", 2]] },
};

test("validate.mjs G-SIZE: a non-numeric width is now REJECTED, not silently coerced through NaN", () => {
  assert.throws(
    () => validateVisualJob({ ...VALID_JOB_FOR_G_SIZE, width: CSS_INJECTION_PAYLOAD }),
    (err) => {
      assert.ok(err instanceof VisualJobError, "expected a VisualJobError");
      assert.equal(err.gate, "G-SIZE");
      assert.match(err.message, /finite number/);
      return true;
    },
  );
});

test("validate.mjs G-SIZE: a non-numeric height is rejected too", () => {
  assert.throws(
    () => validateVisualJob({ ...VALID_JOB_FOR_G_SIZE, height: CSS_INJECTION_PAYLOAD }),
    (err) => err instanceof VisualJobError && err.gate === "G-SIZE" && /finite number/.test(err.message),
  );
});

test("validate.mjs G-SIZE: NaN, Infinity and -Infinity width/height are rejected too, not just strings", () => {
  for (const bad of [NaN, Infinity, -Infinity]) {
    assert.throws(
      () => validateVisualJob({ ...VALID_JOB_FOR_G_SIZE, width: bad }),
      /finite number/,
      `width=${String(bad)} must be rejected`,
    );
    assert.throws(
      () => validateVisualJob({ ...VALID_JOB_FOR_G_SIZE, height: bad }),
      /finite number/,
      `height=${String(bad)} must be rejected`,
    );
  }
});

test("validate.mjs G-SIZE: a normal numeric width/height still passes (regression guard)", () => {
  const r = validateVisualJob({ ...VALID_JOB_FOR_G_SIZE, width: 640, height: 400 });
  assert.equal(r.ok, true);
  assert.equal(r.job.width, 640);
  assert.equal(r.job.height, 400);
});

test("validate.mjs G-SIZE: default width/height (no width/height supplied) still pass", () => {
  const r = validateVisualJob({ ...VALID_JOB_FOR_G_SIZE });
  assert.equal(r.ok, true);
  assert.equal(r.job.width, 800);
  assert.equal(r.job.height, 480);
});
