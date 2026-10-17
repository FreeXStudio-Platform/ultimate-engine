#!/usr/bin/env node
/* graphify — MANUAL, local-only, NO VPS / NO deploy. Engine + whole-system view.
 * Builds a queryable directory-level system map from codemap → graphify-out/graph.json (NetworkX node-link).
 * Run manually (never auto):   node tools/graphify/build.mjs
 * Then ask it, token-cheaply:  graphify query "<question>" --graph graphify-out/graph.json
 */
import { execFileSync } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { requireTool, toolPath, hostRoot, refuseVacuousGraph } from '../lib/engine-config.mjs';

// S144/B2 — graph schema version (VERSIONING.md §2 `g-<schema>.<N>`). Bumps when
// the graph node/link FORMAT changes (not its content). content_version below is
// a deterministic hash of the emitted node/link set (its content identity).
const GRAPH_SCHEMA_VERSION = '1.0';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const OUT = join(ROOT, 'graphify-out');
// WHICH codebase gets mapped. Uses the same host-root resolution every other consumer in this
// engine already goes through (ENGINE_HOST_ROOT env var > engine.config.json's docSystem.hostRoot
// > `git rev-parse --show-toplevel` > this engine's own directory) — see CONFIGURATION.md.
// Previously this was hardcoded to ROOT, so the documented "works against ANY codebase codemap
// can index" claim was only reachable by physically copying the engine into that codebase; there
// was no supported way to point it at a target. Output ALWAYS stays under this engine's own
// graphify-out/ regardless of what is being scanned — mapping a tree never writes into it.
const TARGET = hostRoot();
mkdirSync(OUT, { recursive: true });

// Discovered via engine.config.json's tools.codemap (env var override, explicit path, or PATH
// fallback) — was previously a bare 'codemap' with zero error handling, crashing with a raw
// ENOENT stack trace if not installed. requireTool() gives an actionable message instead.
const codemapBin = requireTool('codemap');
const cm = JSON.parse(execFileSync(codemapBin, ['--json', '--depth', '0', '.'], { cwd: TARGET, maxBuffer: 1 << 27 }).toString());
const DEPTH = 3;                                   // directory granularity for the system view
const dirs = new Map();                            // path -> {files,size}
const linkSet = new Set();                         // "sourcetarget"
const seen = new Set();
const nodes = [];
const addNode = (id, n) => { if (!seen.has(id)) { seen.add(id); nodes.push({ id, ...n }); } };

addNode('(root)', { label: '', type: 'root' });
for (const f of cm.files) {
  const parts = f.path.split('/');
  let prev = '(root)';
  for (let i = 0; i < Math.min(DEPTH, parts.length - 1); i++) {
    const d = parts.slice(0, i + 1).join('/');
    const m = dirs.get(d) || { files: 0, size: 0 }; m.files++; m.size += f.size || 0; dirs.set(d, m);
    linkSet.add(prev + '' + d); prev = d;
  }
  if (parts.length - 1 < DEPTH) {                  // shallow file → its own leaf node
    const d = parts.length > 1 ? parts.slice(0, -1).join('/') : '(root)';
    addNode(f.path, { label: parts[parts.length - 1], type: 'file', ext: f.ext, size: f.size });
    linkSet.add(d + '' + f.path);
  }
}
for (const [d, m] of dirs) addNode(d, { label: d.split('/').pop(), type: 'dir', path: d, files: m.files, kb: Math.round(m.size / 1024) });

const links = [...linkSet].map(l => { const [source, target] = l.split(''); return { source, target, kind: 'contains' }; });
// FILES, not nodes: `(root)` is added unconditionally, so a node count can never reach 0 and
// could never detect a host tree that yielded nothing. No config key is passed because this
// builder maps the host root itself rather than a configured subdirectory.
refuseVacuousGraph('[/graphify]', cm.files.length, 'files', TARGET);
// S144/B2: content_version = short sha of the emitted node/link identity — two
// builds of the same repo state produce the same content version (VERSIONING.md §2).
const contentVersion = createHash('sha256').update(JSON.stringify({ nodes, links })).digest('hex').slice(0, 8);
const graph = { directed: true, multigraph: false, graph: { name: 'codebase-map', schema_version: GRAPH_SCHEMA_VERSION, content_version: contentVersion }, nodes, links };

writeFileSync(join(OUT, 'graph.json'), JSON.stringify(graph, null, 2));
// Interpreter path for the separate `graphify` query CLI (pipx package, not part of this repo)
// to find its own Python. Discovered via engine.config.json's tools.python (env var override,
// explicit path, or the .venv/bin/python -> python3 -> python fallback list) so this works on
// whatever machine runs the build without editing code.
writeFileSync(join(OUT, '.graphify_python'), (toolPath('python') || 'python3') + '\n');
writeFileSync(join(OUT, 'graph-data.js'), 'window.GRAPH = ' + JSON.stringify({ meta: { name: 'codebase-map', schema_version: GRAPH_SCHEMA_VERSION, content_version: contentVersion }, nodes, links }) + ';\n'); // for tools/graphify/graph-view.html — same version identity as graph.json (S144/B2)
try { writeFileSync(join(OUT, 'build.log'), `${new Date().toISOString()} nodes=${nodes.length} links=${links.length} status=ok\n`, { flag: 'a' }); } catch {} // observability (GRAPH-ENGINEERING.md §9)
console.log(`[/graphify] mapped ${TARGET}`);
console.log(`[/graphify] ${nodes.length} nodes · ${links.length} links → graphify-out/{graph.json,graph-data.js,build.log}`);
console.log(`open the visual: tools/graphify/graph-view.html  ·  query (separate tool, see README): graphify query "<question>" --graph graphify-out/graph.json`);
