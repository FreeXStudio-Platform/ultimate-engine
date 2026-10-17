<!-- title: ARCHITECTURE -->
# Architecture — the whole system, from the outside in

**Status:** DESIGN — descriptive, normative about *layering only*. **Derived from source, twice,
independently:** once by the orchestrator reading the tree and once by a fresh Pass-6 analyzer that
had not seen that reading. Where the two disagreed, the artifact decided. Written 2026-08-22.

**Why this file exists.** Every other document here describes one part. Nothing described how the
parts *connect* — which meant the connection points, where defects actually live, were the least
documented and least checked surface in the project. Four of Pass 6's findings were exactly that:
a gate wired into one of two consumers, a CLI command nothing ever called, a config value that
disabled a gate, a guard reading the wrong half of an artifact.

**How to read it.** Outer shape first, then modules, then the ports between them, then the gates at
each boundary, then what is deliberately *not* guarded. That order is the operator's, and it is the
C4 depth ladder decision `docs/plan/BUILD_PLAN.md` D4 already adopted: Context → Container →
Component → Code.

> **No counts are restated here.** `docs/process/RULES.md` Rule 2: if a machine can derive it, prose
> must not state it. Every number below is a command you can run. This file was written after a pass
> in which eight restated numbers were found stale in four documents.

---

## 1. Outer shape — what this is

**In:** authored Markdown carrying a YAML doc-system header, plus an optional sibling
`<stem>_spec.json` describing its figures.
**Out:** a self-contained HTML document (optionally JSON and PDF), figures rendered to inline SVG,
and a set of registries describing what exists.

```
   author's Markdown ──▶ DOCGEN ENGINE ──▶ self-contained HTML
        + _spec.json         │
                             ├── consults ──▶ RULE LAYER      (the laws, as data)
                             ├── gated by ──▶ GATE SPINE      (export_sanitizer)
                             └── figures ──▶ RENDER ENGINES   (ECharts, Mermaid)

   the repository itself ──▶ CORPUS CHECKER ──▶ findings about the corpus
                        └──▶ HEALTH SYSTEM  ──▶ one verdict about the engine
                        └──▶ GIT MOAT       ──▶ refuses a bad commit or push
```

Seven subsystems. The first four are the product; the last three are the scaffolding
`docs/CHARTER.md` warns must stay proportionate to it.

| # | subsystem | owns | entry point |
|---|---|---|---|
| 1 | **Docgen engine** — `tools/docgen/` | Markdown → design-system HTML, figures, registries | `python3 -m tools.docgen.cli` |
| 2 | **Rule layer** — `docs/design/doc-system/` | the laws *as data*: rulebook, taxonomy, manifest, contradiction matrix, impact map, version/lock | read by the engine at runtime |
| 3 | **Render engines** — `tools/visual-engine/`, `tools/mermaid-engine/` | charts and diagrams, out-of-process, vendored, offline | `npm test`, invoked via the bridges |
| 4 | **Project index** — `tools/project_index/` | the registry of built artifacts | `python3 -m tools.project_index` |
| 5 | **Health system** — `tools/health/` | *is the engine green?* — one command, one verdict | `python3 -m tools.health` |
| 6 | **Corpus checker** — `tools/corpus_check/` | *is the corpus true?* — claims against source and built output | `python3 -m tools.corpus_check` |
| 7 | **Git moat** — `tools/hooks/` | refusing a bad commit or push | installed by `tools/hooks/install.sh` |

---

## 2. Layering — the dependency law

**Measured, and acyclic.** Derive it yourself:

```bash
python3 - <<'EOF'
import ast, pathlib, collections
pkg = collections.defaultdict(set)
for p in pathlib.Path("tools").rglob("*.py"):
    if "__pycache__" in str(p): continue
    src = ".".join(str(p).split("/")[:2])
    for n in ast.walk(ast.parse(p.read_text())):
        mods = ([n.module] if isinstance(n, ast.ImportFrom) and n.module else
                [a.name for a in n.names] if isinstance(n, ast.Import) else [])
        for m in mods:
            if m.startswith("tools") and ".".join(m.split(".")[:2]) != src:
                pkg[src].add(".".join(m.split(".")[:2]))
for s in sorted(pkg): print(f"{s:<22} -> {', '.join(sorted(pkg[s]))}")
EOF
```

```
tools.lib  ◀──  tools.docgen  ◀──  tools.corpus_check  ◀──  tools.health
                     ▲                                            ▲
              tools.project_index                            tools.tests
```

**`tools/lib` imports nothing first-party.** That is the law this layer exists to hold — it is where
code lives that both the engine and the checkers above it must agree about, and a helper that
reached back up into its own callers would be a cycle waiting for the first import-order change.
There is currently one such helper, and it is there because five copies of it disagreed
(`OG-36`): `tools/lib/md_table.py`, the one Markdown table reader.

**Health sits above the corpus checker, which sits above the engine.** So health can run the corpus
checker (it does, as `CONS-11`), the corpus checker can build documents with the engine (it does,
in `rendered-output`), and the engine knows about neither.

---

## 3. The document journey — one build, end to end

`generator.build()`, in order. Every step is a boundary where something can be refused.

| # | step | what can go wrong here |
|---|---|---|
| 1 | `_canonicalize_inside_repo(md_path)` | a path outside the repository — refused |
| 2 | `parse_header` → `validate_header` | a missing or malformed header coerces to `Tier.SECRET`, the fail-closed sentinel |
| 3 | `doc_manifest.read_manifest(...)` | the registry the header is checked against |
| 4 | `_load_sibling_figure(...)` | a document referencing figures whose sidecar is gone — **blocking** |
| 5 | `_render_markdown_body` → `_render_html` | figures are rendered by the bridges and **inlined before the gate runs** |
| 6 | `_canonicalize_inside_repo(out_dir)` | output confinement |
| 7 | `local_preview` | tier gate relaxed **only** under the confidential vault |
| 8 | **`export_sanitizer.run_gates(...)` per output format** | **on the FINAL RENDERED BYTES**, not on the source |
| 9 | write, only if the gate passed | inside the per-format loop, immediately after that format's gate |
| 10 | `adjudication.annotate_with_contradictions(...)` | advisory only — fail-open **by contract**, can never change `ok`; runs **after** every write, on the merged result |

> **Steps 9 and 10 were listed the other way round** (`OG-133`). The heading says this table is
> `generator.build()` *"in order"*, and adjudication was shown preceding the write — but
> `run_gates` and `write_text` are a pair inside the per-format loop, and
> `annotate_with_contradictions` runs once afterwards on the merged result. The order matters to a
> reader deciding whether adjudication can influence what lands on disk: it cannot, because the
> bytes are already written. That is exactly the fail-open contract the row states, and the
> sequence now shows it instead of implying the opposite.

> **Step 8 is the most misunderstood line in the system, so it is stated here.** The build-time
> spine already inspects *rendered output*. The corpus checker's `rendered-output` guard is
> therefore **not** a duplicate of it — it asks a different question of the same bytes (unrendered
> Markdown residue; contrast pairs derived from the built stylesheet). A future reader tempted to
> "de-duplicate" them would be removing a real check.

---

## 4. The gatekeepers, by boundary and in order

Six boundaries. For each: what it refuses, and whether it fails open or closed.

| # | boundary | gate | fails |
|---|---|---|---|
| 1 | **author time** | `tools/docgen/AUTHORING_PROMPT.md` conventions | advisory — a human reads it |
| 2 | **build time** | `export_sanitizer` gate spine, ordered by `PRECEDENCE`, `hash_gate` first | **closed** — nothing is written unless the gate passes |
| 3 | **commit time** | `tools/hooks/pre-commit`: L14 classification placement + a secret scan of the **index** | **closed**, and it asserts its own gate count |
| 4 | **push time** | `tools/hooks/pre-push`: engine health + a secret scan of the **pushed range** | **closed**, three gates, count asserted |
| 5 | **health time** | `tools/health` — structure → rule layer → consistency → build → suites | **closed**; a raising check is a FAIL, never a skip |
| 6 | **corpus time** | `tools/corpus_check` — every guard carries an anti-vacuity floor | **closed**; a guard that examined less than its floor is demoted to FAIL |

Derive the live contents of any of them:

```bash
python3 -c "from tools.docgen.export_sanitizer import PRECEDENCE; print(len(PRECEDENCE), 'gate labels'); [print(' ', g) for g in PRECEDENCE]"
python3 -c "from tools.health.checks import CHECKS; print(len(CHECKS), 'checks')"
python3 -m tools.corpus_check --list
```

### The three deliberate fail-**open** paths, and why each is safe

A fail-open path is a decision, not an accident, and each is named here so it stays one.

| path | why open |
|---|---|
| `adjudication` (L10/L11 consultation) | It only ever *appends advisory INFO*. It cannot change `GateResult.ok` in either direction, so a missing contradiction matrix degrades the advice, never the verdict. |
| `build_cache` | Any doubt rebuilds. A corrupt or absent cache is a full build, and entries are digest-verified so a tampered output rebuilds rather than being reported as a hit (`OG-49`, closed). |
| `engine_config` | Returns `{}` on a read error, because it is imported at module load by every entry point — raising there would take down the very command that reports the problem (`L-17`). `STRUCT-08` is the compensating check, and `confidential_dir_relative()` now **refuses** a value naming the repository root rather than degrading silently (`OG-92`). |

---

## 5. The health system — five stages, in dependency order

Foundation first, so a broken foundation never produces a confusing cascade downstream.

| stage | asks |
|---|---|
| **1 structure** | do the files the system depends on exist — and is the moat actually installed? |
| **2 rule layer** | does the governance data parse, and does the hash-gate hold? |
| **3 consistency** | does any file contradict another? *("no part lies to another part")* |
| **4 build** | does a real document still build, end to end? |
| **5 suites** | the full test suites, the lint/type pin, and the retained moat attacks |

**A SKIP is never a pass.** It means the check could not run and its question is open. `--full` and
`--strict` make a SKIP fatal; a default run tolerates it, **and the pre-push hook runs a default
run** — so a skip is accepted at push time. That is stated plainly because it was documented
backwards until Pass 6 (`OG-83`), and the exposure it left on a fresh clone was real.

---

## 6. The rule layer is live, not decorative

Every governance file has real readers. Verify:

```bash
for f in RULEBOOK.md TAXONOMY.md CONTRADICTION.md DOC_MANIFEST.md VERSION.json update_impact_map.json; do
  printf '%-26s <- ' "$f"; grep -rl --include='*.py' "$f" tools/ | grep -v __pycache__ | tr '\n' ' '; echo
done
```

| file | consulted by |
|---|---|
| `RULEBOOK.md` | the L9 hash gate, the build cache key, `CONS-07`, and the corpus guards that read it (`git grep -ln RULEBOOK tools/corpus_check/guards/`) |
| `TAXONOMY.md` | `classification` (prefix validation), the CLI, `CONS-01`/`CONS-02` |
| `CONTRADICTION.md` | `adjudication` (active L11 consultation), `RULE-02`, `CONS-04` |
| `DOC_MANIFEST.md` | `doc_manifest`, `models`, `classification` (drift), `build_index`, `RULE-05` |
| `VERSION.json` | `validate_doc_system` (the lock), `engine_config`, `CONS-03`, and **`CONS-08` reads its `version`** |
| `update_impact_map.json` | `adjudication` (L10 blast radius), `RULE-03` |

**The lock is bidirectional and self-certifying, and that bound is stated rather than implied.**
`VERSION.json` declares both *what is locked* and *the digest*, and is not itself a member of the
locked set — so `CONS-03` compares it against `RULEBOOK.md`'s own table **both ways**. Editing a
locked file requires the two-step: set `rulebook_sha256` to `PENDING`, *then* `--write-hash`.
`--write-hash` alone on a live mismatch does nothing, by design.

---

## 7. What is deliberately NOT guarded

The most useful section, because an unnamed gap is indistinguishable from an oversight.

| gap | status |
|---|---|
| `git commit --no-verify` / `git push --no-verify` | **Unclosable client-side.** No local hook can defend against it. Scheduled to Phase 7, where a server-side required check can (`OG-31`). |
| A determined actor with commit rights | Out of scope by declaration — `docs/process/THREAT_MODEL.md` scopes the moat to *accidental publication by a cooperating developer* (`L-22`). |
| Semantic correctness of prose | `DOC_WRITING_DOCTRINE.md` §7: direction-and-soundness errors are the ~⅓ no script reaches. That is what the deep verification pass is for. |
| Gate 9's overlap comparison | Runs and is fail-closed, but no caller supplies sibling text and no corpus document declares `variants` — a true no-op here, scoped in `RULEBOOK.md` L18 (`OG-93`). |
| A locally-modified `node_modules` with an unchanged lockfile | Both lockfiles are in the cache key; hashing thousands of vendored files would cost more than the accident is worth (`OG-49`). |

---

## 8. Adding something — the extension points

| to add… | edit |
|---|---|
| a **law** | `RULEBOOK.md` + the L9 two-step re-baseline + a `CHANGELOG.md` entry |
| a **doc type** | `TAXONOMY.md` (prefix) and `DOC_MANIFEST.md` (row) — `CONS-01`/`CONS-02` check they agree |
| a **build gate** | a `gate_*` function in `export_sanitizer.py` **and** a position in `PRECEDENCE` — `CONS-04` fails if a gate emits a label with no position |
| a **health check** | one line in `CHECKS` (`tools/health/checks.py`) |
| a **corpus guard** | the module, **plus** its name in the import block **and** in `GUARDS` (`tools/corpus_check/guards/__init__.py`) — two edits in one file — **and, since Phase 5, a third**: `python3 -m tools.blueprint build`, because the guard registry is now part of the derived map, so a new guard leaves `blueprint/` stale and the retained suite fails the push until it is rebuilt. Verified against the source rather than assumed: a verifier registered a twelfth guard with the two documented edits and left the tree push-blocked. The tests derive their set from `GUARDS`, so a registered guard is covered immediately (`OG-80`), and the suite also asserts its floor is ≥ 1 (`OG-122`) |
| a **renderer** | a bridge beside `echarts_bridge.py` / `mermaid_bridge.py`, degrading gracefully when its engine is absent (D6) |

**Two of those six are a single edit — a health check and a renderer. Read the table, not this
sentence.** (`OG-144`: it said *"Four of those six"*, and was wrong the moment the corpus-guard
row was corrected to two edits under `OG-133`'s sibling. `OG-132` rewrote this same sentence for
contradicting the same table; the fix moved the number and kept the habit — `L-26` a fourth time.
The durable form is not a better count, it is **no count**: the table is the source and this line
now names only the two rows a reader can check in one glance.) Read the table rather than
this sentence: a **law** needs three (the rulebook, the L9 re-baseline, a changelog entry), a **doc
type** two, and a **build gate** two. Those are the drift risks, which is precisely why each has a
`CONS-*` check standing over it — `CONS-01`/`CONS-02` for the doc-type pair, `CONS-04` for the
gate/precedence pair, `CONS-03` plus the hash gate for the law.

This sentence read *"Every one of those is a single edit"* until 2026-08-22 (`OG-132`), directly
above a table showing three rows that are not. A summary line that contradicts the table it
summarises is worse than no summary: the table is correct and someone reads the sentence instead.
Where a change needs N edits in N files, the register carries the risk and a check enforces the
agreement — that is the actual design, and it is a stronger one than the claim it replaces.
