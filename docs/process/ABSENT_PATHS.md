<!-- title: ABSENT PATHS -->
# Absent paths — files this repo names but deliberately does not contain

**Status:** PROCESS — machine-read. `tools/health` `CONS-06` consults this file.

**Why it exists.** This engine was extracted from a larger source project. Several documents,
prompts and module docstrings still name files that stayed behind. `CONS-06` fails on any repo-style
path cited in a tracked Markdown file that does not resolve — which is exactly the guard we want for
*new* dead pointers, but it cannot distinguish a stale pointer from a deliberate statement that
something is absent.

**This file is that distinction, written down and reviewable.** A path listed here is declared
absent *on purpose*, with a reason. Anything not listed and not present still fails the check.

**Rules**
1. A path goes here only when its absence is **intentional and explained** — never to silence a
   real stale pointer. The fix for a stale pointer is to fix the pointer.
2. Every row states *why* it is absent and *what replaced it here*, so a reader is never left
   hunting for a file that was never coming.
3. **Present-but-untracked counts as absent.** `CONS-06` resolves a citation against tracked
   content (`git ls-files`), not the filesystem, so a gitignored build artifact that happens to
   exist on this machine does NOT satisfy a citation. It used to: the check passed here and
   failed on every fresh clone, and because the pre-push moat runs health, a fresh clone could
   not push until it had run `npm install`. Cite such a path only with a row here.
4. If a listed path is ever added to the repo, delete its row — a stale entry here is the same
   defect class this file exists to prevent.
5. This file is **not** a locked rulebook file: it is expected to shrink as pointers get cleaned up.

## Declared absent

| path | why it is absent | what serves its role here |
|---|---|---|
| `docs/design/DOC_DESIGN_SYSTEM.md` | Source-project visual law; not bundled | `tools/docgen/assets/tokens.json` + `tokens.py` + `components.py` (RULEBOOK L15/L21) |
| `docs/DOC_CLASSIFICATION_AND_INVENTORY.md` | Source-project tier law; not bundled | `docs/design/doc-system/RULEBOOK.md` (L2/L3/L14) + `TAXONOMY.md` + `DOC_MANIFEST.md` |
| `docs/INDEX.md` | Source-project document index; not bundled | `docgen index` / `content-index`, and `PROJECT_INDEX.json` |
| `tools/visual-engine/node_modules/` | Gitignored, regenerable: installed by `npm install`, and deliberately not vendored because `@resvg/resvg-js` ships platform-specific native bindings | `npm install` in that package, per the bootstrap in `HANDOFF.md` |
| `tools/docgen/__pycache__/` | Gitignored Python bytecode cache, regenerated on every import | nothing — it is build output, named here only because `PROVENANCE.md` records what was excluded from the extraction |
| `docs/system/SYSTEM.json` | Source-project system registry; not bundled | `engine.config.json` + `CAPABILITIES.json` |
| `docs/pm/POOL.md` | Deferred-item register named by `ENGINE_PLAN.md` §4b that **was never created** | `docs/process/OPEN_GATES.md` |
| `docs/architecture.html` | Source-project rendered architecture page | `vault-graph-engine/VAULT_GRAPH_SPEC.md` and the gallery |
| `docs/archives/_trash` | The default value of `docSystem.trashDir`, which `tools/docgen/trash-sweep.sh` creates on first use. Nothing has been swept in this repository, so it has never existed here. Cited for the first time on 2026-08-24 by `docs/process/OPEN_GATES.md` `OG-192`, which exists to warn a reader that it is one letter away from `docs/archive/` and means the opposite thing — a warning that has to name both paths to be worth reading. | `docs/archive/` is the version store (`docSystem.archiveDir`); this path is the trash, and naming it is the whole point of the row that cites it |
| `docs/claude/DOCUMENT_REWRITE_PROTOCOL.md` | Source-project method document | `docs/framework/DOC_WRITING_DOCTRINE.md` |
| `docs/01_ARCHITECTURE.md` | Source-project companion to the vault-graph spec | none — the spec is self-contained here |
| `docs/03_DATA_MODEL.md` | Source-project companion to the vault-graph spec | none — the spec is self-contained here |
| `tools/PROVENANCE.md` | Source-project provenance file | `PROVENANCE.md` at the repo root |
| `tools/docgen/assets/ah-mark.svg` | Source-project brand mark; deliberately excluded during de-branding | none — the engine is domain-neutral (RULEBOOK L20 is *declared*, unbundled) |
| `tools/docgen/bank_doc_lint.py` | Source-project domain linter; excluded during extraction | `tools/docgen/export_sanitizer.py` + `tools/health` |
| `tools/docgen/demo/INDEX.html` | Source-project demo index | `examples/capability-gallery.html` |
| `SYSTEM-INSTRUCTION.md` | The system instruction issued to the operator in field-trial round 1 — what the engine is for, and the standing rules. It lives in the hand-over package **outside this repository** and is deliberately not copied in: a second copy of one text is the drift defect `RULES.md` Rule 2 exists to catch. Its identity is pinned instead by the sha256 recorded in `docs/plan/FIELD_TRIAL_ROUND_1.md` §2. | `docs/plan/FIELD_TRIAL_ROUND_1.md` records the round's protocol and both briefs' hashes; `docs/plan/FIELD_TRIAL.md` is the programme it implements |
| `PROMPT.md` | The task issued with that instruction — eight stages plus the measured starting state — in the same outside package and for the same reason. | `docs/plan/FIELD_TRIAL_ROUND_1.md` §3 records the baseline it states and §4 what it must produce |
| `REPORT.md` | The operator's completed report. **It does not exist yet by construction** — it is produced during the round and returns in the hand-over package, never in this repository. | `docs/plan/FIELD_TRIAL_ROUND_1.md` §5, which the review session completes from it |
| `tools/docgen/hooks/pre-push.sample` | **Deleted 2026-08-20, not merely unbundled.** It could never have worked: its third step ran `cli check --strict` with no input path, so it exited 2 on a usage error and would have blocked every push. Two registers still name it as history, which is deliberate — deleting the record of a defect is how the defect returns. | `tools/hooks/pre-push` (installed by `tools/hooks/install.sh`, verified live by `tools.health` STRUCT-03) |
| `tools/docgen/hooks/pre-commit.sample` | Deleted 2026-08-20. It installed a strict subset of `tools/hooks/pre-commit` (placement only, no secret scan of the index), and two competing pre-commit hooks is the two-sources-of-truth defect this engine exists to catch. Named in `CHANGELOG.md` as history, which is deliberate. | `tools/hooks/pre-commit` (installed by `tools/hooks/install.sh`, verified live by `tools.health` STRUCT-04) |
| `docs/current/` | Scheduled: Phase 4's "last verified" document root (`BUILD_PLAN.md` §3, `OG-07`). | nothing yet — documents build beside their source or into `-o` |
| `docs/confidential/` | **Runtime path, deliberately never committed.** `generator.build` refuses to write a CONFIDENTIAL/SECRET document anywhere else, so the path is enforced in code; git cannot track an empty directory, and a vault with contents is precisely what must not ship. | `engine_config.confidential_dir()` creates it on demand |
| `tools/docgen/assets/fonts/jetbrains-mono-400-italic.woff2` | **Deleted 2026-08-21** (`OG-42`): it was a byte-identical copy of the upright face while being declared to CSS as a real italic, so italic monospace rendered upright in every document AND the browser would not synthesize an oblique, precisely because a "genuine" italic was supplied. Named here only by the audit trail that recorded its removal. | nothing — no italic monospace face is declared, so the browser synthesizes an oblique, which is visibly italic |
| `tools/docgen/bank_judgement_collect.py` | **Deleted 2026-08-20** (`OG-16`): 123 lines, zero callers, documented nowhere. Named only by the audit trail that recorded its removal. | nothing — git history is the archive |
| `tools/corpus_check/guards/probe_vacuous.py` | A **lab probe**, never a repo file. Quoted verbatim in `docs/process/VERIFICATION_LOG.md` Pass 6, where a verifier registered a deliberately vacuous guard in a disposable `git archive` lab to prove the counter-example suite could not see it. | nothing — the finding it proved is `OG-80`, and the fix derives the tested guard set from `GUARDS` |
| `tools/not_built_yet/` | A **lab probe**, never a repo file. The path `present-tense`'s counter-examples plant to prove the guard refuses a present-tense claim about something absent; quoted in Pass 6's record of the exemption-smuggling probe. | nothing — it exists only inside `tools/tests/test_corpus_check.py` |
| `leak_gate.py` | **Never existed.** `tools/docgen/ENGINE_PLAN.md`'s module table named it until 2026-08-22 (`OG-89`); the name survives only where a register or a log quotes the defect. | `tools/docgen/export_sanitizer.py` |
| `hash_gate.py` | **Never existed.** Same row, same correction (`OG-89`). | `tools/docgen/validate_doc_system.py` |
| `build.py` | The bare form of `tools/docgen/build.py`, deleted 2026-08-22 (`OG-73`). Quoted by name in the register, the session record and the authoring prompt's correction note. | `python3 -m tools.docgen.cli build` |
| `secret-scan.sh` | The portfolio secret scanner, deliberately **outside** this repository at `~/.claude/scripts/secret-scan.sh` — vendoring a copy would create a second pattern set (`OG-26`). | the hooks resolve it at runtime, overridable via `ENGINE_SECRET_SCAN` |
| `tools/docgen/demo/README.html` | **Deleted 2026-08-22** (`OG-91`): a pre-rendered copy of docgen's README produced by `build.py`, the second engine deleted in `OG-73`. It carried four live instructions for that deleted command, in tracked output no Markdown guard could see. Its source has no doc-system header, so it cannot be regenerated by the canonical path. | `tools/docgen/README.md` itself; `demo/gallery.html` is the surviving rendered sample, now built by `python3 -m tools.docgen.cli build` |
| `tools/docgen/build.py` | **Deleted 2026-08-22** (`OG-73`): 223 lines, zero importers — a *second* document engine whose input convention (`<!-- classification: X -->` comments, a `###` kicker) is incompatible with the canonical path's YAML front matter, so a document authored for one could not be built by the other. Phase 3's corpus checker is what proved it unreferenced, which is why the decision belonged to this phase. Git history is the archive, as with `OG-16`. | `python3 -m tools.docgen.cli build` — and `tools/docgen/gallery.md`, its only document, was converted to the canonical convention rather than deleted with it |
| `tools/docgen/assets/_build_animations.py` | **Deleted 2026-08-20** (`OG-16`): 433 lines, zero callers; generator for output this engine deliberately does not ship. | nothing — the engine ships static figures |
| `tools/docgen/hooks/surface_channel_router.py` | **Deleted 2026-08-20**: 353 lines implementing RULEBOOK L3's *physical routing* half, with zero callers — and unwireable as written, because it treated every tracked `.json` as a rendered export and reported **104 blocking findings** against this repository. L3's declared status names only the header-validity half, which lives in `models.py` and `classification.py`, so nothing overclaims. | nothing — L3 header validity is enforced; physical routing is not implemented and no longer pretends to be |
| `tools/docgen/assets/animations/` | Generated animation output, excluded during extraction. Its generator `assets/_build_animations.py` (433 lines, zero callers) was **deleted 2026-08-20** with `OG-16`; git history is the archive. | none — the engine ships static figures |
| `.mcp.json` | **Never shipped, and it cannot be.** An MCP registration names a host project's absolute paths, so an engine that carries one is no longer domain-neutral. Two documents claimed a repo-root one existed; both were corrected 2026-08-22 (`P6-10`). `PROVENANCE.md` still names it twice, deliberately — those two lines are the RECORD of the correction, and deleting the record is how the defect returns. | `tools/visual-engine/mcp/config.example.json`, which a host copies into its own MCP config |
| `CLAUDE.md` | **Cited only inside the record of its own removal.** `PROVENANCE.md` lists it among the host-specific integration paths that `ENGINE_MANIFEST.json` used to claim and no longer does. This engine ships no `CLAUDE.md`; a host project has its own. | `docs/CHARTER.md` states what this project is; `HANDOFF.md` states how to work on it |
| `ci-cost-control.md` | **A portfolio rules file, not a project file.** Lives at `~/.claude/rules/ci-cost-control.md` on the operator's machine and governs every project here; `OG-136` cites its §9.1 and §9.3 for why a self-hosted CI gate must not be authored before the runner serves this repository's label. An engine that is domain-neutral cannot bundle its host's portfolio rules. | nothing here — the rule is external and cited by section number so it can be checked |
| `chart-colors.ts` | Source-project application file, named in the adapter inventory table that documents **what the host app already had** before the engine arrived. That table's job is to describe a foreign codebase. | nothing — it is the host's file, and the adapter reads its palette at runtime |
| `VISUALIZATION_ENGINE_MCP_INTEGRATION_SYSTEM.md` | Source-project operator directive the visual engine was built from; not bundled | `tools/visual-engine/README.md` + `ENGINE_MANIFEST.json` carry the parts that survived extraction |
| `AUDIT_HUNT_AI_VISUALIZATION_ENGINE_MCP_INTEGRATION_SYSTEM.md` | The same directive under its original branded filename. `PROVENANCE.md` names it **as a disclosed miss** — a de-branding pass left the source project's name in a citation. Kept so the miss stays visible. | as above |
| `DESIGN_SYSTEM.md` | Source-project visual law ("Atlas tokens/components"), cited by `tools/docgen/README.md`. Distinct from the `docs/design/DOC_DESIGN_SYSTEM.md` row above — two different source-project files, both unbundled. | `tools/docgen/assets/tokens.json` + `tokens.py` + `components.py` |
| `visual_spec.json` | **A KIND of file, not a path.** `ENGINE_PLAN.md` describes the renderer as turning *a* `visual_spec.json` into SVG — the noun for an input shape, the way one says *a `package.json`*. No file of that name is or should be tracked. | `tools/docgen/sample_spec.json` is a real instance of the shape; `tools/docgen/schemas/` defines it |
| `graph.json` | Runtime output of the graph skill, written to a caller-chosen path. Naming a build product is not citing a tracked file. | `skills/graph-engine/SKILL.md` documents the shape; the file appears when a user runs it |
| `deps.json` | As `graph.json` — the dependency-flow output of the same skill. | as above |
| `BRAND_MANIFEST.md` | **Cited only to say it does not exist.** `OG-04` records `RULEBOOK.md` L20 as *declared, unbundled*: the engine is domain-neutral, so a host project supplies its own brand manifest. | nothing here by design; L20 is inert until a host provides one |
| `PROBE_STAMP.md` | **A hypothetical, in a lesson about hypotheticals.** `LESSONS.md` L-15 argues a probe must live in the artifact the gate certifies, and names this file as the bad example — a scratch document a probe was wrongly put in. Creating it would defeat the lesson. | nothing — the real probes live in the documents their gates certify |
| `installed_plugins.json` | On the operator's machine under `~/.claude/`, not in any repo. `BUILD_PLAN.md` cites it as **measurement evidence** (a corpus searched for a term, 0 hits in 435KB). | nothing — it is external evidence, quoted with its measurement |
| `plugin-catalog-cache.json` | As above — part of the same measured corpus. | nothing |
| `known_marketplaces.json` | As above — part of the same measured corpus. | nothing |
| `my-pipeline.json` | **A name the reader invents.** `CONFIGURATION.md` instructs the user to create a pipeline config *of their choosing* shaped like `tools/graphify/pipeline.example.json`. A tracked file by this name would contradict the instruction. | `tools/graphify/pipeline.example.json`, the shape it tells you to copy |
| `docs/design/doc-system/authored/` | **Directory never created.** `tools/docgen/cli.py` `content-index` command expects this directory to contain authored documents, but it is not created by the engine initialization. Engine operates in degraded mode when the directory is absent (`P8-064`). | `tools/docgen/cli.py` falls back to a named error when the directory is missing; documents authored for this engine use the standard header/metadata convention and build via `python3 -m tools.docgen.cli build` |
| `docs/DOC_MASTER_CHECKLIST.md` | **Never created.** Referenced in `tools/docgen/trash-sweep.sh:3` but the file never existed in this repository. The script's policy comment cites a non-existent document (`P8-111`). | nothing — the policy is now inlined in the script itself as a comment block explaining what "delete" means at archive time |
| `.github/workflows/docgen-gate.yml` | **The `ci_cost_control` shipped-default workflow name** (`tools/docgen/ci_cost_control.py:53` `DOCGEN_GATE_WORKFLOW`), deliberately not used here. `OG-25` cites it while recording the phantom the old `ci_cost_control` fabricated when the workflow directory was empty. `CONS-06` began flagging it in Phase 7 only because `.github/workflows/` now carries a tracked file (`secret-scan.yml`), so a sibling citation is expected to resolve — before that the whole directory was untracked and the citation was unchecked (`OG-220`). | `.github/workflows/secret-scan.yml` — the actual CI workflow this repo ships, audited by `STRUCT-05` |

*Change history*

| date | change |
|------|--------|
| 2026-08-22 | `tools/docgen/build.py` declared absent after deletion (`OG-73`). Two documents still instructed authors to run it, and one of them — `AUTHORING_PROMPT.md` — is copied verbatim by authoring agents. `built-claims` was extended the same day to resolve the `python3 <path>.py` invocation form, which it had been blind to; it found three surviving instructions in `gallery.md` immediately. |
| 2026-08-20 | `tools/docgen/hooks/pre-push.sample` declared absent after deletion, and `CONS-06`'s path regex widened from `{1,5}` to `+` on the extension — the 5-character cap had made the check blind to `.sample` and `.geojson` citations, so it reported "every cited repo path resolves" while two tracked documents cited a file deleted in the same session. |
| 2026-08-20 | Registry created during the Phase 1 deep pass, when `CONS-06` was widened from 8 core documents to all 47 tracked Markdown files and surfaced 13 stale pointers. Each was traced to the source project; the actionable ones (`AUTHORING_PROMPT.md`, the READMEs, `ENGINE_PLAN.md`) were repointed at real files, and the historical records now declare their absences here. |
