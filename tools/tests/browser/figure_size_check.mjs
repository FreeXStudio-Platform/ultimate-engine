// Browser check of the figure SIZE STANDARD (FS-1 … FS-5, docs/design/FIGURE_SYSTEM.md §12) on a REAL built document.
//
//   node tools/tests/browser/figure_size_check.mjs <built.html> '<constants json>' [out-dir]
//
// The unit tests pin the arithmetic the document hands to the stylesheet and the stylesheet's text. Neither can say what
// Chromium draws: a `min()` that is valid CSS and wrong is exactly the kind of thing that passes every byte-level test and
// puts a 1150x886 diagram on a laptop screen. So this script re-implements the standard from the constants (independently of
// the stylesheet), measures every sized figure at five viewports, and compares.
//
// Exit codes: 0 = every check passed · 1 = a check failed · 3 = Playwright / a browser is not available.
/* global document, getComputedStyle */
import fs from "node:fs";
import path from "node:path";
import { launchOrSkip, checks } from "./_launch.mjs";

const FILE = path.resolve(process.argv[2]);
const STD = JSON.parse(process.argv[3]);
const OUT = process.argv[4] ? path.resolve(process.argv[4]) : null;
const { ok, finish } = checks();
const b = await launchOrSkip();

const VIEWPORTS = [
  { w: 1440, h: 900 }, // the reference laptop: the case the standard was written for
  { w: 1920, h: 1080 },
  { w: 2560, h: 1440 }, // a big monitor must not make the figures balloon
  { w: 1024, h: 768 },
  { w: 390, h: 844 }, // a phone: the column is the limit, nothing may overflow the page
];

/** The standard, re-derived from the constants. `container` is the frame's content width. */
function expectedWidth({ fw, fh, up, container, vh }) {
  const fitH = Math.min((STD.fitVh / 100) * vh, STD.fitH);
  const tall = fh >= STD.tall * fw - 1e-9;
  let w = Math.min(container, STD.maxW, fw * up);
  if (!tall) w = Math.min(w, Math.max((fitH * fw) / fh, fw * STD.minScale));
  return w;
}

for (const vp of VIEWPORTS) {
  const page = await b.newPage({ viewport: { width: vp.w, height: vp.h } });
  await page.goto("file://" + FILE);
  await page.waitForTimeout(250);
  const figs = await page.evaluate(() => [...document.querySelectorAll("figure.doc-figure")].map((f) => {
    const wrap = f.querySelector(".svgwrap");
    const svg = wrap.querySelector("svg");
    const cs = getComputedStyle(wrap);
    const r = svg.getBoundingClientRect();
    const sized = wrap.classList.contains("svgwrap--sized");
    return {
      id: f.id, kind: f.getAttribute("data-fig-kind-name") || "", sized, tall: wrap.classList.contains("svgwrap--tall"),
      fw: Number(wrap.style.getPropertyValue("--fw")), fh: Number(wrap.style.getPropertyValue("--fh")), up: Number(wrap.style.getPropertyValue("--up")),
      container: wrap.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight),
      w: r.width, h: r.height, grid: cs.backgroundImage !== "none",
    };
  }));
  const tag = `${vp.w}x${vp.h}`;
  ok(`${tag}: the document has figures to measure`, figs.length >= 3, `${figs.length} figures`);
  for (const f of figs.filter((x) => x.sized)) {
    const want = expectedWidth({ ...f, vh: vp.h });
    ok(`${tag}: ${f.id} is drawn at the width the standard asks for`, Math.abs(f.w - want) <= 1.5, `want ${want.toFixed(1)} got ${f.w.toFixed(1)} (design ${f.fw}x${f.fh}, up ${f.up})`);
    ok(`${tag}: ${f.id} keeps its aspect ratio`, Math.abs(f.h / f.w - f.fh / f.fw) <= 0.01, `${f.w.toFixed(0)}x${f.h.toFixed(0)}`);
    ok(`${tag}: ${f.id} is never wider than the figure ceiling or its column`, f.w <= STD.maxW + 1 && f.w <= f.container + 1);
    if (!f.tall && vp.w >= 1024) {
      const cap = Math.min((STD.fitVh / 100) * vp.h, STD.fitH);
      const scale = f.w / f.fw;
      ok(`${tag}: ${f.id} fits one screen unless that would shrink it past the floor`, f.h <= cap + 1.5 || scale <= STD.minScale + 0.005, `h ${f.h.toFixed(0)} cap ${cap.toFixed(0)} scale ${scale.toFixed(2)}`);
    }
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  ok(`${tag}: the page does not scroll sideways`, overflow <= 1, `overflow ${overflow}px`);

  if (vp.w === 1440) {
    const byKind = (k) => figs.filter((x) => x.kind === k);
    ok("1440x900: node-and-edge diagrams sit on the blueprint grid", byKind("flowchart").length > 0 && byKind("flowchart").every((x) => x.grid));
    ok("1440x900: sequence diagrams and charts do not", [...byKind("sequence"), ...byKind("echarts")].every((x) => !x.grid));
    // the headline: a 960x740 diagram is shown between the old x0.61 and the stretched x1.2
    for (const f of byKind("flowchart").filter((x) => x.fw === 960 && x.fh === 740)) {
      const s = f.w / f.fw;
      ok(`1440x900: ${f.id} is neither the old x0.61 nor the stretched x1.2`, s > 0.8 && s < 1.05, `x${s.toFixed(3)} (${f.w.toFixed(0)}x${f.h.toFixed(0)})`);
    }
    // the sequence the operator approved keeps its size (it fits the screen at the enlargement ceiling)
    for (const f of byKind("sequence")) ok(`1440x900: ${f.id} (sequence) is not shrunk below its approved size`, f.w >= 1100, `${f.w.toFixed(0)}x${f.h.toFixed(0)}`);
    if (OUT) {
      fs.mkdirSync(OUT, { recursive: true });
      await page.screenshot({ path: path.join(OUT, "size-1440x900.png"), fullPage: false });
    }
  }

  // An edge label is cut out of the line it sits beside: a stroke in the frame's own ground, painted under the glyphs.
  if (vp.w === 1440) {
    const label = await page.evaluate(() => {
      const t = document.querySelector("svg .edge-label");
      const wrap = t && t.closest(".svgwrap");
      if (!t || !wrap) return null;
      const cs = getComputedStyle(t);
      return { order: cs.paintOrder, stroke: cs.stroke, width: cs.strokeWidth, ground: getComputedStyle(wrap).backgroundColor };
    });
    ok("1440x900: an edge label is cut out of its line (paint-order stroke, ground-coloured)", !!label && /^stroke/.test(label.order) && parseFloat(label.width) >= 4 && label.stroke === label.ground, JSON.stringify(label));
  }

  // The title of a native diagram is an SVG <text>: its default fill is black. In BOTH themes it must be readable on the page.
  if (vp.w === 1440) {
    for (const theme of ["dark", "light"]) {
      await page.evaluate((t) => document.documentElement.setAttribute("data-theme", t), theme);
      const read = await page.evaluate(() => [...document.querySelectorAll("svg .figure-title")].map((t) => {
        const fill = getComputedStyle(t).fill;
        const bg = getComputedStyle(document.body).backgroundColor;
        return { fill, bg };
      }));
      const lum = (rgb) => {
        const m = /rgba?\((\d+)[ ,]+(\d+)[ ,]+(\d+)/.exec(rgb);
        if (!m) return null;
        const f = (v) => { const s = Number(v) / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
        return 0.2126 * f(m[1]) + 0.7152 * f(m[2]) + 0.0722 * f(m[3]);
      };
      for (const t of read) {
        const a = lum(t.fill);
        const g = lum(t.bg);
        const ratio = a == null || g == null ? 0 : (Math.max(a, g) + 0.05) / (Math.min(a, g) + 0.05);
        ok(`1440x900 ${theme}: a diagram title is readable (contrast >= 4.5)`, ratio >= 4.5, `${t.fill} on ${t.bg} = ${ratio.toFixed(1)}`);
      }
    }
  }
  await page.close();
}
await b.close();
finish();
