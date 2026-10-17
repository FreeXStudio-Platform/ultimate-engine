// Universal path/tool configuration loader (Node side — mirrors engine_config.py).
// Single source of truth: ../../engine.config.json (relative to this file). Every value has a
// hardcoded fallback matching this engine's original, tested behavior, so a missing or corrupted
// config file degrades to "works exactly like before" rather than failing. Precedence for every
// setting: environment variable > engine.config.json value > hardcoded fallback below.
//
// See ../../CONFIGURATION.md for the full field reference and override examples.

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ENGINE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..'); // .../Ultimate Engine/
const CONFIG_PATH_ENV = 'ENGINE_CONFIG_PATH';

let _cachedConfig;
function rawConfig() {
  if (_cachedConfig !== undefined) return _cachedConfig;
  const path = process.env[CONFIG_PATH_ENV] || join(ENGINE_ROOT, 'engine.config.json');
  try {
    _cachedConfig = JSON.parse(readFileSync(path, 'utf8'));
  } catch {
    _cachedConfig = {};
  }
  return _cachedConfig;
}

function field(section, key, fallback) {
  const cfg = rawConfig()[section]?.[key];
  if (cfg && typeof cfg === 'object') {
    if (cfg.envVar && process.env[cfg.envVar]) return process.env[cfg.envVar];
    return cfg.value ?? fallback;
  }
  return fallback;
}

let _cachedHostRoot;
export function hostRoot() {
  if (_cachedHostRoot !== undefined) return _cachedHostRoot;
  const configured = field('docSystem', 'hostRoot', null);
  if (configured) return (_cachedHostRoot = resolve(configured));
  const git = toolPath('git');
  if (git) {
    try {
      const out = execFileSync(git, ['rev-parse', '--show-toplevel'], { encoding: 'utf8', timeout: 5000, stdio: ['ignore', 'pipe', 'ignore'] }).trim();
      if (out) return (_cachedHostRoot = out);
    } catch { /* not inside a git repo, or git unavailable — fall through */ }
  }
  return (_cachedHostRoot = ENGINE_ROOT);
}

export function graphifyConfig() {
  return {
    srcRoot: field('graphify', 'srcRoot', 'src'),
    detectorsDir: field('graphify', 'detectorsDir', 'src/analysis/detectors'),
    frontendPublicDir: field('graphify', 'frontendPublicDir', 'frontend/public'),
    pipelineStepsFile: field('graphify', 'pipelineStepsFile', null),
  };
}

export function browserCandidates(name) {
  return rawConfig().browsers?.[name] ?? [];
}

export function securityConfig() {
  return { allowRuntimeCDN: rawConfig().security?.allowRuntimeCDN ?? false };
}

const _toolCache = new Map();

/**
 * True if `candidate` actually resolves to something runnable — either a real filesystem path
 * (existsSync, covering absolute paths and paths relative to the current working directory) or a
 * bare command name findable on PATH (whichSync). Applied to EVERY discovery route, not just the
 * pathFallback loop: `P8-062` reproduced with `ENGINE_CODEMAP_BIN=/nonexistent/codemap node
 * tools/graphify/build.mjs`, which returned that unchecked env-var string as "found" and let a raw
 * `Error: spawnSync /nonexistent/codemap ENOENT` reach the user instead of requireTool()'s
 * actionable message — because the envVar and config `path` branches never validated at all,
 * unlike the pathFallback loop two lines below them.
 */
function isUsable(candidate) {
  if (!candidate) return false;
  return existsSync(candidate) || whichSync(candidate);
}

/** Discover an external binary: env var override > config 'path' field > PATH-searched fallback list. */
export function toolPath(name) {
  if (_toolCache.has(name)) return _toolCache.get(name);
  const cfg = rawConfig().tools?.[name] ?? {};
  let found = null;
  if (cfg.envVar && process.env[cfg.envVar]) {
    const candidate = process.env[cfg.envVar];
    if (isUsable(candidate)) found = candidate;
  } else if (cfg.path) {
    if (isUsable(cfg.path)) found = cfg.path;
  } else {
    for (const candidate of cfg.pathFallback ?? [name]) {
      if (whichSync(candidate)) { found = candidate; break; }
      const rel = join(hostRoot(), candidate);
      if (existsSync(rel)) { found = rel; break; }
    }
  }
  _toolCache.set(name, found);
  return found;
}

/** Like toolPath(), but throws a clear, actionable error instead of returning null. */
export function requireTool(name) {
  const found = toolPath(name);
  if (found) return found;
  const cfg = rawConfig().tools?.[name] ?? {};
  const hint = cfg.installHint ?? `install '${name}' and ensure it is on PATH`;
  const envName = cfg.envVar ?? `ENGINE_${name.toUpperCase()}_BIN`;
  throw new Error(`required tool '${name}' not found. ${hint}. Or point at it explicitly: export ${envName}=/path/to/${name}`);
}

function whichSync(bin) {
  try {
    execFileSync(process.platform === 'win32' ? 'where' : 'which', [bin], { stdio: ['ignore', 'ignore', 'ignore'] });
    return true;
  } catch {
    return false;
  }
}

/**
 * Refuse to emit a graph that answers nothing. `OG-248`.
 *
 * Every graphify builder walks a HOST directory with a fail-open walker, so a missing or
 * differently-shaped tree yields zero rows — and a builder that then writes an empty graph and
 * exits 0 is not reporting "no findings", it is reporting a question it never asked. It has been
 * paid for twice: `build-deps.mjs` shipped a 0-node graph over ~77 real modules for weeks because
 * `srcRoot` still pointed at the shipped example default (see `engine.config.json`
 * graphify._readme), and a field trial ran `build-coverage.mjs` against a foreign host, read
 * `0 detectors ... exit 0` as a result, and filed the exit code as an engine false green.
 *
 * `build-deps.mjs` carried this refusal alone and inline; this is that guard, LIFTED rather than
 * copied, so the three builders with the same fail-open walker cannot drift apart in wording,
 * exit code, or whether they write before refusing (`RULES.md` Rule 1). Exit 2 is build-deps'
 * original contract, kept.
 *
 * Called BEFORE anything is written, so a refused build leaves no plausible artifact behind for
 * the next reader — or for `build-admin-catalog.mjs`, which counts whatever `graphify-out/` holds.
 *
 * @param {string} label      the builder's own `[/name]` prefix, so the message matches its output
 * @param {number} count      how many of the thing it exists to find were found
 * @param {string} what       what that thing is, plural ("`.py` files", "detectors")
 * @param {string} where      the directory that was scanned, so the cause is in the message
 * @param {string} [configKey]  the `graphify.<key>` this builder reads, when it reads one
 * @param {string} [envVar]     that key's environment override
 */
export function refuseVacuousGraph(label, count, what, where, configKey, envVar) {
  if (count > 0) return;
  console.error(`${label} REFUSING: no ${what} under ${where}`);
  if (configKey) {
    console.error(`${label} graphify.${configKey} is '${graphifyConfig()[configKey]}' (engine.config.json,`);
    console.error(`${label} or ${envVar}). Point it at this project's own tree.`);
  }
  console.error(`${label} An empty graph is not a result — nothing is written.`);
  process.exit(2);
}
