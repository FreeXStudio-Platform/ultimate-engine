<!-- title: BUILD PLAN -->
# Build Plan — the governance + blueprint layer

**Written:** 2026-08-19, at the close of the session that reverified the engine.
**Baseline:** commit `5e5d78f` (stamped *Approved With Known Risks* @ `9a1c011`).
**Status of this file:** PLAN — decisions are settled. **Phases 1–7 are complete (`fcb6c39`,
`0e5d1f5`, `c956619`, Phase 4 at `0.5.0`, Phase 5 at `0.6.0`, Phase 6 at `0.7.0`, Phase 7 at
`1.0.0`).** The build is done; what the work becomes after `1.0.0` is `docs/plan/AFTER_1_0.md`. Phase 3
was verified by an independent deep pass on 2026-08-22 which returned 80 findings, 4 of them
CRITICAL; those are fixed or recorded in `docs/process/OPEN_GATES.md`, and the raw findings are in
`docs/process/VERIFICATION_LOG.md` Pass 6. Phase 4 began on 2026-08-24 with the gate clear —
`OG-181`, the last blocker, had been closed on 2026-08-23 with its bound stated rather than glossed
(see `OG-190`, which carries what it did not cover).

**No phase-blocking row is open, so Phase 7 may begin.** `docs/process/OPEN_GATES.md` carries
**0 open blocking rows**: rows in its `## Open` table whose disposition is `BLOCKS_PHASE_N`, for any
phase number, not just the one that has already passed (`OG-172`). Phase 5 raised five rows and closed none of them as
blockers: `OG-198` (six modules with no docstring, deliberately left so the depth ladder was not
tuned by the session that built it) is scheduled to Phase 6, and `OG-199`, `OG-200`, `OG-201`,
`OG-202` are examined and dispositioned with reasoning. `OG-203` — the second round of Phase-5 fixes
has no independent re-attack — is scheduled to Phase 7 alongside `OG-190`, which is the same class
of residue.

**This number is derived, not asserted.** The `counts` guard re-derives it from the register's
`## Open` table on every run and fails CRITICAL when the two disagree — which is exactly what it did
while this paragraph still said `2`. Every other row is fixed, demoted with reasoning, or scheduled
to a phase whose row below names that work — which is the only deferral the operator's phase gate
permits.

**This number is DERIVED, not asserted.** `tools/corpus_check`'s `counts` guard re-derives it
straight from `OPEN_GATES.md`'s `## Open` table on every run, and fails CRITICAL when the two
disagree. The sentence above used to end *"do not trust this sentence; re-derive it from
`OPEN_GATES.md`"* — an instruction that conceded the claim was unverified, that no code ever carried
out, and that was itself false the day it was read: it asserted zero blocking rows while `OG-181`
sat open with exactly that disposition. **A document that has to ask its reader not to trust a
sentence is describing a missing check, not a caveat.**

> **§3 Phase-1 corrections, applied 2026-08-19 from the implementation.** Five claims below were
> falsified by reading the code, and are corrected in place where they appear:
> `VERSION.json`'s `gate` key is **read by no code**; the CLI has **6** commands, not 4 (`index` and
> `content-index` already exist, so part of Phase 2 is already done); `_cmd_check` **already**
> invoked the hash-gate; the rulebook is **L1–L23**, not 8 laws (L17/L22 unreferenced → recorded
> *reserved*); and `TAXONOMY.md` had **no parser and no caller**, so it needed a loader wired in, not
> just a data file. Full detail in `HANDOFF.md`.

Read `docs/framework/DOC_WRITING_DOCTRINE.md` first. It is the *method*; this is the *work*.

---

## 1. The finding that shapes everything

> **Historical — written before Phase 1, kept as the record of why this plan exists.** Read the
> tense literally: at the time of writing the declarative half was missing. **It is not missing
> now** — Phase 1 restored it (`fcb6c39`) and `tools.health` `RULE-01…RULE-05` gate it every run.
> A planned thing is never written in the present tense (`HANDOFF.md` standing rule 5), and this
> section broke that rule for two phases; the fix is to date it rather than to silently rewrite
> history.

The engine already contained **~3,000 lines of governance machinery that ran even then**, and the
declarative half it consults had been left behind when the package was ported. This was not a
build-from-scratch job; it was a finish-what-exists job.

> **The `Lines` column was deleted 2026-08-21.** It was hand-maintained, went stale, was
> re-measured on 2026-08-20 with a note saying *"do not hand-maintain these"* — and **four of the
> six were stale again within the same session**, because the very fixes being recorded changed
> the files. A number a document restates about code it does not own cannot be kept true by
> discipline; the only durable fix is to stop stating it. `wc -l` is the source (`LESSONS.md` L-18).

| Module | Already does | Missing data it needs |
|---|---|---|
| `build_cache.py` | Content-hash incremental build cache, fail-open — **now exposed as `build --cached`** | *(nothing)* |
| `validate_doc_system.py` | SHA-256 hash-gate over locked rule files; a rule edit without a version bump + changelog entry + ADR is a violation | `VERSION.json`, the rulebook file set |
| `adjudication.py` | *Active* consultation of a contradiction matrix; `compute_change_impact` (change → dependent docs) | `CONTRADICTION.md`, `update_impact_map.json` |
| `build_index.py` | Scans built sidecars, groups by manifest type, emits browsable index, tier-aware | *(nothing — just unexposed)* |
| `classification.py` | Tier gates, manifest-drift, prefix taxonomy | `TAXONOMY.md` |
| `doc_manifest.py` | Manifest parse + row model | *(nothing — it ships with eight rows)* |
| `export_sanitizer.py` | 7-gate leak sanitizer | *(complete)* |

**Reference counts in code for files that do not exist:** `VERSION.json` ×22, `rulebook_files` ×16,
`update_impact_map` ×8, `rulebook_sha256` ×7, `CHG-700` ×5, `ADR` ×5, `CONTRADICTION.md` ×11,
`TAXONOMY.md` ×9, `content_index` ×9.

**Observable symptom, printed on every single build to date:**
```
L11 contradiction matrix absent at docs/design/doc-system/CONTRADICTION.md — skipping active consultation
```

The engine has been running in permanently degraded mode and saying so.

`DocHeader` has **no `version` field**. ~~The CLI exposes only 4 commands~~ — **corrected
2026-08-20: it exposes 6** — `build`, `render`, `manifest`, `check`, `index`, `content-index`.

---

## 2. Decisions taken (do not re-litigate without new evidence)

### D1 — Documents are the source of truth. SQLite is a derived index, never a store.

The corpus lives as Markdown + front-matter + JSON sidecars, in git: diffable, reviewable,
greppable, and the thing a stamp can be computed over. A **SQLite database is built *from* that
corpus** as a queryable index (joins, `FTS5` full-text search, "which module has no document")
and is **gitignored, rebuildable in seconds, and never authoritative.**

Why not SQLite as the store: a binary blob is not diffable, its merge conflicts are unresolvable,
and a stamp over it cannot be reviewed. Why not JSON-only: at corpus scale, "which claims resolve
to this symbol" is a join, and scanning a flat file for it is the thing that burns tokens.

*Verified on this machine:* `sqlite3` 3.53.3 in the Python stdlib, **FTS5 available**, `json1`
functions available. **Zero new dependency** — this preserves the engine's portability law.

This mirrors `build_cache.py`'s existing philosophy exactly: derived, content-keyed, fail-open,
degrade to a full rebuild.

### D2 — Saga: do not install. (Nothing to uninstall; it is not installed.)

`saga-mcp` (`github.com/spranab/saga-mcp`, npm `saga-mcp`) is a third-party MCP server: a
Jira-like tracker with **Projects > Epics > Tasks > Subtasks**, a per-project SQLite `.tracker.db`,
22 MCP tools (CRUD, notes, cross-entity search, activity log, batch ops). It is **not** in the
official Anthropic marketplace and is **not** currently installed — verified against
`installed_plugins.json`, `plugin-catalog-cache.json` (0 occurrences of "saga" in 435KB), and
`known_marketplaces.json`.

Rejected for three reasons, none of which is about its quality:

1. **Wrong problem.** Saga tracks *what to do*. This engine needs *what exists and whether it is
   true* — artifacts, versions, verification state, claims, contradictions. Saga has no notion of
   document version, claim→source resolution, stamp validity, or blueprint depth.
2. **It would become a second source of truth about project state** — precisely the drift failure
   mode D1 exists to prevent, and the one the doctrine names in §8.3 ("distrust the summary").
3. **Its 22 tools would load into every session's context** for a capability used rarely, against
   a task-tracking need the harness already covers natively.

The *good idea inside it* — a SQLite-backed queryable project state — is adopted under D1, on our
own schema, in stdlib, under our control.

### D3 — Reuse git for history. Build only the semantic layer.

Git already gives revision history, diffs, integrity, and blame. What it does not give is a
*semantic* version (`version`/`revision` on a document), a verification state, engine attribution,
or a changelog tied to rule-file hashes. Build those; do not build a parallel VCS.

### D4 — Adopt the **C4 depth ladder** as the encoded procedure.

The operator's stated procedure — *sketch → outer shape → modules → connections → what each module
does → deeper each step* — is, essentially exactly, the C4 model's four levels of zoom (Context →
Container → Component → Code). Adopt the C4 *model* (a proven, widely-used standard) as the depth
ladder rather than inventing a private one. Do **not** adopt Structurizr the tool: not installed,
JVM dependency, and our own renderers already cover the output.

Depth levels, normative:

| L | Name | What exists at this level | Completeness question |
|---|---|---|---|
| 0 | `sketch` | The node is named, nothing more | Does it exist? |
| 1 | `shape` | Purpose + boundary: what is in, what is out | What is it for? |
| 2 | `modules` | Its immediate children are enumerated | What is inside? |
| 3 | `connections` | Every edge in/out: direction, payload, gatekeeper | What talks to it, and through what gate? |
| 4 | `internals` | Each child's own behaviour and invariants | How does it work? |
| 5 | `detail` | Fully written document + verified claims + stamp | Is it true? |

A node's depth is the **highest level for which its evidence exists** — not what someone asserted.
The completeness report is then literally "where did we stop", per node.

### D5 — Wire ELK for auto-layout. It is already in the tree.

docgen's documented gap is *"no auto-layout algorithm exists in docgen for a plain edge-list"* —
every node diagram needs hand-supplied `x`/`y`. **`elkjs@0.11.1` is already installed** as a
transitive dependency of `beautiful-mermaid` (verified in `tools/mermaid-engine/package-lock.json`:
4 packages total — `beautiful-mermaid`, `elkjs`, `entities`).

So the single highest-value renderer improvement available costs **zero new dependency**: a small
bridge that hands an edge-list to ELK and gets back coordinates docgen's existing renderers can
consume. This also removes the largest authoring cost measured in the gallery build — the
hand-layout iterations against the 1.5×-short-side gap rule.

### D6 — Optional external renderers: allowed, never required.

Both are already installed on this machine and both must degrade gracefully via the existing
`requireTool()` pattern — the engine's offline, zero-required-dependency law is not negotiable.

| Tool | Path | Why it earns a place | Status |
|---|---|---|---|
| **D2** (`d2`) | `/opt/homebrew/bin/d2` | Native **nested containers** — the one thing our renderers do poorly and the exact shape of "module / in-module mapping". Better default aesthetics than Mermaid. Text source, so it stays diffable. | Optional renderer, Phase 4 |
| **Graphviz** (`dot`) | `/opt/homebrew/bin/dot` | Battle-tested layered/orthogonal layout; a fallback if ELK proves awkward for a given graph | Optional, evaluate in Phase 4 |

Rejected after consideration: **Structurizr** (JVM, not installed — but its *model* is adopted per
D4); **Vega-Lite / Observable Plot** (a better chart abstraction in principle, but ECharts is
already verified at 24 families and adding a second chart engine buys nothing this quarter);
**MkDocs / Docusaurus** (we already emit self-contained HTML with stronger guarantees);
**DuckDB / Kùzu** (overkill; SQLite + FTS5 covers it); **Vale** (prose *style*, not claim-checking —
our checker is the right instrument).

### D7 — Model routing is per phase, not per task.

Per the doctrine §3: strong model writes spines and annotates; cheap model fleshes, loops, and
resolves; the script terminates the loop. This is the single largest token saving available and it
is a *process* decision, not a tooling one.

---

## 3. The phases

> **The build ends at Phase 7, and only half the charter does.** What the work becomes after
> `1.0.0` — the gap-finding loop, what counts as a finding and what does not, and the one
> vocabulary decision the phase gate leaves behind — is `docs/plan/AFTER_1_0.md`. It is not a
> phase, it blocks nothing, and no register row may be dispositioned against it.

Each phase ends in something that runs. Do them in order; finish one before starting the next.

| # | Phase | Deliverables | Exit condition |
|---|---|---|---|
| **1** ✅ | **Restore the rule layer** — DONE `fcb6c39` | `RULEBOOK.md` (L1–L23, generic), `VERSION.json` (`rulebook_files` + `rulebook_sha256`; `gate`/`version` are declarative — no code reads them), `CONTRADICTION.md`, `update_impact_map.json`, `TAXONOMY.md` **+ `classification.load_taxonomy_prefixes()` wired into `cli check`** (the file had no parser and no caller) | **Met.** `cli check` exit 1 → 0; degraded line gone from every entry point; 9 L11 rows parse and the advisory fires; 5 gates each falsified red, then restored. |
| **2** ✅ | **Expose what exists** — DONE `0e5d1f5` | `build_cache` on the CLI (`build --cached`). ~~`index`~~ and ~~`content-index`~~ **already ship** — verified 2026-08-19 | A second build of an unchanged corpus is a measured cache hit; the index page renders. |
| **3** ✅ | **The checker — pointed at this repository's own corpus** — DONE `c956619`, verified by Pass 6 | `tools/corpus_check/` with the doctrine §5 guard set. **Two deliverables the phase now owns explicitly:** (a) **one Markdown table reader**, replacing the five that parse the same governance corpus today and provably disagree (`OG-36`) — a corpus checker that cannot read the corpus consistently is not a checker; (b) the residual **doc-claim findings** recorded in `docs/process/VERIFICATION_LOG.md` (`OG-47`), which are stale counts, dead citations and present-tense plans — *exactly* the classes `counts`, `crossrefs`, `built-claims` and `present-tense` exist to catch. | Every guard **deliberately falsified first** and shown red; then exit 0 on a clean corpus — and **this repository's own tracked documents are the corpus it is run against**, not three fixtures. `docs/CHARTER.md` purpose 2. |
| **4** ✅ | **Document identity + archive** — DONE `23e6354` | `version`/`revision`/`produced_by`/`verified_state` on `DocHeader` + schema; changelog automation; `docs/current/` (last verified) vs `docs/archive/<id>/vN/`; **and figure provenance — `data_sources` becomes a gate rather than a convention**. **Accepts the deferrals `OG-07` and `OG-63`** — a `SCHEDULED (Phase N)` row is only honoured when the phase names it here (`OG-171`) | **The acceptance set below (`A-1`…`A-9`) is the exit condition** — written before the code, per Rule 5. In one sentence: a document can be versioned, superseded and archived, and the stamp gate rejects a stamp on an edited body. The sentence is the summary; the list is what verification checks. |
| **5** ✅ | **The blueprint layer** — DONE `d90722c` | System model generated **from** front-matter + a small system spec (never hand-kept); renders through existing renderers + ELK (D5) + optional D2 (D6); `blueprint verify`; node → document drill-down; SQLite derived index (D1) with FTS5 | From one blueprint, an agent can name every module, its depth, its owning document, its gatekeepers — without reading the corpus. `blueprint verify` exits 1 on any drift. |
| **6** ✅ | **Procedure encoding** — DONE `aaee4d1` | C4 depth ladder (D4) enforced; completeness report ("where did we stop"); skills + rules that mandate tag/wire/date/version/changelog/stamp. **Accepts the deferral `OG-198`** — the six undocumented modules Phase 5's ladder measured, left standing on purpose so the metric was not tuned by the session that introduced it | The report distinguishes *sketched* from *documented* from *verified*, per node, from evidence. |
| **7** ✅ | **Harden + stamp + make the moat non-optional** — DONE 2026-08-30 | Full reverification; three-pass stamp; push; **accepts the deferrals `OG-09`, `OG-31`, `OG-136`, `OG-190`, `OG-203`, `OG-204`, `OG-205`, `OG-207` and `OG-209`**; **and the server-side half of the git moat** — a required status check (or equivalent) so `git push --no-verify` can no longer publish unchecked content (`OG-31`). This is listed as a Phase-7 DELIVERABLE, not a carried risk: no client-side hook can defend against `--no-verify`, so this is the only place it can actually close, and a phase may not begin while a known defect is open unless a later phase's declared work IS its fix. **Scope and anti-scope at full width: `docs/plan/PHASE7_SCOPE.md`** — what this phase owns, the order it has to happen in, and the eleven things it must refuse to do. | All suites green, browser sweep clean, stamp references a real commit, **and a push with `--no-verify` carrying a planted secret is rejected by something that is not a local hook.** |

### Phase 4 — the acceptance set, written before the code

**Rule 5, obeyed literally.** These lines were written on 2026-08-24 before a line of Phase-4 code
existed. The end-of-phase verification pass checks **exactly this list and stops**; it does not go
looking for more, and a finding outside the list is recorded in `docs/process/OPEN_GATES.md` rather
than held against the phase. The previous phase's exit condition was the prose *"the checker works"*
and could not terminate — three verification passes and two follow-up waves closed it.

Each line is a command and the result it must produce. `A-8` is `OG-63`, and it is deliberately
**last**: turning `data_sources` from a convention into a gate fails every numeric figure that
lacks sources, so it lands behind its own line instead of inside the identity work, where its blast
radius would be indistinguishable from a regression.

Each probe **creates or derives its own condition** (`LESSONS.md` L-37). Where a probe needs a
subject set from the live corpus it derives that set and asserts it is non-empty, so the probe
cannot pass by measuring nothing.

**A-1 — a document can be versioned.** Cutting a version assigns `v1`, writes the snapshot, and
records the cut.

```bash
python3 -m tools.docgen.cli archive list
```
Exit `0`, and every archived document reports `frozen`.

> **Deviation, stated rather than amended away (2026-08-24).** This line was written expecting all
> three of `docs/design/doc-system/TAXONOMY.md`, `docs/framework/DOC_WRITING_DOCTRINE.md` and
> `docs/design/doc-system/CONTRADICTION.md` to report `v1`. Two do. `CONTRADICTION.md` reports
> `v1 (superseded) v2` because the phase's own `OG-63` work made its row 8 fire for the first time,
> so the row's recorded outcome — *"Never — `L16` carries no gate-token mapping"* — stopped being
> true and the file had to be corrected under the RULEBOOK L9 protocol.
>
> **This is stronger evidence than the line asked for, not weaker.** The phase's exit condition is
> that a document can be *versioned, superseded and archived*; supersession was going to be
> demonstrated on a synthetic lab document, and it was instead demonstrated on a real, hash-locked
> rule file, with v1 preserved byte-identical and the drift caught by the gate **before** v2 was
> cut. The wording above is relaxed to what it should always have said — the freeze is a property
> of every archived document, not a claim about three specific version numbers, which is precisely
> the borrowed condition `LESSONS.md` L-37 warns against.

**A-2 — a frozen document that is edited is refused.** The probe appends a byte to a frozen
document inside a throwaway copy of the tree, asserts the corpus check goes RED naming that
document, restores it, and asserts it goes green again. Both directions, in one run.

```bash
python3 -m unittest discover -s tools/tests -t . -k frozen
```
Selects at least one test; all selected tests pass.

**A-3 — the header carries identity, and the schema agrees with the dataclass.** Every identity
field is parsed, validated, round-tripped, and present in `tools/docgen/schemas/doc_header.schema.json`
with the same name and type. A field added to one and not the other is a failure.

```bash
python3 -m unittest discover -s tools/tests -t . -k identity
```
Selects at least one test; all selected tests pass.

**A-4 — a document that claims it is verified, and is not, is refused.** `verified_state: verified`
without a valid hardening stamp over the current body is a blocking finding. The claim is the
assertion; the stamp is the evidence; the gate compares them.

```bash
python3 -m unittest discover -s tools/tests -t . -k verified_state
```
Selects at least one test; all selected tests pass.

**A-5 — the stamp gate rejects a stamp on an edited body, end to end.** The phase's headline exit
condition, falsified rather than asserted: the probe stamps a document at a real commit, edits the
body, and asserts the gate refuses it; then declares the drift the way the doctrine's own escape
hatch allows and asserts the gate accepts that instead.

```bash
python3 -m unittest discover -s tools/tests -t . -k stamp_drift
```
Selects at least one test; all selected tests pass.

**A-6 — a document can be superseded and archived.** Cutting a second version leaves the first
readable at its own path, reports it as superseded, and does not mutate its bytes. Supersession is
**derived** from the versions present, never stated in a field that could rot (Rule 2).

```bash
python3 -m unittest discover -s tools/tests -t . -k supersede
```
Selects at least one test; all selected tests pass.

**A-7 — the recorded history and the archive on disk cannot disagree.** A version directory with no
history row, a history row with no directory, and a snapshot whose bytes no longer match the hash
the history recorded are each a blocking finding. This is the changelog half of the phase: the
record is machine-written at the cut, and re-derived on every run.

```bash
python3 -m tools.corpus_check
```
Exit `0` on the tree as committed, and the identity guard reports a non-zero `checked` count.

**A-8 — `data_sources` is a gate, not a convention (`OG-63`).** A figure whose kind carries numbers
and declares no source is refused at build time. The probe derives the numeric kinds from the
engine's own figure-kind registry and asserts that set is non-empty, so it cannot pass by finding
no numeric kinds at all.

```bash
python3 -m tools.docgen.cli build examples/capability-gallery.md -o .docgen/p4-a8 && \
python3 -m unittest discover -s tools/tests -t . -k data_sources
```
The build exits `0`; the selected tests are at least one and all pass.

> **Corrected 2026-08-24:** this line was first written with `-o /tmp/p4-a8`, a command that cannot
> succeed — `generator._canonicalize_inside_repo` refuses any output path outside the repository
> root, so the build would have failed for a reason unrelated to provenance. `.docgen/` is
> gitignored and inside the repo. Only the path changed; what the line asserts did not.

**A-9 — nothing already standing was broken.** The phase does not trade a new capability for an old
one.

```bash
python3 -m tools.health --full
```
`HEALTHY`, exit `0`, zero failed and zero skipped.

### Phase 5 — the acceptance set, written before the code

**Rule 5, obeyed literally.** These lines were written on 2026-08-29 before a line of Phase-5 code
existed. The end-of-phase verification pass checks **exactly this list and stops**; a finding
outside the list is recorded in `docs/process/OPEN_GATES.md` rather than held against the phase.

**The phase has a measured specification, not a guessed one.** Phase 4 was the map's first real
test and was told to record what it had to open anyway. That list is what `blueprint/SYSTEM.md`
still cannot answer, and it is what `A-6` below turns into a derived surface: the JSON schemas
(the map never mentions them), the configuration surface and its environment variables, the CLI
command and flag inventory, the guard contract and how to register one, the figure-kind and
sidecar inventory, and what each health check *asserts* rather than merely its id.

Each probe **creates or derives its own condition** (`LESSONS.md` L-37). Where a probe needs a
subject set from the live corpus it derives that set and asserts it is non-empty, so the probe
cannot pass by measuring nothing.

**A-1 — the system spec resolves against the tree, and `verify` is clean on the tree as
committed.** The spec carries only what no artifact owns — the system's name, its containers, each
container's purpose, and the document that owns it. Every other fact in the model stays derived.

```bash
python3 -m tools.blueprint verify
```
Exit `0`, and the output names a non-zero count of containers, modules and documents checked.

**A-2 — `verify` exits 1 on drift, and the drift classes are falsified both ways.** A container
naming a module prefix that matches nothing; a module in the tree that no container claims; a
module claimed by two containers; an owning document that does not resolve to tracked content; and
a stale committed map. Each is planted in a throwaway copy of the tree, shown red, then restored.

```bash
python3 -m unittest discover -s tools/tests -t . -k blueprint_drift
```
Selects at least one test; all selected tests pass.

**A-3 — every module is owned exactly once.** The exit condition's *owning document* half, asserted
over the whole module set rather than a sample: the probe derives the module list from the model
and asserts the set of unassigned modules and the set of doubly-claimed modules are both empty.

```bash
python3 -m unittest discover -s tools/tests -t . -k ownership
```
Selects at least one test; all selected tests pass.

**A-4 — every module carries a depth derived from evidence, never asserted.** The C4 ladder of
`D4`, levels 0–5, where a node's depth is the highest level whose evidence exists *and* whose lower
levels all hold. The probe asserts the depth of a node changes when its evidence changes — it
removes a piece of evidence in a throwaway tree and asserts the derived depth falls.

```bash
python3 -m unittest discover -s tools/tests -t . -k depth
```
Selects at least one test; all selected tests pass.

**A-5 — every module names its gatekeepers, and the gatekeeper set is derived from the gates
themselves.** Not a hand-kept table: a gatekeeper is a registered guard, health check or gate whose
own source names the module or its path. The probe asserts the mapping is non-empty, that a module
known to be guarded reports its guard, and that inventing a gate name in a throwaway tree changes
the derived set.

```bash
python3 -m unittest discover -s tools/tests -t . -k gatekeeper
```
Selects at least one test; all selected tests pass.

**A-6 — the six surfaces Phase 4 had to open the tree for are answerable from the blueprint
alone.** Schemas, configuration + environment variables, the CLI command/flag inventory, the guard
contract, the figure kinds, and what each health check asserts. Every one is derived from the
artifact that owns it, and each is cross-checked against that artifact by the probe rather than
against a copy.

```bash
python3 -m unittest discover -s tools/tests -t . -k surfaces
```
Selects at least one test; all selected tests pass, and each of the six surfaces reports a
non-zero row count.

**A-7 — ELK computes the layout, and the committed layout matches a fresh run (`D5`).** The
auto-layout gap docgen has carried since the beginning — every node diagram needing hand-supplied
`x`/`y` — closed with the `elkjs` already present as a transitive dependency, so at zero new
dependency. **Node or `elkjs` absent is a SKIP with its cause named, never a FAIL** (`LESSONS.md`
L-25), and never a silent pass.

```bash
python3 -m tools.blueprint layout --check
```
Exit `0` when node and `elkjs` are present; exit `0` with an explicit `SKIP:` line naming the
missing dependency when they are not. Exit `1` only on real drift.

**A-8 — the SQLite index builds, answers the join, is gitignored, and refuses to be empty
(`D1`).** Derived, rebuildable, never authoritative. A builder that produces an empty result exits
non-zero (`RULES.md` Rule 6).

```bash
python3 -m tools.blueprint index && \
python3 -m tools.blueprint query "which modules have no document" && \
git check-ignore -q .blueprint && \
python3 -m unittest discover -s tools/tests -t . -k sqlite_index
```
Every command exits `0`; the index reports FTS5 available; the selected tests are at least one and
all pass.

**A-9 — nothing already standing was broken.** The phase does not trade a new capability for an
old one.

```bash
python3 -m tools.health --full
```
`HEALTHY`, exit `0`, zero failed and zero skipped.

### Phase 6 — the acceptance set, written before the code

**Rule 5, obeyed literally.** These lines were written on 2026-08-29 before a line of Phase-6 code
existed, and the end-of-phase pass checks **exactly this list and stops**. A finding outside the
list is recorded in `docs/process/OPEN_GATES.md` rather than held against the phase.

**What this phase is NOT allowed to do, stated first because it is the tempting mistake.** Phase 5
derived the depth ladder; Phase 6 must **enforce and report on it**, never re-derive it. A second
derivation of one fact is the defect this engine exists to catch, and the ladder already lives in
`blueprint/SYSTEM.json` under `depth`, with `stopped_because` naming the exact rung each node
failed. Equally, the six lifecycle steps below already have gates — `classification` tags,
`manifest_drift` wires, `identity` and `stamps` adjudicate. **The report REPORTS; the existing
gates keep ENFORCING.** Anything here that becomes a second enforcer of an existing rule is a
defect, not a deliverable.

Each probe **creates or derives its own condition** (`LESSONS.md` L-37), and each `-k` token selects
its **whole** group — Phase 5 measured that a token matching one probe of eleven satisfies the
letter of an acceptance line while gutting it.

**A-1 — the completeness report exists, and classifies every node into exactly one of three
states.** *sketched* (it is named, and perhaps says what it is for), *documented* (its inside,
edges, gatekeepers and probes are known), *verified* (its owning document is governed and its
verified claim is backed by evidence, not merely asserted). This is the phase's exit condition.

```bash
python3 -m tools.blueprint completeness
```
Exit `0`, and the output classifies a non-zero number of nodes, every node into exactly one state.

**A-2 — the three states are derived from evidence, and a node MOVES when its evidence moves.** The
probe changes one piece of evidence in a throwaway copy of the tree and asserts the node's state
falls; then restores it and asserts the state returns. A report that cannot move is a picture.

```bash
python3 -m unittest discover -s tools/tests -t . -k completeness
```
Selects at least one test; all selected tests pass.

**A-3 — the report answers "where did we stop" for the document lifecycle too, per document.** For
every governed document: which of **tag / wire / date / version / changelog / stamp** is complete,
each derived from the artifact that owns it — the header for tag and date, `DOC_MANIFEST.md` for
wire, the archive for version, `CHANGELOG.md` for changelog, the stamp for stamp.

```bash
python3 -m unittest discover -s tools/tests -t . -k lifecycle
```
Selects at least one test; all selected tests pass, and the report covers every governed document.

**A-4 — the ladder is ENFORCED by a ratchet, not by a report.** Each container declares a
`depth_floor` in `system.spec.json`; a container measuring below its floor is a **blocking**
finding. The floor may only ever be raised — a floor written below a container's measured depth is
itself refused, because a ratchet that can be loosened is a suggestion.

```bash
python3 -m unittest discover -s tools/tests -t . -k floor
```
Selects at least one test; all selected tests pass, and both directions are falsified: a container
dropped below its floor is refused, and a floor lowered beneath the measurement is refused.

**A-5 — `OG-198` is closed, and the containers it held down have risen.** The six modules with no
docstring are documented, so the four containers stuck at `sketch` measure higher. **The number is
re-derived, never asserted:** the probe reads the live model rather than a copied expectation.

```bash
python3 -m tools.blueprint completeness --check
```
Exit `0`; zero containers report `sketch`; and `docs/process/OPEN_GATES.md` records `OG-198` in its
`## Closed` table.

**A-6 — the authoring procedure is written down AND consistent with what the code enforces.** A
skill and a rule that mandate tag/wire/date/version/changelog/stamp, in which **every enforcement
claim resolves to a real gate**. A procedure that claims a check nobody runs is the defect this
engine exists to catch, one document over.

```bash
python3 -m tools.corpus_check
```
Exit `0` on the tree as committed, with the `built-claims`, `symbols` and `cross-doc` guards clean
over the new documents.

**A-7 — the report is DERIVED and committed, so a stale copy fails the push.** `RULES.md` Rule 6:
the ratchet, not the artifact, is what makes it trustworthy. The report joins the file set
`blueprint_files()` describes, so the existing staleness check covers it without a second checker.

```bash
python3 -m tools.blueprint verify
```
Exit `0`, and `python3 -m tools.blueprint check` reports the completeness report among the files it
matched against a fresh build.

**A-8 — nothing already standing was broken.** The phase does not trade a new capability for an old
one.

```bash
python3 -m tools.health --full
```
`HEALTHY`, exit `0`, zero failed and zero skipped.

### Token expectation

Building this costs roughly **250–400k tokens**. It does **not** save tokens during the build — it
costs them. Break-even lands around the 3rd–4th session of any project that then uses it, sooner
on a document-heavy one. The immediate saving available on day one is Phase 2, which is nearly
free.

### Phase 7 — the acceptance set, written before the code

**Rule 5, obeyed literally.** These ten lines were written on 2026-08-30 before a line of Phase-7
work — before the reverification ran, before any fix, before the stamp. The end-of-phase pass checks
**exactly this list and stops**; a finding outside the list is recorded in
`docs/process/OPEN_GATES.md` rather than held against the phase. This matters most in Phase 7,
because Phase 7's own deliverable is verification, and verification without a finite acceptance set
does not converge — it is interrupted (`DEEP_VERIFICATION_PASS.md` §3.1).

**This section sits AFTER `### Token expectation` on purpose.** Inserting it between the Phase-6
acceptance section and `### Token expectation` would extend the awk range that reproduces Phase 6's
frozen hash (`f67765dcfad1c32e`, recorded in `CHANGELOG.md [0.7.0]` and `OG-209`) to cover Phase 7's
bytes too, silently falsifying a freeze record this project exists to keep. Ordering yields to
correctness.

**Freeze protocol, stated so the close can reproduce it.** This section is hashed the moment it is
committed, before any Phase-7 work, and proven byte-identical at the close — an acceptance set edited
to fit what was built is not an acceptance set (`RULES.md` Rule 5). The recipe, identical in shape to
the one that produced Phase 6's `f67765dcfad1c32e`:

```bash
git show <freeze-commit>:docs/plan/BUILD_PLAN.md \
  | awk '/^### Phase 7 — the acceptance set/,/^## 4\. Open risks/' | sed '$d' \
  | shasum -a 256 | cut -c1-16
```

The frozen hash is recorded in the `CHANGELOG.md [1.0.0]` entry, **outside** this section so writing
it down does not change the bytes it measures. Marking Phase 7 complete edits the phase **table row**
above, never this section, so the hash survives the closeout.

Each probe **creates or derives its own condition** (`LESSONS.md` L-37), and each `-k` token selects
its **whole** group — a line saying "selects at least one test" is satisfied by a token matching one
probe of eleven, which Phases 5 and 6 both paid for.

**A-1 — the health floor holds.** Every suite the engine ships is green, nothing skipped.

```bash
python3 -m tools.health --full
```
`HEALTHY`, exit `0`, zero failed and zero skipped. `SUITE-05` runs 525+ counter-examples under a
fixed 600 s wall-clock budget; on a machine loaded by unrelated work it reports `TIMEOUT, not a test
failure` (`OG-212`'s documented residual, not a corpus defect), and the run is repeated on a quiet
machine, where the suite passes directly.

**A-2 — the corpus is clean over the tree as committed.** All eleven guards, including `stamps`,
green over every tracked document.

```bash
python3 -m tools.corpus_check
```
Exit `0`.

**A-3 — the derived map matches a fresh build.** No drift between `system.spec.json`, the tree, and
the committed `blueprint/`.

```bash
python3 -m tools.blueprint verify
```
Exit `0` (`verify` is `check` plus every spec-vs-tree disagreement, so it subsumes `blueprint
check`).

**A-4 — the completeness ratchet is level and the report is current.** No container below its floor,
no floor written with slack, and the committed report matches a fresh derivation.

```bash
python3 -m tools.blueprint completeness --check
```
Exit `0`.

**A-5 — `verified` is non-zero, as a CONSEQUENCE and not a target (`OG-207`).** Re-hardening and
stamping a container-owning document whose container already measures at rung 4 makes the top state
reachable, and it is then reached. The probe reads the live model, asserts `verified ≥ 1` on the tree
as committed, and asserts that removing the owning document's verified claim or its stamp drops the
count back to `0` — the consequence, falsified both ways. Not a number aimed at: `4.2` of
`PHASE7_SCOPE.md` forbids chasing it, and stamping a still-moving body to raise it would be worse
than leaving it zero.

```bash
python3 -m unittest discover -s tools/tests -t . -k verified_reachable
```
Selects at least one test; all selected tests pass.

**A-6 — `PROVENANCE.md`'s hardening stamp covers its body at a real commit (`OG-09`).** The stamp is
no longer `NEEDS RE-HARDENING`; the `stamps` guard reads the `artifact-hardened` line, resolves its
commit, and finds the body at that commit equal to the body now.

```bash
python3 -m tools.corpus_check --guard stamps
```
Exit `0`, the guard reports a non-zero `checked` count, and `PROVENANCE.md` is among the files it
checked (so the guard is proven to be looking at the stamp `OG-09` is about, not passing by ignoring
it).

**A-7 — the hostile push is refused by something that is NOT a local hook (`OG-31`).** A commit
carrying a planted, pattern-matching but non-live secret is pushed to the protected branch with the
verification-bypass flag set — so every local hook is skipped by design — and the push is **rejected
by the server** (a branch ruleset and/or a required status check), demonstrated by doing it, not
asserted. This is the one acceptance line that uses the bypass flag deliberately, to prove the server
catches what the skipped hook would have (`HANDOFF.md` standing rule 17); the secret never reaches
`origin`, because the rejection is what stops it.

```bash
bash tools/tests/moat_server_side.sh
```
Exit `0` means the hostile push was correctly **refused** by the server; the script asserts a
non-zero push exit and a server-origin rejection message, and targets a throwaway ref so no real
history is touched. Requires network and the `OG-31` mechanism deployed.

**A-8 — every accepted row is closed or re-dispositioned; none is left parked (`PHASE7_SCOPE.md`
§2).** The nine rows Phase 7 owns — `OG-09`, `OG-31`, `OG-136`, `OG-190`, `OG-203`, `OG-204`,
`OG-205`, `OG-207`, `OG-209` — are each moved to `## Closed`, or re-dispositioned to `NOT_A_DEFECT`
with reasoning a verifier can attack. **Nothing rolls forward:** there is no Phase 8, so no row may
remain `SCHEDULED (Phase 7)`.

```bash
awk -F'|' '/^## Closed/{exit} /^\| OG-(09|31|136|190|203|204|205|207|209) /{if ($4 ~ /SCHEDULED/){print $2; f=1}} END{exit f}' docs/process/OPEN_GATES.md
```
Exit `0` — no accepted row survives in the `## Open` table with a `SCHEDULED` disposition.

**A-9 — the version reaches `1.0.0` and the changelog agrees.** The build ends where the plan says it
does.

```bash
python3 -c "import pathlib,re,sys; v=pathlib.Path('PROJECT_VERSION').read_text().strip(); m=re.search(r'^## \[([0-9]+\.[0-9]+\.[0-9]+)\]', pathlib.Path('CHANGELOG.md').read_text(), re.M); sys.exit(0 if v=='1.0.0' and m and m.group(1)=='1.0.0' else 1)"
```
Exit `0` (`CONS-05` already asserts the two agree on every run; this pins the specific `1.0.0`
target).

**A-10 — the rendered gallery has no text overlaps or overflow, measured in a real browser.** The
exit condition's *browser sweep clean* half, run by the method `INTERPRETATION.md` Part 2 documents
rather than by re-reading the collision gates: build `examples/capability-gallery.md`, open the HTML
in a real browser, walk every `<text>`/`<tspan>`, compare bounding boxes pairwise for intersection,
and check each against its own `<svg>`'s box — in **both** themes.

```bash
python3 -m tools.docgen.cli build examples/capability-gallery.md -o .docgen/p7-a10
# then, in a real browser over the built HTML, in light AND dark:
#   the pairwise + against-viewBox bounding-box sweep of every <text>/<tspan>
```
The build exits `0`; the sweep reports **0** text-box overlaps and **0** out-of-box text in both
themes, and the measured element count is recorded with the result (it is `0`-of-what that makes the
zero worth anything — `LESSONS.md` L-18).

---

## 4. Open risks carried in from the baseline

Unchanged and still true; see `PROVENANCE.md`'s stamp block for the full register with bounds and
triggers. R1 (gate coverage demonstrated, not proven complete) and R2 (`simulate` rewrites the
goldens `npm test` guards) are the two that most affect this build — R2 is now also doctrine §8.7.
