# project_index — don't lose track of what you've built

> **Not bundled (note added 2026-08-20).** `docs/architecture.html` was part of this engine's source project and
> is not shipped with this package. The index this tool verifies is `PROJECT_INDEX.json` at the repo root.

> **Implementation moved (2026-09-24).** `index.py` in this directory is now a thin
> re-export shim; the real registry — `Artifact`, `register_artifact`, `verify`, the classification
> gate, everything — lives at [`tools/docgen/artifact_index.py`](../docgen/artifact_index.py). It
> moved so `tools.docgen.views` (audience views) can import it without depending on this
> package (`tools/project_index`) being vendored: a host that vendors `tools/docgen` alone but owns
> an unrelated `tools/project_index` of its own — one downstream host does, for its docs-index gate —
> can no longer shadow the registry. The CLI (`cli.py`) and dashboard (`dashboard.py`) below are
> unaffected: they import the public API through `index.py`'s shim exactly as before. If you need
> to patch or inspect this registry's *internals* (not just call its public functions), import
> `tools.docgen.artifact_index` directly — see `index.py`'s own docstring for why patching a name
> through the shim doesn't reach the real module's internal calls.

A flat, JSON-backed registry of every document/chart/graph/diagram this engine has produced
for a project, so a large body of work stays navigable instead of turning into "I have no
idea what's in this repo anymore." Not a build system, not a database — just a place to note
"I made this" once, so you (or an agent working the same project later) can ask "what do I
have" and get a real answer instead of re-scanning the filesystem.

## Why this exists

The other four engines (document-engine, chart-engine, graph-engine, mermaid-engine) each
produce output files, but none of them track what got produced across a whole project over
time. On a small project that doesn't matter. On a large one — dozens of generated documents,
charts for every report, diagrams for every subsystem — losing track of what already exists is
exactly how duplicate work and stale copies happen.

## Usage

```bash
# After generating something, register it:
python3 -m tools.project_index.cli register \
  --id q3-revenue-chart --path charts/q3-revenue.svg --type chart \
  --title "Q3 Revenue by Region" --section Reports \
  --summary "Bar chart, sourced from the CRM export" --tags "revenue,q3" \
  --status final --created 2026-08-18 --engine chart-engine

# Query it later:
python3 -m tools.project_index.cli list                     # everything
python3 -m tools.project_index.cli list --section Reports   # one section
python3 -m tools.project_index.cli list --type chart        # one type
python3 -m tools.project_index.cli search "revenue"         # substring search
python3 -m tools.project_index.cli stats                    # counts by type/section/status

# See it as a page:
python3 -m tools.project_index.cli dashboard                # writes PROJECT_INDEX.html

# Check the map still matches reality (exit 1 if not):
python3 -m tools.project_index.cli verify                   # missing files, duplicate paths
python3 -m tools.project_index.cli verify --scan docs       # + built files nothing has claimed
```

## `verify` — why a hand-maintained index needs one

Because nothing writes to this index automatically, it can drift from the filesystem in both
directions, and `list`/`stats`/`dashboard` cannot tell the difference: a registered artifact
whose file was deleted or moved is displayed exactly like one that is still there. On a project
with dozens of artifacts that is how the map quietly stops being worth reading — not by being
loudly wrong, but by being confidently stale.

`verify` is the check that makes the index falsifiable:

| Finding | Meaning | Affects exit code |
|---|---|---|
| `MISSING` | A registered `path` no longer resolves to a file — the artifact moved (update the entry) or was deleted (`remove` it). | yes → exit 1 |
| `DUPLICATE` | Two ids point at the same file, usually the same artifact registered twice. | yes → exit 1 |
| `unregistered` | With `--scan DIR`: a `.html`/`.svg`/`.png`/`.pdf` under `DIR` that no artifact claims. | no — advisory |

Paths resolve against the **index file's own directory**, which under the default configuration
is the host project root. `--json` gives the same report machine-readably. Run it at the start
of a session to find out whether the index can be trusted before relying on it, and at the end
to catch anything built but never registered.

Or call the Python API directly (`tools.project_index.index`) — the CLI is a thin wrapper
over `register_artifact`/`list_artifacts`/`search_artifacts`/`stats`/`remove_artifact`.

## Where the index file lives

`PROJECT_INDEX.json` at the host project root by default (same `hostRoot` resolution as the
rest of this engine — see `../../CONFIGURATION.md`), or wherever `ENGINE_PROJECT_INDEX_PATH`
points. One file, human-readable, safe to commit to your project's own repo if you want the
history of what's been built to travel with the code.

## Fields

| Field | Meaning |
|---|---|
| `id` | Your own stable identifier — re-registering the same `id` updates that entry in place. |
| `path` | Where the actual artifact file lives (relative to whatever makes sense for your project). |
| `type` | Free text, but the dashboard color-codes by convention: `document`, `chart`, `graph`, `diagram`, `map`, `mermaid`, `other`. |
| `title`, `summary` | Human-readable description. |
| `section` | A free-text grouping (e.g. "Architecture", "Q3 Report") — the dashboard groups by this. |
| `tags` | Comma-separated on the CLI, a list in the JSON/API — for `search`/`list --tag`. |
| `status` | Free text (`draft`/`review`/`final` are the suggested convention, not enforced). |
| `created`/`updated` | Caller-supplied date/timestamp strings. This module never calls the system clock itself — matching the rest of this engine's "no wall-clock in generated output" determinism discipline — so pass real dates when you register something. |
| `engine` | Which engine produced it (`document-engine`/`chart-engine`/`graph-engine`/`mermaid-engine`) — informational. |

## What this is NOT

- Not automatic — nothing in the other four engines calls this on your behalf. That's
  deliberate: auto-registering every render would fill the index with test/scratch output.
  Register the things worth remembering.
- Not a dependency graph or a build cache — it doesn't know whether a registered render such as
  `examples/capability-gallery.html` is stale relative to its source Markdown. It's a map of what
  exists, not a freshness tracker.
- Not multi-user/concurrent-safe — it's a JSON file, last write wins. Fine for one agent or
  person working a project; not a shared team database.
