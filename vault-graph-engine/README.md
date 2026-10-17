# `vault-graph-engine/` — why this directory ships, and what verified it

**Status: KEPT, not deleted. Verified 2026-08-23 (H7-deadweight lane).** This note exists so
that decision is readable from inside the directory itself, without cross-referencing five
other files.

## What this is

Two files:

- `VAULT_GRAPH_SPEC.md` — a design contract for a **different, sibling project's** (CredMgr V2)
  future in-app credential-vault node-graph UI. Its own header already says its two companion
  documents (`docs/01_ARCHITECTURE.md`, `docs/03_DATA_MODEL.md`) "are not shipped with this
  package" — that is expected, not an error: those two live in the source project, this spec is
  the retained design record.
- `force-graph.min.js` — a vendored copy (MIT, force-graph@1.51.4) of the same 2D force-graph
  library `tools/graphify/vendor/force-graph.min.js` also vendors.

**Zero consuming implementation.** No code anywhere in this repository reads
`VAULT_GRAPH_SPEC.md` or renders a view from it. `CAPABILITIES.json` states this explicitly:
`"status": "SPEC + VENDORED LIBRARY ONLY — ZERO CONSUMING IMPLEMENTATION. Do not report this as
a working component; it is design material."`

## Verified this pass (not assumed)

- `md5 vault-graph-engine/force-graph.min.js tools/graphify/vendor/force-graph.min.js` →
  **byte-identical** (`28a5d7eff1d1008f8803c38370ad1f48` both sides). Confirmed independently by
  SHA-256 in `docs/process/VERIFICATION_LOG.md` P8-123.
- This is **not an accidental duplicate**. `PROVENANCE.md` records that the two copies come from
  two different source projects (`tools/graphify` ← AuditHunt; `vault-graph-engine` ← CredMgr
  V2's own separate design contract) that both happen to vendor the same upstream library, and a
  six-agent deep completeness audit confirmed both copies present, byte-identical, and clean.
- The duplication **is a known, logged, accepted risk** — `VERIFICATION_LOG.md` L37: "two copies
  can drift independently" — carried at LOW severity because one side (`vault-graph-engine/`) is
  inert design material a downstream project will copy out, not code this engine's own build
  ever loads.
- This directory **is read**, just not executed: `tools/health/checks.py`'s completeness check
  (`CONS-06`) walks it as one of the repo's tracked top-level directories, and
  `tools/corpus_check/guards/symbols.py` actually parses `VAULT_GRAPH_SPEC.md`'s prose (it
  produced a real, since-fixed false positive — a JSON field `counts.totp` misread as a missing
  Python symbol — documented in that guard's own source and in
  `tools/tests/test_corpus_check.py`).

## Why it was not deleted

Every one of the above facts was already independently documented, before this pass, across
`CAPABILITIES.json`, `PROVENANCE.md`, `README.md`, `CONFIGURATION.md`, `skills/graph-engine/
SKILL.md` and `docs/process/ABSENT_PATHS.md`. Deleting this directory would not remove
deadweight — it would delete design material that a sibling project (CredMgr V2) is the intended
consumer of, contradicting six files that correctly describe it as intentional, and losing the
one written record of a UI contract (radial hierarchy layout, per-kind node sizing, lock/2FA/
grant overlay glyphs, mandatory accessible tree-view mirror) that graphify's own generic
hierarchical/radial layout is the closest already-working equivalent of, per
`skills/graph-engine/SKILL.md`.

**What was missing, and is fixed by this file:** none of the six files above lives inside
`vault-graph-engine/` itself, so a reader who opens only this directory had no way to learn any
of this without already knowing where to look across the rest of the tree. This README closes
that gap.
