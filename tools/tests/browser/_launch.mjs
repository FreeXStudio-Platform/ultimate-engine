// Shared launcher for the browser checks: finds Playwright and a headless Chromium, or says why it cannot.
//
// Exit-code contract of every check that imports this file: 0 = every check passed · 1 = a check failed ·
// 3 = Playwright / a browser is not available (the Python caller reports a SKIP with this cause; never a pass).
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..", "..");

function loadPlaywright() {
  const bases = [process.env.PLAYWRIGHT_MODULE_DIR, process.cwd(), ROOT, path.join(ROOT, "tools", "visual-engine")]
    .filter(Boolean).map((d) => path.join(d, "package.json"));
  for (const base of bases) {
    for (const name of ["playwright", "playwright-core", "@playwright/test"]) {
      try { return createRequire(base)(name); } catch { /* try the next */ }
    }
  }
  return null;
}

function chromiumPath() {
  const cache = path.join(process.env.HOME || "", "Library", "Caches", "ms-playwright");
  const linux = path.join(process.env.HOME || "", ".cache", "ms-playwright");
  for (const dir of [cache, linux]) {
    if (!fs.existsSync(dir)) continue;
    for (const d of fs.readdirSync(dir).filter((x) => /^chromium_headless_shell-/.test(x)).sort().reverse()) {
      const sub = fs.readdirSync(path.join(dir, d)).find((x) => x.startsWith("chrome-headless-shell"));
      if (!sub) continue;
      for (const bin of ["chrome-headless-shell", path.join("chrome-headless-shell-mac-arm64", "chrome-headless-shell")]) {
        const full = path.join(dir, d, sub, bin);
        if (fs.existsSync(full)) return full;
      }
    }
  }
  return undefined;
}

/** Launch headless Chromium, or print `SKIP: <cause>` and exit 3. */
export async function launchOrSkip() {
  const pw = loadPlaywright();
  if (!pw) { console.log("SKIP: playwright is not installed (set PLAYWRIGHT_MODULE_DIR or `npm i -D playwright`)"); process.exit(3); }
  try {
    const exe = chromiumPath();
    return await pw.chromium.launch(exe ? { executablePath: exe } : {});
  } catch (e) {
    console.log("SKIP: no Chromium available — " + String(e).split("\n")[0]);
    process.exit(3);
  }
}

/** A tiny assertion log: `ok(name, cond, extra)` prints PASS/FAIL; `finish()` sets the exit code. */
export function checks() {
  const out = [];
  return {
    ok(name, cond, extra = "") { out.push(`${cond ? "PASS" : "FAIL"}  ${name}${extra ? "  — " + extra : ""}`); },
    finish() {
      console.log(out.join("\n"));
      process.exit(out.some((l) => l.startsWith("FAIL")) ? 1 : 0);
    },
  };
}
