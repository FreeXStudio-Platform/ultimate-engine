<!-- title: CONFIGURATION -->
# Configuration — universal paths, zero required setup

This engine works out of the box with no configuration at all. Every path and tool it needs is
either resolved relative to its own files (never breaks, never needs config) or discovered
automatically (git root, PATH-searched binaries) with a fallback that reproduces this package's
original, tested behavior. **You only need this file when you want to change something** — point
the engine at a host project's own doc-governance layout, a non-default browser, or a custom
`codemap`/`python`/`node` install.

## The one file: `engine.config.json`

Lives at the engine's root, next to this file. Read it once — every field has an inline
`_readme` explaining what it's for and what happens if you leave it alone. It is **not required
to exist**: every consumer falls back to a hardcoded default (the values already in the shipped
file) if it's missing, unreadable, or malformed.

## Precedence (highest wins)

1. **Environment variable** — every configurable field names its own env var (e.g.
   `ENGINE_HOST_ROOT`, `ENGINE_DOC_MANIFEST_PATH`, `ENGINE_CODEMAP_BIN`). Set one to override
   just that field for one shell session or one CI run, without touching the config file.
2. **`engine.config.json`'s `value`/`path` field** — edit this file to make an override
   permanent for everyone using this copy of the engine.
3. **Built-in fallback** — what ships today. Matches this engine's own tested, documented
   behavior exactly, so an engine with zero configuration behaves identically to before this
   system existed.

## How host-project root resolution works

Most doc-governance paths (the manifest, the confidential-docs boundary, the rulebook) are
relative to a "host project root" — the repo you've dropped this engine into, not necessarily
where the engine's own files live. Resolution order:

1. `ENGINE_HOST_ROOT` env var, if set.
2. `engine.config.json`'s `docSystem.hostRoot`, if set (not `null`).
3. `git rev-parse --show-toplevel` from the current working directory — this is why dropping
   `tools/docgen/` and `tools/visual-engine/` anywhere inside your own git repo and running
   commands from within it "just works" with zero config: the engine finds your repo root on
   its own, wherever it's nested.
4. This engine's own directory, as a last resort (so running the engine completely standalone,
   with no host project around it — e.g. building the bundled `sample.md` — still works).

## What's configurable, section by section

### `tools` — external binaries
`codemap` (graphify's structure-graph builder), `python`, `node`, `git`. Each has an env var,
an optional explicit `path`, and a PATH-searched fallback list. `codemap` and `node` fail with
an actionable message if missing (`requireTool()`/`require_tool()`); `git` degrades gracefully
(git-hook features just skip).

### `docSystem` — docgen's doc-governance layout
`docSystemDir`, `docManifestPath`, `versionJsonPath`, `confidentialDir`, `trashDir`,
`contentIndexPath`, `authoredDocsRoot`. All relative to `hostRoot`. Point these at your own
project's doc-governance layout instead of the bundled minimal example (see
`docs/design/doc-system/DOC_MANIFEST.md` — it ships with eight rows (`ADR`, `CHG`, `WF`, `SPEC`,
`SYS`, `API`, `GUIDE`, `REF`), enough for the
bundled sample document to build; replace it with your own project's real registry).

### `graphify` — the four host-shape-dependent example builders
`srcRoot`, `detectorsDir`, `frontendPublicDir`, `pipelineStepsFile`. `build.mjs` (the generic
directory-structure mapper) needs none of these four — it takes its scan target from the same
**host root** resolution described above, so `ENGINE_HOST_ROOT=/path/to/repo node
tools/graphify/build.mjs` maps that repo. Its output always goes to this engine's own
`graphify-out/` whatever it scanned, so pointing it at a read-only tree is safe. The other four (`build-deps.mjs`, `build-coverage.mjs`, `build-pipeline.mjs`,
`build-admin-catalog.mjs`) are **worked examples** tuned to one Python project's `src/`-rooted
layout — point these fields at your own project, or copy the files and adapt the parsing logic
for a different language/layout. `pipelineStepsFile` is the cleanest of the four to adapt: it's
pure data (`tools/graphify/pipeline.example.json`) — author your own file in the same shape
instead of editing code.

### `browsers` — graphify's "open as an app window" convenience feature
Candidate install paths per browser, tried in order; falls back to the OS `open`/`xdg-open`,
then to just printing the URL. Nothing else in this engine depends on a browser being found.

### `security.allowRuntimeCDN`
Defaults to `false`. Every capability in this engine already works at `false` — force-graph,
3d-force-graph, and ECharts are all vendored locally, so this flag has nothing to disable
today. It exists so a host project can assert its own no-CDN policy explicitly in one place,
and so any future addition to this engine has a flag to check before it's allowed to add one.

### `mermaid`
See `tools/mermaid-engine/README.md` for what's supported and why (gantt/git-graph/mindmap are
intentionally out of scope — see that README for the alternative).

### `projectIndex`
`path` — where `PROJECT_INDEX.json` lives (default: `hostRoot`). See
`tools/project_index/README.md`.

## Worked examples

**Point this engine at a different host project**, from a shell:
```bash
export ENGINE_HOST_ROOT=/path/to/my-project
python3 -m tools.docgen.cli build my-project/docs/some-doc.md
```

**Use a custom `codemap` install location**, permanently, by editing `engine.config.json`:
```json
"codemap": { "envVar": "ENGINE_CODEMAP_BIN", "path": "/opt/tools/codemap", ... }
```

**Point graphify's dependency-graph builder at your own `src/`-equivalent** (e.g. a `lib/`
directory):
```json
"graphify": { "srcRoot": "lib", ... }
```

**Describe your own pipeline instead of the bundled security-scanner example**: author
`my-pipeline.json` in the same shape as `tools/graphify/pipeline.example.json`, then either set
`ENGINE_GRAPHIFY_PIPELINE_STEPS_FILE=/path/to/my-pipeline.json` or edit
`engine.config.json`'s `graphify.pipelineStepsFile`.

## For an agent reading this to configure the engine

If you are an AI agent embedding this engine into a project and need to adapt it:
1. Read this file and `engine.config.json`'s inline `_readme` fields first — don't guess field
   names or grep source files for hardcoded paths; there shouldn't be any left (see
   `PROVENANCE.md`'s portability-audit section for what was found and fixed, and report any new
   ones you find the same way — file:line, fix, then update the config schema).
2. Prefer env var overrides for anything session-scoped or CI-scoped; edit `engine.config.json`
   directly only for a permanent, shared change.
3. `docSystem` fields matter most when embedding `tools/docgen`; `graphify` fields matter most
   when embedding `tools/graphify`'s four example builders (`build.mjs` needs none of them —
   it reads only the host root, like `docgen` does). `tools/visual-engine` and
   `vault-graph-engine` need no host-project configuration at all — they're self-contained.

## Environment variables outside `engine.config.json`

Added 2026-08-20 (`OG-30`): these are read directly by the git moat and the health system, not
through `engine.config.json`, and were documented nowhere. They are listed here because a variable
an operator cannot discover is a variable that gets rediscovered by breaking something.

| variable | read by | effect |
|---|---|---|
| `ENGINE_SKIP_PRECOMMIT=1` | `tools/hooks/pre-commit` | Skips both commit-time gates. **Announces itself loudly** on stderr — a silent bypass is indistinguishable from a gate that ran. |
| `ENGINE_SKIP_PREPUSH=1` | `tools/hooks/pre-push` | Skips all three push-time gates. Also announces itself. |
| `ENGINE_PREPUSH_FULL=1` | `tools/hooks/pre-push` | Runs `tools.health --full` (both npm suites) instead of fast mode. Slower; use before a milestone push. |
| `ENGINE_SECRET_SCAN=<path>` | both hooks | Overrides the portfolio secret scanner's location (default `~/.claude/scripts/secret-scan.sh`). **Fails closed** if the path is not executable — "no scanner" is never "no secrets". |
| `ENGINE_DOC_SYSTEM_DIR=<dir>` | `tools/docgen/engine_config.py` | Relocates the **whole** rule layer together — taxonomy, `DOC_MANIFEST.md`, `VERSION.json`, the content index and the authored-docs root (`OG-22`, closed). Bare filenames resolve under it, paths containing `/` resolve host-root-relative, absolute paths are used as-is. |
| `ENGINE_<SECTION>_<KEY>` | `tools/docgen/engine_config.py` | Per-field override of any `engine.config.json` value; the pattern is declared in the config file itself. Highest precedence. |

**`git commit --no-verify` / `git push --no-verify` are not in this table on purpose** — they are
git's own flags, not the engine's, and they bypass every hook silently with no artifact for an audit
to find. No client-side hook can defend against them (`OG-31`).
