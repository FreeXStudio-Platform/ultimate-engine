<!-- title: PHASE 3 OVERLAP -->
# Phase 3 overlap table — what already exists before a line is written

**Status:** PLAN — an opening verification report (per the workflow in `docs/plan/NEXT_SESSION.md`) must run
*before* implementing anything. **Written 2026-08-22, at the start of Phase 3, against the tree at the floor commit.**

**Why this file exists, stated once.** `DOC_WRITING_DOCTRINE.md` §5 names nine mandatory guards.
`tools/health` already answers several of them. Building all nine from scratch would put two
checkers on one question, which is the two-sources-of-truth defect this engine exists to catch —
so the honest first task is to write down, per guard, **what exists, what it covers, and what is
missing**, and then build only the missing half.

The rule this table serves: **absorb and extend, never duplicate.** Where a `CONS` check already
answers a guard's question for part of the corpus, the guard calls it, widens it, or declares the
`CONS` check the owner — it does not re-implement it.

---

## The table

Derived 2026-08-22 by reading `tools/health/checks.py` at the floor commit. Every "covers" cell
below is what the code *does*, not what its name suggests — the difference is the defect class this
whole project exists around.

| # | guard | served today by | what that actually covers | what is missing |
|---|---|---|---|---|
| 1 | `symbols` | `CONS-07` | Backticked identifiers appearing in a `RULEBOOK.md` `**Status:**` **block** must exist in one of the `.py`/`.mjs`/`.sh` files cited in that same block. Block-aware (continuation lines and blockquotes included). | Every document other than `RULEBOOK.md`. Dotted module paths (`tools.health.checks.CHECKS`) are never resolved anywhere. A symbol cited in `HANDOFF.md`, `LESSONS.md` or `OPEN_GATES.md` is unchecked. |
| 2 | `counts` | `CONS-08`, `CONS-09` | `CONS-08`: three fact families (`rulebook <semver>`, `project <semver>`, `N passed / M failed / K skipped`) across exactly four state documents, with a `_MIN_CLAIMS` floor so it cannot pass vacuously. `CONS-09`: the charter's two measured counts (tracked / governed). | Every other count in the corpus. Gate counts, law counts, manifest-row counts, taxonomy-prefix counts, L11-row counts, test totals, guard counts — none re-derived. `OG-27` (a "7-gate" claim against a longer `PRECEDENCE`) was exactly this class. |
| 3 | `test-refs` | **nothing** | — | Every cited test name and every cited **check id**. This corpus cites check ids (`SUITE-05`, `CONS-08`, `STRUCT-03`…) constantly, in documents a session reads first, and nothing verifies one exists. |
| 4 | `built-claims` | **nothing** | `BUILD-01`/`BUILD-02` prove *documents* build; neither reads a prose claim. | Every documented command, subcommand and flag. `OG-58` is this class: two documents taught a build invocation that fails on its first line, and no check could see it. |
| 5 | `cross-doc` | `CONS-01…CONS-05` | Five specific pairs: impact-map prefixes ↔ taxonomy; manifest ids ↔ taxonomy; `RULEBOOK` locked table ↔ `VERSION.json`; emitted gate labels ↔ `PRECEDENCE` ↔ `CONTRADICTION.md`; `PROJECT_VERSION` ↔ `CHANGELOG.md`. | The register's own integrity, and the register ↔ plan agreement that `OPEN_GATES.md`'s own "Rules for this file" #6 states as a rule and leaves to human care. Measured at the start of this phase: it had **failed** — see `register` below. |
| 6 | `stamps` | `STRUCT-06` (partial) | The `SESSION_STATE.md` stamp parses, uses a state the document itself defines, names a real commit, and that commit is an ancestor of `HEAD`. | **The drift half — the half doctrine §8.2 is about.** Nothing compares a stamped document's *body* against the commit its stamp names, and no stamped document other than `SESSION_STATE.md` is checked at all. |
| 7 | `crossrefs` | `CONS-06` | Backtick-delimited repo-relative paths across all tracked Markdown resolve to **tracked** content, with `ABSENT_PATHS.md` as a reviewable registry of deliberate absences (first column only). | Markdown link targets — `[text](path)` and `[text](#anchor)` — are invisible to the backtick pattern. A dead link in a rendered document is exactly the "grep the outputs" class (doctrine §8.4). |
| 8 | `present-tense` | **nothing** | — | Everything. "A planned thing is never written in the present tense" is a standing rule in `HANDOFF.md` with, at the floor commit, **zero** mechanical enforcement. |
| 9 | `rendered-output` | **nothing** | `BUILD-01` builds three documents and discards the bytes. Nothing inspects a built artifact. | Everything. This is the guard whose absence let the renderer ship four green passes with 118 literal backticks in the flagship, and it is the missing capability `OG-49` and `OG-50` both wait on. |

### One guard the doctrine does not name, added on measured evidence

| # | guard | why it is here |
|---|---|---|
| 10 | `register` | Found while orienting for this phase, before any code was written: `OPEN_GATES.md` carried **eleven duplicate primary keys** (`OG-48`…`OG-58`), each naming two different findings — one in `## Open`, one in `## Closed`. Two numbering runs both started at `OG-48`. The register that the phase gate itself is answered from could not identify its own rows. It is a `cross-doc` defect one level lower than any of the five pairs `CONS-01…05` guard: not *two documents disagreeing*, but *one document unable to name its own contents*. |

---

## What this table decides

1. **`CONS-01`…`CONS-10` keep their questions.** `tools.corpus_check` does not re-ask them. Where a
   guard's territory overlaps a `CONS` check, the guard states the owner and checks only the
   remainder — recorded per guard in its own module docstring.
2. **Six guards are net-new capability**: `test-refs`, `built-claims`, `present-tense`,
   `rendered-output`, `register`, and the drift half of `stamps`.
3. **Three guards extend an existing check** rather than replacing it: `symbols` (beyond the
   rulebook), `counts` (beyond four documents and three fact families), `crossrefs` (Markdown links
   and anchors, which the backtick pattern cannot see).
4. **The corpus is this repository.** Every guard runs over the tracked Markdown corpus that
   `git ls-files` reports, not over fixtures — `docs/CHARTER.md` purpose 2.

## The bar every guard here is held to

Each is **falsified red before it is trusted**, with the failing input retained as a test that runs
on every health run (`docs/process/RULES.md` Rule 1) — and the counter-example covers the *class*,
not the instance. A guard that has only ever been seen green is a guard nobody has tested.
