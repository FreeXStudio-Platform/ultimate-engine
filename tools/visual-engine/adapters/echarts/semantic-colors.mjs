/**
 * Semantic colours for labels that already MEAN something.
 *
 * A chart whose categories are "Critical / High / Medium / Low" must not colour "Critical" blue because blue is the
 * first slot of the categorical palette. In the Atlas severity scale blue is LOW, so the chart said the opposite of
 * what its own label said — measured on two charts of a 28-chart report (a severity pie, severity-by-area bars), where Critical was
 * blue and Unrated was red.
 *
 * Rule: when at least two labels of a chart are severity / status words and they are at least half of the chart's
 * labels, those labels take the reserved severity / status colours from the theme; every other label keeps the
 * categorical palette. `job.semantic_colors === false` opts out. Pure functions; the theme supplies every colour.
 */

const SEVERITY = [
  [/^crit(ical)?$/i, (t) => t.severity.crit],
  [/^high$/i, (t) => t.severity.high],
  [/^med(ium)?$/i, (t) => t.severity["med-hi"] ?? t.severity.med],
  [/^low$/i, (t) => t.severity.low],
  [/^info(rmational)?$/i, (t) => t.severity.info],
  [/^(unrated|not rated|n\/a|none|unknown)$/i, (t) => t.semantic.inks.ash ?? t.semantic.inks.mute],
];
const STATUS = [
  [/^(proven|passed?|ok)$/i, (t) => t.semantic.verify],
  [/^(failed?|blocked)$/i, (t) => t.severity.crit],
  [/^cannot[ _-]?verify$/i, (t) => t.semantic.gold],
];

export function semanticColor(label, theme) {
  const text = String(label ?? "").trim();
  if (!text || !theme?.severity || !theme?.semantic) return null;
  for (const [re, pick] of [...SEVERITY, ...STATUS]) if (re.test(text)) return pick(theme) ?? null;
  return null;
}

/** `{ colors: (string|null)[], hits }` for a label list, or `null` when the chart should keep its palette. */
export function semanticPalette(labels, theme) {
  const colors = labels.map((l) => semanticColor(l, theme));
  const hits = colors.filter(Boolean).length;
  return hits >= 2 && hits * 2 >= labels.length ? { colors, hits } : null;
}
