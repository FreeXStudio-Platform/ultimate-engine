---
name: project-index
description: Track and query every document/chart/graph/diagram built for a project so large-scale work stays navigable. Use after generating something worth remembering, or when asked "what have we already built", "what documents exist", or similar large-project orientation questions.
---

# project-index — don't lose track of what you've built

Path: `tools/project_index/`. Python, stdlib only, no dependency on the other engines.

## When to use this

On a small task, skip it — it's overhead for one or two files. On sustained work across a
large project (dozens of generated documents/charts/graphs over many sessions), register
things worth remembering right after you build them, so a later question like "what reports do
we have for Q3" or "have I already built an architecture diagram for this" has a real answer
instead of requiring a filesystem crawl or, worse, relying on your own memory of a
long-finished conversation.

## Register right after creating something

```bash
python3 -m tools.project_index.cli register \
  --id <your-own-stable-id> --path <where-the-file-lives> --type document|chart|graph|diagram|map|mermaid \
  --title "..." --section "..." --summary "..." --tags "a,b,c" --status draft|review|final \
  --created 2026-08-18 --engine document-engine|chart-engine|graph-engine|mermaid-engine
```

Re-registering the same `--id` updates that entry in place — safe to call again after revising
something.

## Query before assuming something doesn't exist yet

```bash
python3 -m tools.project_index.cli search "revenue"      # substring, across title/summary/tags/section/path
python3 -m tools.project_index.cli list --section Reports
python3 -m tools.project_index.cli stats                 # counts by type/section/status — a quick orientation view
python3 -m tools.project_index.cli dashboard              # writes PROJECT_INDEX.html — open it, don't just read JSON
```

**Before building something that sounds like it might already exist, search first.**
Duplicating a chart or document that's already in the index because nobody checked is exactly
the failure mode this tool exists to prevent.

## Verify the index before you trust it — and again before you finish

```bash
python3 -m tools.project_index.cli verify                  # exit 1 if any entry is stale
python3 -m tools.project_index.cli verify --scan docs      # + built files nothing has claimed
```

Nothing writes to this index automatically, so it drifts, and `list`/`search`/`stats`/
`dashboard` **cannot tell a live artifact from a deleted one** — both display identically. A
stale index is worse than no index: it makes you skip work that no longer exists, or trust a
path that 404s.

Two points in a session where this matters:

- **At the start**, before answering "what do we already have" from the index — if `verify`
  exits 1, the answer you are about to give is partly fiction. Fix the entries first.
- **At the end**, with `--scan` over wherever you write output — anything you built this
  session but never registered shows up as `unregistered`, which is your prompt to register it
  while you still remember what it was for. `unregistered` is advisory and never fails the
  command; `MISSING` and `DUPLICATE` do.

## What NOT to do

- Don't register scratch/test output — this is for things worth remembering, not everything a
  render command ever produced.
- Don't expect this to auto-populate — none of the other four engines write to it
  automatically. That's deliberate (see `tools/project_index/README.md`'s "What this is NOT").
- Don't treat it as a freshness/staleness tracker — it records that something exists, not
  whether it's still up to date with its source.
