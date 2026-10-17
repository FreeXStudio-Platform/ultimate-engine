#!/usr/bin/env node
/* tools/graphify/build-coverage.mjs — the COVERAGE graph (model #5): detectors <-> SWC classes <-> tags.
 *
 * Scans src/analysis/detectors/ for each detector's name / swc_id / tags and wires detector->SWC and
 * detector->tag edges. Answers "which vuln classes (SWC) have detectors and which tags dominate" and surfaces
 * detectors with NO swc mapping (a coverage blind-spot to investigate). Deterministic, LOCAL-only.
 * Writes graphify-out/{coverage.json, coverage-data.js, build.log}. Usage: node tools/graphify/build-coverage.mjs
 */
import { readFileSync, writeFileSync, readdirSync, statSync, existsSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { hostRoot, graphifyConfig, refuseVacuousGraph } from '../lib/engine-config.mjs';

// ROOT = the HOST PROJECT being analyzed (engine.config.json's docSystem.hostRoot / git root
// discovery), not necessarily this engine's own location. DET defaults to "src/analysis/detectors"
// (graphify.detectorsDir) — this script is a worked EXAMPLE tuned to one project's detector-plugin
// shape (name=/swc_id=/tags= class attributes); adapt the regex scan below for a different shape.
const ROOT = hostRoot();
const DET = join(ROOT, graphifyConfig().detectorsDir);
const OUT = join(ROOT, 'graphify-out');

const files = [];
(function walk(d){ let e=[]; try{e=readdirSync(d);}catch{return;} for(const x of e){ if(x==='__pycache__'||x.startsWith('.'))continue;
  const p=join(d,x); let s; try{s=statSync(p);}catch{continue;} if(s.isDirectory())walk(p); else if(x.endsWith('.py')&&!x.startsWith('_'))files.push(p); } })(DET);

const nodes=[], links=[], seen=new Set();
const add=(id,type,label,extra={})=>{ if(!seen.has(id)){ seen.add(id); nodes.push({id,type,label,...extra}); } };
const swcCount={}, tagCount={}; let detectors=0, noSwc=0;

for(const p of files){
  let txt; try{ txt=readFileSync(p,'utf8'); }catch{ continue; }
  const name=(txt.match(/\bname\s*=\s*["']([\w-]+)["']/)||[])[1];
  if(!name) continue;
  detectors++;
  const swc=(txt.match(/\bswc_id\s*=\s*["'](SWC-\d+)["']/)||[])[1] || null;
  const tags=[...(txt.match(/\btags\s*=\s*\[([^\]]*)\]/)?.[1]?.matchAll(/["']([\w-]+)["']/g)||[])].map(m=>m[1]);
  add('det:'+name,'detector',name);
  if(swc){ add(swc,'swc',swc); links.push({source:'det:'+name,target:swc,kind:'covers'}); swcCount[swc]=(swcCount[swc]||0)+1; }
  else { noSwc++; }
  for(const t of tags){ add('tag:'+t,'tag',t); links.push({source:'det:'+name,target:'tag:'+t,kind:'tagged'}); tagCount[t]=(tagCount[t]||0)+1; }
}

refuseVacuousGraph('[/coverage]', detectors, 'detectors', DET, 'detectorsDir', 'ENGINE_GRAPHIFY_DETECTORS_DIR');

try{ if(!existsSync(OUT)) mkdirSync(OUT,{recursive:true}); }catch{}
const nodeLink={ directed:true, multigraph:false, graph:{name:'coverage'}, nodes, links };
try{ writeFileSync(join(OUT,'coverage.json'),JSON.stringify(nodeLink,null,2)); }catch{}
try{ writeFileSync(join(OUT,'coverage-data.js'),'window.GRAPH = '+JSON.stringify({meta:{name:'coverage'},nodes,links})+';\n'); }catch{}
try{ writeFileSync(join(OUT,'build.log'),`${new Date().toISOString()} graph=coverage detectors=${detectors} swc=${Object.keys(swcCount).length} tags=${Object.keys(tagCount).length} no_swc=${noSwc} status=ok\n`,{flag:'a'}); }catch{}

const top=(o,n)=>Object.entries(o).sort((a,b)=>b[1]-a[1]).slice(0,n);
console.log(`[/coverage] ${detectors} detectors · ${Object.keys(swcCount).length} SWC classes · ${Object.keys(tagCount).length} tags · ${noSwc} detectors with NO swc_id`);
console.log(`  top SWC by detector count: ${top(swcCount,6).map(([k,v])=>`${k}(${v})`).join(' ')}`);
console.log(`  top tags: ${top(tagCount,8).map(([k,v])=>`${k}(${v})`).join(' ')}`);
console.log(`  view: graph-view.html?g=coverage   ·   query (separate tool, see README): graphify query "<q>" --graph graphify-out/coverage.json`);
