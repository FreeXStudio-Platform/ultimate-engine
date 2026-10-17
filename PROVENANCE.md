<!-- artifact-hardened: Approved With Known Risks @ 96b90d8 on 2026-08-30 via three-pass-v1 -->

# Hardening status — `Approved With Known Risks`

> **Path scope note (added 2026-08-20).** Several file paths cited in the session records below
> belong to this engine's **source project** and were deliberately excluded when the package was
> extracted — `docs/INDEX.md`, `docs/system/SYSTEM.json`, `tools/PROVENANCE.md`,
> `tools/docgen/assets/ah-mark.svg`, `tools/docgen/bank_doc_lint.py`,
> `tools/docgen/demo/INDEX.html`. They are retained verbatim as the historical record of what was
> verified *there*; **none of them exists in this repository** and none should be looked for here.

**Re-hardened and re-stamped at the Phase-7 close (2026-08-30, `OG-09`).** The stamp above certifies
this document's body against the commit it names, after the full independent reverification (Pass 9,
`docs/process/VERIFICATION_LOG.md`) that found and closed two real moat breaches (`OG-213`, `OG-214`)
and four other defects. The `stamps` corpus guard now passes because the body MATCHES the stamped
commit — `drift declared by: none` — not because a handover declared the drift; the
`NEEDS RE-HARDENING` block that stood here, and the `HANDOFF.md` line that excused it, are both
removed. Scope of this approval: this package's engines, their configuration layer, the git moat and
its two Phase-7 breach fixes, and the claims in `README.md` / `USAGE_GUIDE.md` / `CONFIGURATION.md` /
`INTERPRETATION.md` / this file. **If this file is modified after the stamped commit, the stamp is
void** and the `stamps` guard reports the drift — verified rather than assumed.

The six known risks R1–R6 below are re-verified as still bounded and carried, which is what
`Approved With Known Risks` means; each has a bound, an owner and a trigger. The original Session-4
stamp (`Approved With Known Risks @ 9a1c011`, 2026-08-19) is superseded, not deleted — its method and
findings remain in "Session 4" below as the historical record.

## Gate results, with cited evidence

| Gate | Verdict | Evidence |
|---|---|---|
| Every documented capability exists and runs | PASS | 15 native figure kinds + 2 bridges all rendered in one real CLI build (`examples/capability-gallery.html`, 21 figures); MCP server advertises its 7 claimed tools over stdio; `engine.config.json` resolves on both the Python and Node loaders |
| Test suites green | PASS | visual-engine `npm test` 30/30, `npm run simulate` 22/22; mermaid-engine 6/6 — re-run after every fix in this pass, not once at the start |
| Fail-closed rules actually enforce | PASS | All four gates deliberately triggered; each exited 1 with a specific message and wrote no output (table in Session 4). Not inferred from source |
| Rendered output is correct | PASS | 262 text elements across 21 figures browser-measured: 0 overlaps, 0 out-of-box text, in dark AND light |
| Numbers are accurate and traceable | PASS | 25 arithmetic identities across the gallery's insight claims recomputed from source data — all consistent; each figure cites one of six named, reproducible measurements |
| Documentation matches reality | PASS | Every claim re-verified this pass; five that did not hold were fixed in code, not softened in prose (Session 4) |
| Offline / no runtime CDN | PASS | Gallery output: 0 external `src`/`href`, 0 `@import`, 0 `googleapis`/`unpkg` references |
| No project-name leakage | PASS | Brand-name grep across the gallery output: 0 hits for every retired term |
| No secrets committed | PASS | `~/.claude/scripts/secret-scan.sh` on the staged tree: 235 files, 44,142 lines read, exit 0 |
| Self-contained for a fresh reader | PASS | Depends on no chat memory; `verify`, the gallery, and the six root documents are the entry points |
| Gate coverage proven complete | **NOT PROVEN** | See risk R1 — gates are demonstrated sound on the cases measured, and this pass found two things they drew but did not check |

## Known risks

Each is bounded, none blocks use, and none is a silent unknown — all are also listed under
"Not verified" at the end of this file.

**R1 — Collision-gate coverage is demonstrated, not proven complete.**
*Bound:* does not affect any figure in the shipped gallery or bundled samples, all of which are
measured clean in both themes; does not affect correctness of data, sourcing, or the four
enforcement gates. Applies only to the possibility of a *further* undrawn-but-unchecked element
in some future figure geometry.
*Owner:* next engine session.
*Resolution:* re-run the browser bounding-box sweep (method documented in `INTERPRETATION.md`
Part 2) after any renderer change. **Trigger:** any edit to a `tools/docgen/*.py` renderer.

**R2 — `npm run simulate` rewrites the goldens `npm test` guards.**
*Bound:* affects only the regression-evidence workflow, never rendered output or any gate. Does
not apply if the documented `npm test && npm run simulate` order is used, since `&&`
short-circuits on failure.
*Owner:* operator (it is a change to this engine's own evidence model, not a defect fix).
*Resolution:* split baseline-writing from simulation running, or make golden-writing opt-in via
a flag. **Trigger:** the first time a drift is discovered to have been silently re-baselined.

**R3 — Three graphify example builders remain unexecuted against a real target.**
`build-deps.mjs` / `build-coverage.mjs` / `build-admin-catalog.mjs` are config-wired and
syntax-clean but have never been run end-to-end, because this package has no `src/`-rooted
Python tree to point them at.
*Bound:* does not affect `build.mjs` (the generic structure mapper, run twice this pass against
two different trees) or `build-pipeline.mjs` (run and verified). These three are explicitly
documented as worked examples, not general-purpose tools.
*Owner:* whoever first embeds this engine in a matching codebase.
*Resolution:* run each once against that codebase and record the result here. **Trigger:** first
use against a `src/`-rooted Python project.

**R4 — chart-engine and mermaid-engine figures are outside docgen's collision gates.**
Correctly disclosed in `INTERPRETATION.md`; they inherit ECharts' and ELK's own layout
guarantees instead.
*Bound:* docgen-native figures are unaffected — they are gated. The gallery's bridged figures are
measured clean, but empirically for that one document, not by a standing gate.
*Owner:* next engine session.
*Resolution:* extend the browser sweep into a repeatable check, or accept permanently and keep
it disclosed. Note two of this pass's five defects were in exactly this uncovered area.
**Trigger:** adding a new chart family or Mermaid diagram type to a source-of-truth document.

**R5 — Figure rule-errors reach the CLI as unhandled tracebacks.**
Header/manifest failures print a clean `[header] …` line and `BLOCKED`; the three figure gates
raise instead.
*Bound:* **corrected 2026-08-20 — the previous bound was falsified by measurement.** It read
"purely presentational … exit 1, nothing written", and an independent verifier disproved both halves
on the corpus build path added in Phase 2: a raise on document N leaves documents 1..N-1 fully
written, so "nothing written" was false; and the raise skipped `save_cache`, discarding every cache
entry the run had earned, so the consequence was work-loss rather than display. The true bound now:
**single-document builds are still exit-1-nothing-written; corpus builds persist the documents that
already succeeded**, and since `build_corpus` gained per-document isolation plus a `finally`-guarded
save (`OG-24`, closed 2026-08-20), a raising document is recorded as a blocking finding and no longer
takes the rest of the corpus or the cache down with it. What remains open is the error MODEL: a
renderer rule-break still surfaces as an exception rather than a `Finding`.
*Bound (unchanged):* the traceback names the failing file and line.
*Owner:* operator (it is an error-model decision: is a renderer rule-break a *finding* or an
*exception*?).
*Resolution:* decide the model, then make `cli.py` consistent with it. **Trigger:** first time a
non-authoring user hits one and misreads it as a crash rather than a refusal.

**R6 — `project_index` has no concurrency protection.** Pre-existing and disclosed; last write
wins on the JSON file.
*Bound:* fine for one agent or one person, which is the documented intended use. `verify` now
detects the duplicate-path symptom if two writers do collide.
*Owner:* operator.
*Resolution:* file locking, or accept permanently. **Trigger:** first multi-writer use.

---

# Provenance

Assembled 2026-08-18 by Claude Code, on explicit instruction, from two source
projects — both read-only during this process; nothing was written back into
either. Verified via `git status` in AuditHunt before and after (working tree
of `tools/` and `docs/` unmodified by this session) and by never running a
write/edit tool against either source path.

This document names the source projects deliberately, as an honest audit
trail — see the note in `README.md`. The de-branding described below applies
to the delivered engine code (`tools/`, `vault-graph-engine/`), not to this
record of where it came from.

## Sources

| Source | Path as of 2026-08-18 | What was taken |
|---|---|---|
| AuditHunt — the project whose engines were handcrafted | `<workspace>/AuditHunt/tools/docgen/` | Full source, minus exclusions below → `tools/docgen/` |
| AuditHunt | `<workspace>/AuditHunt/tools/visual-engine/` | Full source, minus `node_modules/` and scratch `renders/current/` → `tools/visual-engine/` |
| AuditHunt | `<workspace>/AuditHunt/tools/graphify/` | Full source, no exclusions → `tools/graphify/` |
| CredMgr V2 — the project that received a ported copy of the above | `<workspace>/CredMgr/v2/design/graph-engine/` | Full contents (its own, separate force-graph engine — not a copy of anything from AuditHunt) → `vault-graph-engine/` |

A fully de-branded port of AuditHunt's `docgen` + `visual-engine` also exists
inside CredMgr, at `<workspace>/CredMgr/tools/` (its own project
root, dated 2026-08-17 — the source project's own `tools/PROVENANCE.md`, not bundled here, documented that port in
detail: `AuditHunt`/`audithunt` → `CredMgr`/`credmgr`, `detector` vocabulary →
`op`/`finding`, package renamed `@audithunt/visual-engine` →
`@credmgr/visual-engine`, 30/30 unit tests + 22/22 acceptance simulations
green). **This build does not use that copy** — it rebuilds directly from
AuditHunt's originals instead, per instruction, so that AuditHunt's actual
authored templates (`tools/docgen/template.html`, `tools/visual-engine/
themes/*`, `tools/visual-engine/presets/*`) are the ones carried forward, not
CredMgr's re-derived, differently-themed "KEEP" versions. CredMgr's own port
was read only for its already-validated rename mapping (used as a reference
for this build's own renames, not copied) and to confirm it did *not*
independently port `graphify` — it did not; `graphify`'s only counterpart in
CredMgr is the separate `vault-graph-engine` design contract at
`v2/design/graph-engine/`, which is included above.

Two Desktop design-handoff packages (`CredMgr-V2-Design/` and
`CredMgr-V2-Design-SEND/`) and a partial documentation-only handoff snapshot
(`AuditHunt-Handoff-2026-08-12/`) were investigated and excluded — confirmed
to contain no generator code (design tokens, specs, and one static example
output only), and out of scope per instruction (frontend/UI design handoff,
not the generation engines).

## What was excluded, and why

| Excluded | Reason |
|---|---|
| `tools/docgen/__pycache__/`, `_sample_out/`, all `node_modules/` | Regenerable build/cache artifacts, not source |
| `tools/docgen/assets/ah-mark.svg` | AuditHunt's actual brand logo artwork |
| `tools/docgen/assets/animations/` (6 exploit-flow SVGs: bridge-drain, brute-force, sandwich, manipulation, double-spend, reentrancy) | AuditHunt's own security-audit domain content, not generic engine capability |
| `tools/docgen/bank_doc_lint.py` | AuditHunt's own contract-bank-specific linter |
| `tools/docgen/demo/INDEX.html`, `demo/CHANGELOG_DOCS.html` | Turned out to be full pre-rendered copies of AuditHunt's **actual internal document index and changelog** (231KB / 144KB, real operational history — VPS details, wallet references, real handoff docs) used as demo fixtures, not generic samples. Both also baked the real logo SVG artwork inline (see below). `demo/gallery.html` and `demo/README.html` were kept — genuinely generic component/README demos. |
| `tools/docgen/_out/*.html` (5 pre-rendered sample docs) | Discovered to have the real brand-mark SVG artwork (the actual logo's vector path data, not just a file reference) baked inline via `logo_svg()`'s inlining behavior. Removing the source `ah-mark.svg` file alone was not sufficient — these renders had already captured it. Deleted rather than hand-edited; regenerate fresh samples by running the build once dependencies are installed. |
| `tools/visual-engine/node_modules/` (92MB), `renders/current/` (gitignored scratch, 1 file) | Regenerable / scratch, not source |
| CredMgr's own already-de-branded `tools/docgen` + `tools/visual-engine` port | Superseded by rebuilding directly from AuditHunt's originals (see above) — not copied in |
| Both Desktop design-handoff packages, the partial handoff snapshot | Out of scope per instruction; confirmed to contain no generator code |

## De-branding performed (on `tools/` and `vault-graph-engine/` only)

A case-insensitive literal-string sweep for "AuditHunt", its retired product
alias "ChainSentinel", and "CredMgr", run before and after:

| Term | Hits before | Hits after |
|---|---|---|
| AuditHunt / audithunt | 110 files | 0 |
| ChainSentinel / chainsentinel | 2 files (both in the excluded demo files above) | 0 |
| CredMgr / credmgr | 3 files (2 in excluded demo files, 1 in `VAULT_GRAPH_SPEC.md`) | 0 |

Method: an ordered Python regex pass (multi-word phrases first, then npm-scope
and identifier renames, then a word-boundary catch-all), run twice — the first
pass had an ordering bug (a multi-word "CredMgr V2" rule placed after the
bare-word strip, so it never matched) and left literal double-space artifacts
from a whitespace-cleanup step that was defined but never actually invoked.
Both were caught on review, and the fix was to redo the copy from scratch
(rather than patch on top of a flawed first pass) with the ordering corrected
and the cleanup step removed in favor of hand-fixing the specific broken
sentences — see the next section. One additional manual fix outside the
regex pass: an env-var-style identifier the word-boundary rule couldn't reach
(`AUDITHUNT_API_KEY`), in a sample SDK doc since removed along with the rest
of `_out/`. Verified with a fresh `grep -ril` sweep after every pass — the
table above is the final tree's result.

Specific identifier renames (not just text strip):
- npm package `@audithunt/visual-engine` → `visual-engine` (unscoped)
- MCP server registration `audithunt-visuals` → `doc-visuals`
- `ENGINE_MANIFEST.json` id `audithunt-visual-engine` → `visual-engine`
- graphify's graph identity `audithunt-system` → `codebase-map`
- `assets/tokens.json` provenance line pointing at `audithunt-marketing` → generalized to `brand-source`
- `VAULT_GRAPH_SPEC.md`'s `KEEP · CredMgr V2` header → `node canvas`; other `CredMgr V2` mentions → `the vault`

**What was deliberately *not* renamed**, because it is domain vocabulary, not
a project name: the `detector-*` preset naming in `visual-engine/presets/`
(`detector-coverage-heatmap.json`, `detector-performance.json`, etc.), the
`shield`/`bronze`/`gold`/`ember`/`verify` token color-role names in
`assets/tokens.json` / `themes/tokens.json`, and the Space Grotesk / Inter /
JetBrains Mono typography choice. These are AuditHunt's actual authored
design decisions and chart-preset shapes — the instruction was to carry the
templates forward as the main templates, not to re-theme them. Flagging this
explicitly in case a future pass wants the vocabulary genericized too — that's
a larger, more editorial rewrite than literal project-name removal and
wasn't attempted here.

## Sentences repaired after brand-word removal

Stripping a bare "AuditHunt" sometimes removed a sentence's actual subject
(e.g. a doc title "How AuditHunt Analyzes a Contract" → "How  Analyzes a
Contract"), not just a modifier. These were found by grepping the tree for
leftover double-spaces after the regex pass and fixed by hand with real
replacement text (not a blanket space-collapse, which was tried first and
reverted — see above) in: `tools/docgen/sample.md`,
`tools/docgen/AUTHORING_PROMPT.md`, `tools/docgen/models.py`,
`tools/visual-engine/AI_AGENT_SKILL.md`, `tools/visual-engine/mcp/server.mjs`,
`tools/visual-engine/adapters/echarts/render.mjs`,
`tools/visual-engine/adapters/echarts/validate.mjs`,
`vault-graph-engine/VAULT_GRAPH_SPEC.md`. This was a manual pass over a
grepped list, not a full line-by-line read of all 103 modified files — inline
code comments elsewhere in the tree that lost "AuditHunt" as a modifier
(rather than a subject) were left as literal-string-clean but not
individually proofread for grammar; that's real, remaining, low-severity
residue, noted here rather than silently claimed away.

## Structural fix required after copying (not a branding issue)

`docgen` uses absolute Python imports (`from tools.docgen.models import ...`)
and `echarts_bridge.py` locates its `visual-engine` sibling via
`Path(__file__).resolve().parents[2] / "tools" / "visual-engine"` — both
assume the original `tools/docgen` + `tools/visual-engine` sibling layout
under a common root. Flattening these into differently-named top-level
folders (the first attempt, since reverted) would have broken every internal
import and the docgen→visual-engine bridge. Fixed by preserving the original
`tools/` nesting inside this folder instead of rewriting ~50 import
statements — `Ultimate Engine/tools/docgen/` and
`Ultimate Engine/tools/visual-engine/` are siblings under `tools/`, exactly
as they were in the source, so `parents[2]` still resolves correctly and no
import needed changing. `tools/__init__.py` was added (empty, matching
AuditHunt's own) since it wasn't part of either engine's own directory.

## Verification evidence

**Static checks:**
- Final brand-reference grep (AuditHunt / ChainSentinel / CredMgr, case-insensitive, whole `tools/` + `vault-graph-engine/` tree): **0 hits**, all three terms.
- All `.json` files: parsed clean with `python3 -m json.tool`.
- All `.py` files under `tools/docgen/`: compiled clean with `python3 -m py_compile`.
- All `.mjs` files under `tools/visual-engine/` and `tools/graphify/`: parsed clean with `node --check`.
- `tools/graphify/open.sh`: parsed clean with `bash -n`.
- No stray `__pycache__`/`.pyc` left in the delivered tree.
- Final size: 2.7MB total, 198 files — vs. ~185MB if both engines' `node_modules` had been carried over.

**Actually executed** (2026-08-18, second session): `cd tools/visual-engine && npm install && npm test && npm run simulate` — **30/30 unit tests pass, 22/22 acceptance simulations pass**, identical counts to the source engine. Run twice (before and after the fixes below) with the same result both times. `node_modules` removed again afterward — native bindings (`@resvg/resvg-js`) are platform-specific, so vendoring them would tie the package to this machine rather than making it portable; `npm install` reproduces the pass on any machine. `docgen` and `graphify` were not executed end-to-end (no test suite ships with docgen itself in the source project — see "What was deliberately not ported" above — and graphify's non-`build.mjs` scripts need a target codebase, see below).

**Deep completeness audit** (second session, 6 parallel read-only agents comparing this tree file-by-file against both sources): `tools/docgen`, `tools/visual-engine`, `tools/graphify`, and `vault-graph-engine` all verdict **CLEAN** — every file present in source (minus the documented exclusions above) exists here; vendored `force-graph.min.js` confirmed byte-identical (sha256 match) in both places it appears; no unexplained gaps in either direction.

## Fixes applied after the deep-verification pass (second session)

The first pass's own de-branding, while thorough on literal name-strings, missed several things a plain grep for "AuditHunt"/"CredMgr" structurally cannot catch. A second audit (independent agents re-checking with different methods — rendered-output inspection, full-file reads, portability scanning) found and this session fixed:

- **`"hunt"` token key removed** (`tools/docgen/assets/tokens.json`, `tools/visual-engine/themes/tokens.json`, `tools/docgen/tokens.py`) — a pure alias of `bronze` (`var(--bronze)`, same hex `#C4762A`), never consumed anywhere, whose only purpose was echoing the second half of "AuditHunt." Deleted outright rather than renamed, since nothing referenced it.
- **`tools/graphify/build.mjs`** — line 54 hardcoded this machine's personal pipx path (`/Users/<user>/.local/pipx/venvs/graphifyy/bin/python`) into its own generated output. Now derives the interpreter dynamically via `which python3` with a `python3` (PATH-relative) fallback.
- **`tools/docgen/ENGINE_PLAN.md`** — added a historical-context header note (the file is the original build plan and wasn't marked as such); fixed a missed double-space where "AuditHunt" had been stripped as a sentence subject (`protects the  platform` → `protects the platform`); generalized five "eye mark"/"eye-mark" references and two stale `ah-mark.svg` filename mentions to describe the actual shipped placeholder mark instead.
- **`tools/docgen/generator.py`** — same "eye-mark" → "mark" generalization in one docstring.
- **`tools/visual-engine/ENGINE_MANIFEST.json`** — the `registered_in` array listed AuditHunt-repo-specific integration paths (`CLAUDE.md`, `docs/system/SYSTEM.json`, `.mcp.json` at repo root, etc.) that don't exist in this package. Replaced with an honest note that this is a standalone package not yet wired into a host project.
- **`tools/visual-engine/mcp/config.example.json`** — its `_comment` claimed a repo-root `.mcp.json` exists "(committed)"; none ships with this package. Corrected.
- **`tools/graphify/open.sh`** — added a one-line note that its Chrome/Edge app-launch path is macOS-specific (it already degrades gracefully to `open`, then to printing the URL, so this was a documentation gap, not a functional one); fixed three more leading-space/orphaned-dash artifacts from brand-word removal (`#  interactive...` → proper single space, `.cache/-graph-window` → `.cache/graphify-graph-window`, `echo " graph →"` → `echo "graph →"`).
- **13 more leading-space artifacts** from the original brand-removal pass, found by a broader sweep (comment markers, string literals, an orphaned `-pipeline`/`-coverage` graph-name identifier in two graphify scripts) rather than the narrower double-space-in-prose check the first pass used: `mcp/server.mjs`, `tokens.py`, `sankey.py`, `build.mjs`'s own header comment, `fetch_public_fact.py`'s `User-Agent` string, `build-pipeline.mjs`/`build-coverage.mjs`'s graph identity names, `schemas/visual-job.schema.json`'s title, `adapters/echarts/html-template.mjs`'s fallback `<title>`, and all 13 chart presets' `provenance` field.

All fixes re-verified: fresh brand-name grep still 0 hits across all terms; JSON/Python/Node/shell syntax all still clean; `npm test` + `npm run simulate` re-run after the fixes, still 30/30 + 22/22.

## Separately audited, NOT part of this package: CredMgr's own AuditHunt→CredMgr port

The operator asked whether CredMgr's own de-branded copy (`<workspace>/CredMgr/tools/`, referenced above as the port this build deliberately does not use) actually holds up, or whether it missed anything the way this build's first pass did. Answer, from a read-only audit of that project (nothing there was touched): **its literal-string claim is true, but real branding survives in forms a name-grep can't catch:**

- `tools/visual-engine/README.md:57` cites the operator-directive filename `AUDIT_HUNT_AI_VISUALIZATION_ENGINE_MCP_INTEGRATION_SYSTEM.md` verbatim, underscore-joined — a genuine, undisclosed miss.
- AuditHunt's `ah-` brand-prefix is baked into 12 live CSS-class/animation-name identifiers across 7 of docgen's own native chart/diagram renderer files (`charts.py`, `geo_map.py`, `layered_workflow.py`, `isometric3d.py`, `sequence_diagram.py`, `sankey.py`, `visual.py` — e.g. `ah-figure`, `ah-bar`, `ah-radar`, `ah-heatmap`, `ah-pulse`). This is executable code, not a comment — it would ship into any document CredMgr renders through docgen's native renderers (as opposed to the ECharts-bridge path), and it's undocumented in the engine's source project `tools/PROVENANCE.md` (not bundled here) despite that file's two dated Correction sections existing specifically to log exactly this class of gap. It's invisible in CredMgr's one currently-rendered sample document only because that document's figure happens to route through the ECharts bridge instead.
- One stale docstring in `components.py` still names the deleted `ah-mark.svg` — low severity, no functional impact, the code itself correctly loads the replacement file.
- `ENGINE_PLAN.md`'s `ah-mark.svg` mentions are legitimately disclosed as historical (explicit header disclaimer) — not counted as a miss.

Not fixed, not touched — CredMgr's project, CredMgr's call. Reported per the operator's request.

## Session 2 (2026-08-18, later the same day) — universal config, real capability gaps filled, deeper audit

The operator's ask this pass: make every path/tool configurable rather than hardcoded to this
machine or this folder; audit for and fill genuine capability gaps (Mermaid, 2D/3D maps,
anything "must have" as a document/blueprint/graph engine); add a project-navigation system and
Claude Skills; verify everything actually works, not just that it parses. Summary of what
changed, in the order it was done:

### Universal configuration system

New: `engine.config.json` (root) + `tools/docgen/engine_config.py` (Python loader) +
`tools/lib/engine-config.mjs` (Node loader) + `CONFIGURATION.md`. Precedence everywhere: env
var > config file value > hardcoded fallback (== this package's original, tested behavior — so
adding the system was additive, not a behavior change, until someone actually overrides a
field). Refactored to use it instead of independently-hardcoded literals: `generator.py`,
`cli.py` (also fixed a real pre-existing bug — `_cmd_check` re-hardcoded `rules_dir`/
`version_json_path` inline instead of reusing `validate_doc_system.py`'s own overridable
resolution, two independently-hardcoded copies of the same path that could silently drift),
`validate_doc_system.py`, `adjudication.py`, `staged_content_scanner.py`, `echarts_bridge.py`
(node discovery), `ci_cost_control.py` (also fixed a dangling reference to the operator's
personal `~/.claude/rules/ci-cost-control.md` dotfile — generalized to describe the policy
instead of naming a file that won't exist on anyone else's machine), `trash-sweep.sh`,
`tools/graphify/build.mjs` (both the `codemap` call, previously bare with zero error handling —
now `requireTool()` with an actionable message — and the python-interpreter-path write, fixed
in the first session but re-verified consistent with the new shared loader), `build-deps.mjs` /
`build-coverage.mjs` / `build-admin-catalog.mjs` (host-project root + `srcRoot`/`detectorsDir`/
`frontendPublicDir` now config-driven instead of assuming the engine's own 2-levels-up
directory is the codebase being analyzed), `build-pipeline.mjs` (its `STEPS` table externalized
to `pipeline.example.json` — data, not code, so describing your own pipeline never means
editing the script), `open.sh` (browser-path discovery via two new tiny CLI helpers,
`tools/lib/print-tool-path.mjs`/`print-browser-path.mjs`, reading the same config).

**A real bug found and fixed as part of this**: `tools/graphify/graph-view.html`'s force-graph
canvas rendered at 0×0 (a genuine, pre-existing bug, not something this session introduced) —
`#graph` is `position:fixed;inset:0`, and the vendored force-graph library's Kapsule constructor
sometimes measures that as zero-size at init time. Fixed by explicitly passing
`.width()`/`.height()` from the container's actual `clientWidth`/`clientHeight` and re-applying
on window resize. Verified by screenshot before/after (blank canvas → real rendered graph).

### The `ah-` brand-prefix leak — found independently, fixed in this copy

While building the choropleth (below), the same `ah-` (AuditHunt) abbreviated CSS-class/
animation-name prefix that Session 1's CredMgr audit flagged as a residual leak in *CredMgr's*
copy was found in **this package's own** `charts.py`, `layered_workflow.py`, `geo_map.py`,
`visual.py`, `isometric3d.py`, `sequence_diagram.py`, `sankey.py` — 12 occurrences (`ah-figure`,
`ah-bar`, `ah-radar`, `ah-pie`, `ah-timeline`, `ah-heatmap`, `ah-geomap`, `ah-layered`,
`ah-iso3d`, `ah-sequence`, `ah-sankey`, `ah-pulse` keyframe) — Session 1's regex-based
de-branding pass targeted the spelled-out "AuditHunt"/"audithunt" and never caught the
abbreviated prefix. Renamed to `fig-*` throughout. A broader sweep then found the SAME class of
issue in two more places Session 1 also missed: `--ah`/`--ah-hi`/`--ah-dim` CSS custom
properties in `tools/docgen/template.html` and `demo/gallery.html` (the older v1 template,
separate from the v2 renderer files above) — renamed to `--accent`/`--accent-hi`/`--accent-dim`.
Re-verified: fresh build of `sample.md` after the rename, zero `ah-` occurrences in the output,
correct `fig-figure fig-figure-sample-flow` class present.

### Graph engine: real 3D, fixed a live CDN violation, added hierarchical/radial layout

`tools/graphify/graph-view.html`'s "3D" button previously injected
`<script src="https://unpkg.com/3d-force-graph@1">` live at click-time — an unpinned,
unchecksummed runtime CDN fetch that directly contradicted this same file's own vendored-2D-
library "no runtime CDN" rationale, and failed silently offline. Fixed by vendoring
`3d-force-graph@1.80.0` (MIT, `tools/graphify/vendor/3d-force-graph.min.js`, 1,313,897 bytes,
sha384 `63b6c2d8f04abbcba3c6dbe8e7e67ad4e786752551cc5b185812b88b97672ff53a6850d3a1d93ad6a3949137c89dac52`,
same PROVENANCE.md-in-vendor/ pattern as the 2D library) and pointing the lazy-load at the local
file. Verified: served over a local static server, clicked 3D, confirmed via
`read_network_requests` that zero requests hit unpkg or any CDN, and the WebGL view rendered
correctly (screenshot + the library's own rotate/zoom/pan control hint appearing, confirming
`ForceGraph3D` genuinely activated, not a silent no-op).

Separately: `dagMode` — a feature *already present* in the vendored 2D `force-graph` library,
just never wired into the UI — was exposed as a new "Layout" button cycling
force → top-down-tree → radial. Zero new dependency. Verified: built a real graph of this
package's own file tree, screenshotted all three layouts, confirmed the tree layout produces a
genuinely different, correctly-hierarchical arrangement (not just a relabeled force layout).

### New engine: `tools/mermaid-engine/` — Mermaid-syntax rendering, fully offline

Researched (WebSearch + GitHub/npm API, dated 2026-08-18): the official `mermaid` npm package
cannot render to SVG in bare Node (needs real DOM text-measurement APIs — confirmed against
mermaid.js's own unresolved GitHub discussions, not assumed). Every real option needs either a
real/shimmed browser (`@mermaid-js/mermaid-cli` via Puppeteer — ~150-280MB platform-specific
Chromium) or a from-scratch reimplementation. Chose `beautiful-mermaid@1.1.3` (MIT, Craft Docs)
over the Chromium route specifically because of this package's portability goal — 4 npm
packages total, no browser. Covers 6 of Mermaid's diagram types (flowchart, sequence, class,
state, ER, xychart) — a real, verified limit of the library, not a partial build; gantt/
git-graph/mindmap/journey/kanban/pie/quadrantChart/timeline are genuinely unimplemented
upstream (see `tools/mermaid-engine/README.md` for what to use instead per type).

**Found and fixed during build, not assumed clean**: the library's raw SVG output
unconditionally injects a live `@import url('https://fonts.googleapis.com/...')` with no option
to disable it (confirmed: passing a custom `font` value only changes which name is requested
from the same CDN). `render.mjs` strips this and substitutes a system-font stack before
returning output — verified via a real rendered SVG, `googleapis` string absent, screenshot
confirms the diagram still renders cleanly with the system font.

**A second real bug found and fixed** while integrating into docgen: `mermaid_bridge.py`
originally defaulted figure colors to literal `var(--bg)`/`var(--fg)` (matching docgen's own
page-level variable names) — this is a genuine CSS cycle when the embedded SVG sets its OWN
local `--bg`/`--fg` on its own root element (which the underlying library always does): the
property becomes the *guaranteed-invalid* value per the CSS Custom Properties spec, not "falls
back to the page's value" as the naive assumption would suggest. Confirmed by rendering (solid
black boxes, invisible black-on-black text) before diagnosing the cause via the raw SVG output,
not guessed. Fixed with a distinctly-named alias layer: `tools/docgen/tokens.py` now defines
`--mermaid-bg: var(--bg)` / `--mermaid-fg: var(--fg)` in both the dark and light theme blocks
(safe — different property name than what's being referenced, no cycle), and
`mermaid_bridge.py`/`generator.py` default to `var(--mermaid-bg)`/`var(--mermaid-fg)` instead.
Re-verified via computed CSS in-browser: `getComputedStyle(svg).getPropertyValue('--bg')`
matches the page body's own `--bg` exactly, in BOTH the dark and the (separately, and correctly)
toggled theme state — the diagram is genuinely theme-reactive, not hardcoded.

`tools/docgen/mermaid_bridge.py` wires `kind: "mermaid"` into the same figure-sidecar dispatch
as every other figure type (`echarts`, `geo_map`, etc.) — see `generator.py`.

### New capability: real-country-boundary choropleth maps (`geo_map.py`)

Researched: two viable options for country-level choropleth (ECharts `registerMap` + a
world-atlas TopoJSON dependency, or extending `geo_map.py` directly with a bundled GeoJSON
asset, stdlib-only, reusing the existing `_project()`). Chose the second — zero new runtime
dependency, stays inside docgen's existing deterministic/stdlib-only design law. Bundled
`tools/docgen/assets/world-countries-110m.geojson` — 177 countries, Polygon and MultiPolygon
geometries, `{"name": "..."}` properties only (no ISO codes — country names must match this
dataset's short/common form exactly, e.g. `"USA"` not `"United States of America"`;
`list_choropleth_country_names()` exists specifically so this doesn't have to be guessed).
Source: `github.com/holtzy/D3-graph-gallery` (GitHub API reports MIT license on the repo), data
itself is a widely-mirrored simplification of Natural Earth (public-domain geographic boundary
data — geographic facts are not independently copyrightable in the way the surrounding code is,
but the specific file's repo-level license is recorded here for completeness). Fetched via
`curl` from the repo's raw GitHub content, not modified after download.

`render_choropleth()` colors countries via 5 discrete `color-mix(in srgb, var(--shield-hi) N%,
var(--paper-2))` buckets rather than a computed RGB gradient — deliberately mirrors the existing
severity-lattice/achromatic-ramp pattern already used elsewhere in this engine (`tokens.py`),
and the practical payoff is that it's theme-reactive automatically, same mechanism as every
other figure, no extra wiring. `kind: "choropleth"` wired into the same sidecar dispatch as
every other figure kind (added after initially treating it as a manual-Python-call-only
capability — the sidecar path is more consistent with the rest of the engine and was added once
that inconsistency was noticed during the multi-figure integration test below).

Verified: rendered a standalone 5-country sample map (screenshot — genuinely recognizable
continent shapes, correct value-to-intensity mapping, working legend), then built a full
document (`tools/docgen/sample-multi-figure.md`, bundled as a permanent example) embedding the
choropleth alongside a Mermaid flowchart and an ECharts line chart in one build — all three
figures confirmed present with correct data via both screenshot and DOM text extraction.

### New: `tools/project_index/` — project navigation/index system

A flat, stdlib-only, JSON-backed registry (`PROJECT_INDEX.json` at the host project root) of
documents/charts/graphs/diagrams built for a project, plus an HTML dashboard
(`dashboard.py` → `PROJECT_INDEX.html`), so sustained work on a large project stays navigable.
Explicitly NOT automatic — nothing in the other four engines writes to it; an agent/user
registers what's worth remembering. CLI: `python3 -m tools.project_index.cli
register|list|search|stats|remove|dashboard`. Verified: registered 3 real artifacts, tested
list/search/stats, screenshotted the rendered dashboard (stat cards, section grouping, working
tag/status badges). One real bug caught during its own build: `_index_path()` initially checked
only the `ENGINE_PROJECT_INDEX_PATH` env var directly, bypassing the config-file-value layer
every other setting in this engine goes through — fixed by routing it through a proper
`engine_config.project_index_path()` function, same env var > config value > default
precedence as everything else, and re-verified with a fresh test.

### New: `CAPABILITIES.json`, `USAGE_GUIDE.md`, `skills/`

`CAPABILITIES.json` — machine-readable index of every capability across all five engines, entry
points, formats, and explicit `notImplemented` sections (so an agent reading it knows exactly
what's genuinely missing and where to go instead, rather than discovering it by trial and
error). `USAGE_GUIDE.md` — worked, verified examples (not hypothetical commands — every command
shown was actually run during this session). `skills/` — one Claude Skill per engine
(`document-engine`, `chart-engine`, `graph-engine`, `mermaid-engine`, `project-index`) plus an
`ultimate-engine` router skill, placed inside the package itself (not the operator's personal
`~/.claude/skills/`) so they travel with the engine.

### Final re-verification (this session)

`npm test` + `npm run simulate` (visual-engine, 30/30 + 22/22) and `node test.mjs`
(mermaid-engine, 6/6) all re-run and green after every fix above, not just once at the start.
`node_modules/` removed again after each install (native bindings are platform-specific —
vendoring them would hurt portability, not help it; `npm install` reproduces every result
above on any machine). A final independent parallel audit (4 read-only agents: de-brand
resweep across every file including everything added this session, portability resweep,
cross-document consistency check, and a fresh confirmation that neither AuditHunt nor CredMgr
was ever written to) — see the block below this section for its findings.

## Session 3 (2026-08-18/19, later still the same operator day) — audit-fix round, interpretive layer, precision guarantees, final re-verification

Session 2's own closing "4-agent final verification audit" (see above) surfaced real findings
that were still open when Session 2's summary was written. This session closed every one of
them, then answered two further operator requirements that arrived mid-session, then did one
more full-package re-verification pass.

### Audit-fix round (findings from Session 2's own closing audit, fixed this session)

- **`ah-` branding leak, round 2.** The first de-branding pass (Session 1/2) caught 12
  CSS-class/keyframe occurrences (`ah-figure`, `ah-bar`, etc.) inside `tools/docgen/*.py`
  renderers and renamed them to `fig-*`. This session's independent audit found the SAME prefix
  had also leaked into `tools/docgen/demo/README.html` (8 live `--ah`/`--ah-hi`/`--ah-dim` CSS
  custom-property occurrences) and two prose docs (`AUTHORING_PROMPT.md`, `README.md`) that the
  first pass's grep pattern missed. Fixed to `--accent`/`--accent-hi`/`--accent-dim` everywhere.
  Lesson written down for future passes: a de-brand sweep needs at least two independent grep
  strategies (literal name AND abbreviated-prefix) run separately, because a pattern tuned to
  catch one form reliably misses the other.
- **Undocumented broken pipeline, fixed.** `README.md`/`CAPABILITIES.json` claimed
  `layered_workflow` and five chart kinds (bar/radar/pie/timeline/heatmap) were reachable
  through the standard `<!-- figure:ID -->` + sidecar-JSON pipeline — but `generator.py` never
  actually imported or dispatched to any of them; the modules existed and worked in isolation
  but were never wired in. This was a real "documented but not implemented" gap, not a
  cosmetic one. Fixed: `generator.py` now imports all six, has `isinstance()` render-dispatch
  branches and `kind ==` dict-parsing branches for each, and six new `_*_spec_from_dict()`
  parser functions (`_bar_spec_from_dict`, `_radar_spec_from_dict`, `_pie_spec_from_dict`,
  `_timeline_spec_from_dict`, `_heatmap_spec_from_dict`, `_layered_spec_from_dict`), plus a
  shared `_data_sources_from_dict()` helper. **Verified by actually building a document that
  uses all six kinds** (not just code review) — see "Final re-verification" below.
- **Undisclosed external dependency, disclosed.** `graphify query`, referenced throughout
  `README.md` / `build.mjs` / `build-pipeline.mjs` / `build-coverage.mjs`, is a SEPARATE,
  non-bundled pipx package (`graphifyy`) that happens to share the "graphify" name with this
  package's own directory — nowhere disclosed, which would read as a missing/broken feature
  ("command not found") to anyone trying to use it. Fixed with explicit disclosure in
  `tools/graphify/README.md` and inline console messages at the call sites.
- **Dangling `$schema` reference, fixed.** `engine.config.json`'s `$schema` field pointed at
  `./engine.config.schema.json`, a file that was never created. Fixed to a self-describing
  string, matching the pattern `CAPABILITIES.json` already used for the same situation.
- **Two remaining literal project-name leaks, fixed.** `engine.config.json`'s `docSystem._readme`
  and `docs/design/doc-system/DOC_MANIFEST.md` both still contained the literal word
  "AuditHunt" in prose, despite the original de-branding pass — found by the later, more
  thorough audit. Both rewritten to generic phrasing. This re-applies the user's original
  "completely cleared of any project name" requirement to material a later pass found, not a
  scope change.

### Interpretive-knowledge layer (operator requirement, mid-session)

The operator's instruction, in full: a graph or blueprint is not only a display artifact — it
is a second, calculation-derived view of the same system a document already describes in text
and numbers, and the engine should carry that meaning forward, not just render shapes.
Concretely: every figure kind across the whole package (13 dataclasses: `VisualSpec`,
`SequenceSpec`, `SankeySpec`, `GeoMapSpec`, `ChoroplethSpec`, `IsometricSpec`, `BarSpec`,
`RadarSpec`, `PieSpec`, `TimelineSpec`, `HeatmapSpec`, `LayeredSpec`, `MermaidFigureSpec`) now
carries two optional string fields:
- `reader_question` — the specific question this figure answers that the surrounding prose
  alone doesn't make as immediately legible (mirrors chart-engine's own pre-existing MANDATORY
  `reader_question` field on ECharts job packets — this extends the same discipline to every
  native docgen renderer, which never had it before).
- `insight` — the actual takeaway, ideally cross-referencing the section of the document that
  independently derives the same conclusion in prose/numbers, so the figure and the text are
  two views of one source of truth rather than two disconnected artifacts.

`components.figure()` renders both, when present, as a `.figure-insight-block` under the
figure (new CSS in `tokens.py`). `INTERPRETATION.md` (new, ~15KB) is the full write-up: the
mechanism, worked examples of good vs. hollow `reader_question`/`insight` pairs, and how this
connects documents/blueprints/JSON specs as one interconnected system rather than three
separate artifact types.

### Precision guarantees (operator requirement, mid-session)

The operator's instruction: figure text must not overlap or run outside its box, lines must
not overlap, line start/end anchor points must land on the actual objects they connect (not
displaced), settings must render exactly where they belong, colors must be deliberately chosen
— following a real universal standard where one exists for that graph type, and left to the
authoring agent's judgment where none exists. `INTERPRETATION.md` Part 2/3 documents this
**against the actual code**, not as aspiration:
- Every native docgen renderer (`visual.py`, `sequence_diagram.py`, `sankey.py`, `geo_map.py`,
  `isometric3d.py`, `layered_workflow.py`, `charts.py`) has a `check_*_collisions()` function
  that fail-closes the build if any text bounding box overlaps another, or a label runs outside
  its container — this was already true before this session (docgen's existing fail-closed
  design discipline) and is now documented explicitly as the mechanism that answers the
  operator's requirement, rather than left implicit.
- Edge/line routing is computed from actual node bounding boxes, not free-hand coordinates —
  so anchor points are structurally correct by construction, not by convention.
- Color convention research (this session): real universal standards exist for very few chart
  types (e.g., choropleth sequential/diverging color-ramp conventions, a red/green
  polarity convention for financial deltas) — most diagram types (flowcharts, dependency
  graphs, sequence diagrams, layered workflows) have NO universal standard, only house styles.
  `INTERPRETATION.md` states plainly, per figure kind, which case applies: follow a cited
  universal convention, or the authoring agent chooses deliberately within the existing theme
  tokens (`tokens.py`) rather than inventing ad hoc colors — directly answering the operator's
  "check whether there are any must-follow rules... if there are none, let the agents choose."

### Final re-verification (this session, after every fix above)

- `npm test` + `npm run simulate` (visual-engine): 30/30 unit tests, 22/22 acceptance
  simulations, green.
- `npm test` (mermaid-engine): 6/6 diagram types, green.
- **All six newly-wired figure kinds (`bar`/`radar`/`pie`/`timeline`/`heatmap`/
  `layered_workflow`) built end-to-end through the real CLI** (`python3 -m tools.docgen.cli
  build`), not just imported or unit-tested in isolation — a real Markdown document with a
  6-figure sidecar spec produced an HTML file containing 8 `<svg>` elements and 7
  `.figure-insight-block` divs, with every `reader_question` string (including one containing
  an apostrophe, confirmed correctly HTML-entity-escaped rather than breaking the parse)
  present in the rendered output. Test files removed after verification.
- `__pycache__` and `node_modules` removed again after this round (portability — native
  bindings are platform-specific, `npm install`/`pip install` reproduce everything on any
  machine).
- **Re-confirmed AuditHunt and CredMgr were not written to by this session.** `git status
  --short` in this vault (`<credential vault>/`) shows only one pre-existing, unrelated dirty file
  (`CLAUDE.md`, a Session-2-era pointer-block edit about the design-handoff folder rename —
  present before this session began, not touched by any Ultimate Engine work). AuditHunt
  (`<workspace>/AuditHunt/`) shows two modified files (`Makefile`, `docs/INDEX.md`)
  that were flagged to the operator directly rather than reverted or investigated further: this
  session's own tool-call history never referenced the AuditHunt path, and the diff's shape (a
  13th `make verify` gate for a docs-index check, a regenerated auto-generated index file
  whose header now names the current HEAD commit) is consistent with AuditHunt's own
  documented daily-health-pass automation or a separate concurrent session doing AuditHunt-side
  work — not a side effect of a read-only recon + copy task that only ever wrote inside
  `<clone>/`. Not reverted: this package's own hard rule is "never touch the
  sources," and reverting another project's uncommitted work without understanding its origin
  would itself be an unauthorized cross-project action.

## Session 4 (2026-08-19) — full-engine reverification, gates proven by deliberate failure, five real defects fixed

The ask this pass: confirm every claim in `CAPABILITIES.json` is true *right now*; prove the
fail-closed rules actually enforce rather than reading the code and believing it; render one
example of every renderable kind in a single document from real data and hand-check the numbers;
close any real navigation gap; clean up; stamp.

Nothing in this section is a re-statement of an earlier session's evidence — everything below was
re-run or newly measured on 2026-08-19.

### What was verified as already-true (no change needed)

- `tools/visual-engine`: **30/30** unit tests, **22/22** acceptance simulations.
- `tools/mermaid-engine`: **6/6** diagram types.
- All 17 sidecar `kind` values dispatch correctly (13 explicit branches + the 4 `VisualSpec`-shaped
  kinds via `_FIGURE_RENDERERS`) — read in `generator.py` and then exercised, not assumed.
- `engine.config.json`: every field resolves on both the Python and the Node side (`codemap`,
  `python`, `node`, `git` all found; host root, doc-manifest and project-index paths all real).
- `mcp/server.mjs` speaks MCP over stdio and advertises exactly the **7** claimed tools.
- `graph-view.html` contains no live CDN fetch — its one `unpkg.com` string is a comment recording
  the removed fetch; the actual load is `vendor/3d-force-graph.min.js`.
- Both bundled samples (`sample.md`, `sample-multi-figure.md`) still build.

### The four gates, each triggered on purpose

Every one refused the build with a specific message and wrote **no output file**. Test documents
deleted immediately afterwards.

| Gate | How it was triggered | Result |
|---|---|---|
| `check_bar_collisions` | 6 long labels in a 300px-wide bar chart | `ChartRuleError`, 12 overlapping-label findings, exit 1 |
| L16 "every number is sourced" | a `geo_map` point with `value: 42` and no `data_sources` | `GeoMapRuleError: … no DataSource; every figure number must be sourced (L16)`, exit 1 |
| `manifest_drift` | a document with id-prefix `ZZ`, absent from `DOC_MANIFEST.md` | `[header] high: No DOC_MANIFEST.md row found for doc-type prefix 'ZZ'` → `BLOCKED`, exit 1 |
| choropleth unmatched country | `"United States of America"` (the dataset uses `"USA"`) | `ChoroplethRuleError: … does not match any country name in the bundled dataset`, exit 1 |

Worth recording: only the header gate produces a clean `BLOCKED` findings line. The three figure
gates surface as an unhandled traceback from the CLI. Fail-closed either way (exit 1, nothing
written) and the traceback names the file:line, but the two paths report differently. Left as-is —
see "Not verified / open" below.

### Five real defects found and fixed

Each was found by *measuring rendered output*, not by reading source. Each is a case the existing
tests could not see.

1. **`graphify/build.mjs` could not be pointed at anything.** It hardcoded the engine's own
   directory as the `codemap` cwd, so the documented "works against ANY codebase codemap can index"
   was only reachable by physically copying the engine into that codebase. `hostRoot()` already
   existed and was exported but unused here. Now uses it, so `ENGINE_HOST_ROOT=/path/to/repo node
   tools/graphify/build.mjs` works. Output still always lands in this engine's own `graphify-out/`,
   so a scanned tree is never written to. Verified both directions: default run maps this engine
   (130 nodes), overridden run maps an external tree (96 nodes) with nothing written into it.

2. **Numbered edge badges were drawn but invisible to the collision gate.** `visual.py`'s
   `check_collisions()` modelled node boxes, labels, notes, title, caption, legend, edge labels and
   edge conditions — but not the numbered badge it also draws on every `main` edge. The badge sat
   18px from the edge label, below the module's own 22px minimum, so it overlapped systematically.
   Measured in a browser: a 3×3px badge-on-label overlap on every labelled main edge. Fixed by
   adding the badge to the box list (with its own owner, so it is checked against its own edge's
   label) and moving the offset to 46px, derived from the label half-height + the 22px minimum +
   the badge radius. The gate then correctly rejected the first layout that did not clear it.
   Both bundled samples still build unchanged.

3. **`isometric3d` never checked that its scene fits its own canvas.** The projection origin is
   fixed and the emitted `viewBox` is always `0 0 width height` with no auto-fit, and
   `check_collisions()` compared boxes only against *each other* — so a scene projecting past the
   declared canvas was silently clipped. Measured: two box labels rendered outside the SVG. Added a
   containment check (footprint ∪ label box vs. the canvas) as a blocking `iso3d.bounds` finding.

4. **chart-engine: `treemap`/`sunburst` crashed on their own documented input shape.**
   `job.data.root.children ?? job.data.items` throws `TypeError` on the missing `root` before the
   `??` is ever reached, so the `items` fallback was unreachable. No preset, fixture or test
   covered either family. One character each (`root?.children`).

5. **chart-engine: a job with both `title` and `units` rendered the unit on top of the title.**
   `valueAxis()` set `axis.name` without `nameLocation`, and ECharts defaults that to `"end"` —
   the top-left corner for a vertical value axis, exactly where `titleBlock()` puts the title; and
   past the right edge, outside the SVG, for `bar_horizontal`. The `bubble` builder in the same
   file already set `nameLocation: "middle"` + a `nameGap`, so the correct pattern was established;
   `valueAxis()` simply did not use it. **This was already shipping**: the committed
   `SIM-08-queue-latency` golden had its `ms` label at `translate(114 33)`, inside the title's box.
   One golden re-baselined and classified in
   `tools/visual-engine/renders/diffs/2026-08-19-axis-name-placement.md`.

### The theme toggle did nothing (found while verifying the gallery, fixed)

`components.py`'s toggle sets `data-theme` on `<html>`; `tokens.py` declares the palette on
`[data-theme="dark"]` / `[data-theme="light"]`. But `generator.py` emitted `<body
data-theme="dark">` — re-declaring the dark palette on a **descendant** of the element the toggle
writes to, so body's values won the cascade for the entire document. The button flipped the
attribute, persisted it to localStorage and relabelled itself while changing nothing visible; the
light theme was unreachable. Removing the hardcoded attribute fixes it (`:root` already yields dark
with no attribute and no JS, so a no-JS reader is unaffected).

Removing it exposed a second instance of the same mistake one level deeper: `visual.py`,
`sequence_diagram.py`, `isometric3d.py` and `layered_workflow.py` stamped `data-theme="{theme}"`
onto every figure `<svg>` (default `"dark"`), which pinned 7 of 21 figures dark while the rest of
the page went light. The `theme` parameter exists for a real reason — `cli.py render --theme`
produces a standalone, deliberately-pinned SVG — so the attribute is now **opt-in**: the default is
`None` (inherit from the page) and it is emitted only when a caller explicitly passes a theme.
`diagram_graphs.py`'s three wrappers needed the same change, since they forwarded `"dark"`
explicitly. Measured after the fix: all 21 figures track the page in both themes; `--theme` still
pins a standalone render.

**Why this survived a previous session's "verified theme-reactive in both states" claim:** that
check compared the Mermaid figure's `--bg` against the page's `--bg`, which matched — both were
dark, because the page could not actually leave dark. Comparing two things that are wrong in the
same direction is not a verification. The check that found it renders the document, flips the
toggle, and reads `getComputedStyle(body).backgroundColor` on both sides.

### Navigation gap closed: `project_index verify`

The 50-document question — *would a fresh agent lose track of what has already been built?* The
index is the only instance-level map (`DOC_MANIFEST.md` registers document *types*, not
instances), nothing writes to it automatically, and — until this pass — nothing could check it
against reality. Demonstrated concretely: an entry pointing at a deleted file was reported by
`list`, `stats` and `dashboard` identically to a live artifact. A map that cannot be falsified
stops being worth reading exactly when the project gets big enough to need it.

Added `python3 -m tools.project_index.cli verify`: reports `MISSING` (registered path no longer
resolves) and `DUPLICATE` (two ids, one file) and exits 1 on either; `--scan DIR` additionally
lists `.html`/`.svg`/`.png`/`.pdf` files under `DIR` that no artifact claims, as advisory output
that never affects the exit code. Proven by planting a stale entry (caught, exit 1) and by
scanning a directory of unregistered build output (6 files listed, exit 0). Documented in
`tools/project_index/README.md` and `skills/project-index/SKILL.md`.

### The sample gallery

`examples/capability-gallery.md` + `_spec.json` → `examples/capability-gallery.html` (~557KB, one
self-contained file, zero external requests). 21 figures: all 15 native docgen kinds, 5
chart-engine families across 5 different capability groups (line, treemap, boxplot, funnel,
bar_horizontal), and a Mermaid flowchart. Every figure carries a real `reader_question`/`insight`
pair.

Data is real and non-sensitive: the *structure* of an unrelated local directory tree, surveyed
read-only with `find`/`wc -l`/`ls`/`codemap` — file-extension mix, per-module line counts,
per-directory and per-depth file counts, last-modified month. No file contents beyond line counts
over nine JavaScript modules; the tree's secret-bearing directories were excluded from every survey
by path and nothing was ever written into it. The two inherently-geographic figures say so on their
own captions and are sourced from this engine's own bundled boundary dataset, because a filesystem
has no geographic dimension — inventing a country mapping for file counts would have been a
prettier figure and a false one.

Accuracy checked three ways: 25 arithmetic identities across the insight claims recomputed from the
source numbers (all consistent — e.g. the Sankey's 155 + 43 = 198 reconciles the document's two
deliberately-different file-count denominators); every rendered value grepped back out of the HTML;
and the browser sweep for overlaps/overflow described above.

### Final state of this pass

- `npm test` 30/30 · `npm run simulate` 22/22 · mermaid-engine 6/6 — all re-run after every fix.
- `sample.md`, `sample-multi-figure.md`, `capability-gallery.md` all build clean.
- Browser-measured: 21 figures, 262 text elements, **0 overlaps, 0 out-of-box text, in both themes**.
- Brand-name grep across the gallery output: 0 hits for every retired term.
- `__pycache__`, `node_modules`, `graphify-out/`, `renders/current/` and all test scratch removed.

## Not verified (be aware before treating this as fully proven)

- `graphify`'s `build-deps.mjs` / `build-coverage.mjs` / `build-admin-catalog.mjs` now read their
  target paths from `engine.config.json` (Session 2) instead of hardcoding them, and that
  refactor was compiled/code-reviewed — but none of the three was actually RUN end-to-end
  against a real matching codebase this session (this package itself has no `src/`-rooted
  Python tree to point them at). `build.mjs` (the generic structure mapper, needs no
  project-shape config at all) and `build-pipeline.mjs` (needs only a `pipeline.example.json`-
  shaped data file, no target codebase) were both actually run and verified. Treat the other
  three's config wiring as "correct by code review," not "proven by execution," until run
  against a real target.
- Inline code-comment prose that lost "AuditHunt" as a sentence modifier (not a subject) was not
  exhaustively proofread line-by-line beyond the artifacts a broader grep sweep surfaced — the
  ones found (listed above, across both sessions) were fixed; others may remain undiscovered.
- The chart-preset and token *vocabulary* itself (`detector-*` naming, `shield`/`bronze`/`gold`/`ember`/`verify` color-role names, the actual brand hex values `#1E3A6E`/`#C4762A`/`#C0282A`/`#C8972A`/`#3DA875`) was deliberately left as-is — see "What was deliberately not renamed" above. This is a real, disclosed scope boundary, not an oversight: the operator asked for AuditHunt's actual templates to be the main templates, and these are genuinely design/domain vocabulary rather than encoded references to the project's name (unlike `"hunt"`/`ah-`, which were removed precisely because they weren't).
- The choropleth's source GeoJSON (`world-countries-110m.geojson`) uses country names in a
  short/common form with no ISO country-code field — matching against real-world data sources
  that use official names or ISO codes will need a small mapping table if you hit a mismatch;
  none is bundled.
- `tools/project_index/` has no concurrency protection (last write wins on the JSON file) —
  fine for one agent/person, not verified or intended for simultaneous multi-writer use.
- Swimlane/BPMN-lane diagrams and Venn/Euler diagrams were identified as gaps during Session
  2's research but deliberately not built (see `CAPABILITIES.json`'s `notImplemented` entries)
  — smaller, not-explicitly-requested capabilities, judged lower priority than the ones that
  were built. Not an oversight; a scoping decision, recorded here so it isn't rediscovered as
  a "surprise" gap later.

*Opened or re-scoped by Session 4 (2026-08-19):*

- **Figure rule-errors reach the CLI as unhandled tracebacks**, while header/manifest failures
  print a clean `[header] …` finding line and `BLOCKED`. Both are genuinely fail-closed (exit 1,
  nothing written) and the traceback names the file and line, so nothing unsafe follows from it —
  but two failure paths report in two different shapes, and only one of them reads as a
  deliberate refusal. Not changed here: catching them in `cli.py` would mean deciding whether a
  renderer rule-break is a *finding* (collected, reported with siblings) or an *exception*
  (immediate), and that is an error-model decision, not a cleanup.
- **`_EDGE_BADGE_OFFSET_PX = 46` is a good default, not a proof.** It clears the two edge
  geometries measured here (label on the route midpoint, and the ~6px-above-midpoint offset a
  vertical route produces). Other routings may need more. This is now safe rather than silent:
  since Session 4 the gate checks the badge box like any other, so a geometry the default does
  not clear fails the build instead of shipping an overlap.
- **`npm run simulate` rewrites the goldens that `npm test` guards.** `tests/run_simulations.mjs`
  writes `renders/golden/*` unconditionally, and `tests/regression.test.mjs` compares against
  those same files — so running simulate after a rendering change silently re-baselines and
  erases the drift signal. The documented order (`npm test && npm run simulate`) short-circuits
  on failure and avoids it, but nothing enforces the order. Always read the `npm test` result
  *before* running simulate. Not changed here: splitting "write goldens" from "run simulations"
  is a change to this engine's own evidence workflow and deserves its own decision.
- **The collision gates are now demonstrated sound on the cases measured, not proven complete.**
  Session 4 found two things the gates drew but did not check (edge badges; isometric canvas
  bounds). Both are fixed and both were found by measuring rendered geometry in a browser rather
  than by reading the checker. The honest generalisation: a gate can only enforce what it has
  been told to look at, and the way to find the next gap is another rendered-output measurement,
  not another code review. The browser sweep used here (every `<text>`/`<tspan>` bounding box,
  pairwise overlap + containment, in both themes) is cheap and worth re-running after any
  renderer change.
- **chart-engine and mermaid-engine figures are still outside docgen's collision gates** —
  unchanged from earlier sessions and correctly disclosed in `INTERPRETATION.md`. Session 4's
  browser sweep covers them empirically for this one document; it is not a standing guarantee.
  Two of the five defects fixed this pass were in exactly that uncovered area.
