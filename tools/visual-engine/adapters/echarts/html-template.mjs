/**
 * Self-contained interactive HTML export.
 *
 * Docgen law carried over: zero external references — ECharts is inlined from
 * the pinned node_modules copy, the theme is inlined, no CDN, no @import.
 * Reduced-motion users and print get the static SVG fallback via
 * `prefers-reduced-motion` / `print` media queries (same pattern as docgen's
 * layered_workflow dual-variant SVG).
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));

let _echartsDist;
function echartsDist() {
  if (!_echartsDist) {
    _echartsDist = readFileSync(join(HERE, "..", "..", "node_modules", "echarts", "dist", "echarts.min.js"), "utf8");
  }
  return _echartsDist;
}

const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// HTML *attribute*-value escaping — a strict superset of `esc` (which only ever protects HTML
// *text* nodes). Order matters: '&' MUST be replaced first, or the entities the later
// replacements produce (e.g. the '&' in "&quot;") would themselves get re-escaped into
// "&amp;quot;". Fixes GHAS js/incomplete-html-attribute-sanitization: `esc`
// alone cannot protect a double-quoted attribute value — a literal '"' in the input closes the
// attribute early and lets an attacker inject new attributes (e.g. `" onmouseover=alert(1) x="`).
const escapeAttr = (s) => String(s ?? "")
  .replace(/&/g, "&amp;")
  .replace(/</g, "&lt;")
  .replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;")
  .replace(/'/g, "&#39;")
  .replace(/`/g, "&#96;"); // IE/legacy unquoted-attribute parsing treats a backtick as a quote too

// Safe JSON embedding inside an inline <script> body. JSON.stringify() does not escape '<', so a
// string value containing the literal text "</script>" terminates the real script element early
// and everything the document has after that point is then parsed as markup — attribute escaping
// (escapeAttr, above) does not close this path; it is a separate sink and needs its own fix.
// Escaping '<' and '>' as \u-escapes is correctness-preserving: a JSON string
// "<" round-trips through JSON.parse to the identical '<' character, so chart data/text is
// byte-for-byte unchanged. '>' is escaped too, defeating a "-->"-style HTML-comment breakout in
// the same script context ('&' does not need escaping for that: raw text <script> content is
// never HTML-entity-decoded by the parser, only scanned for "</script"). U+2028/U+2029
// (LINE/PARAGRAPH SEPARATOR) are valid inside a JSON string but are not escaped by
// JSON.stringify and have historically broken raw script-literal parsing, so they are
// neutralised the same way here, defensively.
const jsonForScript = (value) => JSON.stringify(value)
  .replace(/</g, "\\u003C")
  .replace(/>/g, "\\u003E")
  .replace(/\u2028/g, "\\u2028")
  .replace(/\u2029/g, "\\u2029");

// CSS-value guard for the colour tokens interpolated into the <style> block (bg/ink/inkMuted,
// below). These come from the theme object -- engine-computed today via theme-adapter.mjs, not
// job-controlled -- but this template must stay safe even if a future caller reaches it with an
// unvalidated or job-influenced theme (defence in depth: the same stance already taken here for
// the attribute sink via escapeAttr and the script sink via jsonForScript). HTML-entity escaping
// does NOT neutralise a CSS sink -- `&#39;` etc. are never decoded inside a <style> element -- so
// the danger in THIS sink is a bare "}" or "</style>" breaking the block open, not an unescaped
// quote. The correct control for a CSS value is therefore an ALLOWLIST of the value shapes CSS
// itself accepts for a colour, not an escaper. Chosen rule: accept only
//   - a hex colour: #rgb, #rgba, #rrggbb, #rrggbbaa
//   - rgb()/rgba() or hsl()/hsla() with digits/dot/percent/comma/space arguments only
//   - var(--custom-ident) -- REQUIRED, not decorative: "document-theme" (RESKINNING_AND_THEME_
//     POLICY.md) legitimately sets textStyle.color/subtextStyle.color to "var(--fg)"/"var(--mute)"
//     so an inlined chart follows its host docgen document's live theme; a guard that rejected
//     this would silently break that theme's HTML export (a worse bug than the one being fixed)
//   - a bare CSS named colour / keyword (letters only), which also covers "transparent"
// Anything else -- including every character sequence needed to close the block ("}", "<", ";",
// whitespace outside a function's argument list) -- falls back to the caller's supplied default.
const CSS_COLOR_RE =
  /^(#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})|rgba?\(\s*[\d.]+%?(?:\s*,\s*[\d.]+%?){2,3}\s*\)|hsla?\(\s*[\d.]+(?:\s*,\s*[\d.]+%){2}(?:\s*,\s*[\d.]+%?)?\s*\)|var\(\s*--[a-zA-Z0-9_-]+\s*\)|[a-zA-Z]+)$/;

function safeCssColor(value, fallback) {
  if (value === undefined || value === null) return fallback;
  const s = String(value);
  return CSS_COLOR_RE.test(s) ? s : fallback;
}

export function interactiveHTML({ job, option, theme, themeName, width, height, staticSVG, versions, ground }) {
  // OG-50: the page chrome follows the theme instead of being baked dark.
  //
  // The chart SVG has always been theme-correct — it is generated FROM `theme`. What was hardcoded
  // was everything around it: a `#060608` body, `#EAEEF5` ink and a `#8A96AE` caption, on every
  // export. A light-theme interactive HTML therefore framed light-theme ink in near-black, and the
  // defect was invisible in the SVG path and invisible in source.
  //
  // Ink comes from the SAME theme object the chart is rendered with, so the two cannot disagree;
  // the ground is passed in because `theme.backgroundColor` is deliberately "transparent" for
  // every non-print theme (a chart inherits its host's ground) and a standalone page has no host.
  // Each is passed through safeCssColor() (defined above) so a value that cannot be a legitimate
  // CSS colour never reaches the <style> block raw -- see that function's comment for the rule.
  const bg = safeCssColor(ground, "#060608");
  const ink = safeCssColor(theme?.textStyle?.color, "#EAEEF5");
  const inkMuted = safeCssColor(theme?.title?.subtextStyle?.color, "#8A96AE");

  // Defence in depth: validate.mjs's G-SIZE gate rejects a non-numeric
  // width/height before a job reaches this function -- but this template must not rely SOLELY on
  // that validator having run (same stance as the guard above). `<`/`>` range checks are false for
  // NaN, so a non-numeric width/height previously interpolated raw into the <style> block below,
  // closing it early (CSS-context HTML injection). Coerce to numbers at the point of use and fail
  // closed -- refuse to render -- rather than emit an unsafe or nonsensical value.
  const safeWidth = Number(width);
  const safeHeight = Number(height);
  if (!Number.isFinite(safeWidth) || !Number.isFinite(safeHeight)) {
    throw new Error(
      `interactiveHTML: width/height must be finite numbers (got width=${JSON.stringify(width)}, height=${JSON.stringify(height)})`,
    );
  }

  const scheme = themeName === "project-theme-light" || themeName === "print-theme" ? "light" : "dark";
  const interactiveOption = { ...option, animation: true, animationDuration: 400 };
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(job.title ?? "visual")}</title>
<style>
  :root { color-scheme: ${scheme}; }
  body { margin: 0; background: ${bg}; color: ${ink};
         font-family: "Inter", system-ui, -apple-system, sans-serif; }
  main { max-width: ${safeWidth + 48}px; margin: 24px auto; padding: 0 16px; }
  h1 { font-family: "Space Grotesk", system-ui, sans-serif; font-size: 18px; font-weight: 600; margin: 0 0 4px; }
  p.q { color: ${inkMuted}; font-size: 13px; margin: 0 0 16px; }
  #chart { width: ${safeWidth}px; height: ${safeHeight}px; max-width: 100%; }
  .static-fallback { display: none; }
  figcaption { color: ${inkMuted}; font-size: 12px; margin-top: 12px; }
  @media (prefers-reduced-motion: reduce), print {
    #chart { display: none; }
    .static-fallback { display: block; }
  }
</style>
</head>
<body>
<main>
  <h1>${esc(job.title ?? "")}</h1>
  <p class="q">${esc(job.reader_question ?? "")}</p>
  <figure>
    <div id="chart" role="img" aria-label="${escapeAttr(job.title ?? job.reader_question ?? "chart")}"></div>
    <div class="static-fallback">${staticSVG}</div>
    <figcaption>${esc(job.text_summary ?? "")}</figcaption>
  </figure>
</main>
<script>${echartsDist()}</script>
<script>
  (function () {
    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return; // static fallback is already visible via CSS
    echarts.registerTheme(${jsonForScript(themeName)}, ${jsonForScript(theme)});
    var chart = echarts.init(document.getElementById("chart"), ${jsonForScript(themeName)}, { renderer: "canvas" });
    chart.setOption(${jsonForScript(interactiveOption)});
    window.addEventListener("resize", function () { chart.resize(); });
  })();
</script>
<!-- generated-by visual-engine · echarts@${versions.echarts} inlined (self-contained, no CDN) -->
</body>
</html>
`;
}
