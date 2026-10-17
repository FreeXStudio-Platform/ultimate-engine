/**
 * Readable ink on a coloured fill — decided at build time, never at hover time.
 *
 * A treemap tile, a sunburst arc and a heat-map cell each carry a label ON TOP of a palette colour. ECharts draws
 * that label in one theme-wide ink with a 2px outline in a contrasting colour (the "halo"), which on a dark theme
 * read as a thick white fringe round every letter, and on a gold tile as pale-on-pale. This module picks the label
 * ink from the fill instead: whichever of near-black and white has the higher WCAG contrast ratio.
 *
 * Pure functions, no I/O. A fill that is not a literal colour (`var(--x)`, a gradient) cannot be measured; the
 * caller gets `null` and keeps its default ink.
 */

const DARK_INK = "#0B0E14";
const LIGHT_INK = "#FFFFFF";
const PURE_BLACK = "#000000";

export function parseColor(c) {
  if (typeof c !== "string") return null;
  let m = /^#([0-9a-f]{3})$/i.exec(c.trim());
  if (m) return [...m[1]].map((h) => parseInt(h + h, 16));
  m = /^#([0-9a-f]{6})([0-9a-f]{2})?$/i.exec(c.trim());
  if (m) return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16));
  m = /^rgba?\(\s*(\d+(?:\.\d+)?)[ ,]+(\d+(?:\.\d+)?)[ ,]+(\d+(?:\.\d+)?)/i.exec(c.trim());
  if (m) return [Number(m[1]), Number(m[2]), Number(m[3])];
  return null;
}

function luminance([r, g, b]) {
  const f = (v) => { const s = v / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

export function contrastRatio(a, b) {
  const la = luminance(a);
  const lb = luminance(b);
  const [hi, lo] = la >= lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

const AA = 4.5;

/**
 * The label ink for `fill`: the brand near-black or white, whichever reads better; `null` if `fill` is not a literal
 * colour. Mid-tones are the exception: near-black and white both fall just short of WCAG AA there (the best of the two
 * peaks at about 4.4:1), so the ink steps to pure black or white, which cannot (their worst case is 4.58:1).
 */
export function inkFor(fill) {
  const rgb = parseColor(fill);
  if (!rgb) return null;
  const dark = contrastRatio(rgb, parseColor(DARK_INK));
  const light = contrastRatio(rgb, parseColor(LIGHT_INK));
  const best = dark >= light ? [DARK_INK, dark] : [LIGHT_INK, light];
  if (best[1] >= AA) return best[0];
  return contrastRatio(rgb, parseColor(PURE_BLACK)) >= contrastRatio(rgb, parseColor(LIGHT_INK)) ? PURE_BLACK : LIGHT_INK;
}

/** Linear mix of two literal colours, `t` in 0..1 toward `to`. Returns `from` unchanged if either is unparseable. */
export function mix(from, to, t) {
  const a = parseColor(from);
  const b = parseColor(to);
  if (!a || !b) return from;
  const c = a.map((v, i) => Math.round(v + (b[i] - v) * t));
  return `#${c.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

/** Interpolate a multi-stop ramp at `t` in 0..1 (same linear-RGB rule ECharts' visualMap uses). */
export function rampAt(stops, t) {
  const rgb = stops.map(parseColor);
  if (rgb.some((x) => !x)) return null;
  const x = Math.min(1, Math.max(0, t)) * (rgb.length - 1);
  const i = Math.min(rgb.length - 2, Math.floor(x));
  const f = x - i;
  const c = rgb[i].map((v, k) => Math.round(v + (rgb[i + 1][k] - v) * f));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export const INKS = { DARK_INK, LIGHT_INK, PURE_BLACK };
