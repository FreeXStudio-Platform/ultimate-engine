#!/usr/bin/env node
/* tools/graphify/build-admin-catalog.mjs — emits frontend/public/graph-catalog.json for the admin Graph tab.
 *
 * IMPORTANT: this ships only METADATA about the graphs (model, scope, question, counts, the local command) —
 * NEVER the graph data itself. The graphs (graphify-out/) stay gitignored + local + never deployed. So even in
 * a deployed admin build, this tab describes the system and tells the operator how to open each graph locally;
 * it does not leak module lists, detector internals, or the engine structure.
 * Counts are read from graphify-out/*.json if present (local), else null (fresh clone). Usage: node tools/graphify/build-admin-catalog.mjs
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { hostRoot, graphifyConfig } from '../lib/engine-config.mjs';

// ROOT = the HOST PROJECT (engine.config.json's docSystem.hostRoot / git root discovery). PUB
// defaults to "frontend/public" (graphify.frontendPublicDir) — this script is a worked EXAMPLE
// assuming a sibling deployed frontend with an admin "Graph" tab; if your host project has no
// such thing, this script's output simply has nowhere useful to go — point frontendPublicDir at
// wherever your own admin surface reads catalog metadata from, or skip this script entirely.
const ROOT = hostRoot();
const GOUT = join(ROOT, 'graphify-out');
const PUB = join(ROOT, graphifyConfig().frontendPublicDir);

const count = (file) => {
  try { const g = JSON.parse(readFileSync(join(GOUT, file), 'utf8')); return { nodes: g.nodes?.length ?? null, links: (g.links ?? g.edges)?.length ?? null }; }
  catch { return { nodes: null, links: null }; }
};

const MODELS = [
  { id:'graph',    name:'Structure',       scope:'repo dir/file tree (codemap)', question:'where does X live / what is in this module', builder:'tools/graphify/build.mjs', open:'bash tools/graphify/open.sh', ...count('graph.json') },
  { id:'deps',     name:'Dependency',      scope:'real Python import edges',     question:'what depends on Y / the risky core / redundancy', builder:'tools/graphify/build-deps.mjs', open:'bash tools/graphify/open.sh deps', ...count('deps.json') },
  { id:'pipeline', name:'Pipeline',        scope:'scan → detect → AI → report',  question:'how a scan actually flows, step by step', builder:'tools/graphify/build-pipeline.mjs', open:'bash tools/graphify/open.sh pipeline', ...count('pipeline.json') },
  { id:'coverage', name:'Coverage',        scope:'detectors ↔ SWC ↔ tags',       question:'which vuln classes have detectors / which are uncovered', builder:'tools/graphify/build-coverage.mjs', open:'bash tools/graphify/open.sh coverage', ...count('coverage.json') },
];

const catalog = {
  meta: {
    schema: '.graph-catalog/v1',
    generated_at: new Date().toISOString(),
    note: 'Metadata only. The graphs themselves are LOCAL + gitignored + never deployed. This tab documents the system and how to open each graph locally; it never serves graph data.',
    local_only: true,
  },
  models: MODELS,
};

try { if (!existsSync(PUB)) mkdirSync(PUB, { recursive: true }); } catch {}
writeFileSync(join(PUB, 'graph-catalog.json'), JSON.stringify(catalog, null, 2));
console.log(`[admin-catalog] wrote frontend/public/graph-catalog.json (${MODELS.length} models; counts ${MODELS.some(m=>m.nodes)?'live':'null — run builders first'})`);
