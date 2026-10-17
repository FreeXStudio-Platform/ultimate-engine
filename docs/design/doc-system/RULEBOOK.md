# RULEBOOK.md — the locked laws (L1–L23)

This is the engine's law file. `tools/docgen/__init__.py` describes the package as "the machine
that obeys `docs/design/doc-system/`", and `tools/docgen/README.md` names this file's contents as
**locked L1–L23**. Every law below is stated in the form the code already enforces it, and each
carries its enforcement site so a reader can check the law against the machine rather than trusting
this file.

**This file is locked.** It is listed in `VERSION.json`'s `rulebook_files`, so its bytes are part of
the rulebook hash. Editing it without following **L9** makes the gate exit non-zero:

```bash
python3 -m tools.docgen.validate_doc_system          # the argument-free gate
python3 -m tools.docgen.cli check <document.md>      # same gate, plus that document's header checks
python3 -m tools.health                              # the gate as one check among all others
```

(`cli check` requires a document argument — it gates a document *and* the rulebook.)

## How to read the enforcement column

| Marker | Meaning |
|---|---|
| **enforced** | Code refuses, blocks, or fails closed on a violation today. The cited symbol exists. |
| **advisory** | Code consults the law and reports, but never changes a pass/fail outcome. Fail-open by contract. |
| **declared** | The law is stated and referenced by the engine, but no mechanical check exists in this package. Enforcement is review, not code. |
| **reserved** | The number is unallocated in this engine. No semantics are asserted for it. |

A law marked *declared* or *reserved* is **not** a claim that the engine checks it. Per the
doctrine, a planned thing is never written in the present tense.

---

## L1 — Precedence spine

When two laws or two gate findings apply to the same artifact, they are ordered:

> **security > source-of-truth > registries > execution-state > visual rules > automation contracts > exports > changelog**

A higher-precedence finding is never softened, reordered, or explained away by a lower one.
`adjudicate()` sorts on this spine; an unrecognised gate name sorts last and never crashes the sort.

**Status:** enforced — `tools/docgen/export_sanitizer.py` `PRECEDENCE`, `_precedence_rank()`.
**The concrete gate order is `PRECEDENCE` itself and is deliberately NOT restated here.** This
paragraph used to enumerate seven gates. The code held nine when `OG-27` was raised and holds
seventeen now, so the prose was wrong twice over — and a wrong precedence list in the law file is
worse than no list, because it is the thing a reader trusts when deciding which finding outranks
which. Read `tools/docgen/export_sanitizer.py` `PRECEDENCE`; `tools.health` `CONS-04` asserts, in
both directions, that every gate label the engine actually emits has a position in it and that no
position is dead.

What this law fixes is the ORDER OF THE CATEGORIES above, not the membership of each one. New gates
join at the category position their subject matter dictates; that is a code change under `CONS-04`,
not a rule change under L9.

## L2 — Classification tiers

Every document carries exactly one tier: `public`, `confidential`, or `secret`. A tier that cannot
be parsed degrades to `secret` — the most restrictive reading, never the most permissive.

**Status:** enforced — `tools/docgen/models.py` `Tier`; `tools/docgen/classification.py`
`_coerce_tier()` (unparseable → `Tier.SECRET`).

## L3 — Surface

A document's surface declares where it may render: `web`, `repo`, `both`, or `none`.
**Non-public tiers are always `none`.** A public document may not declare `none`, and a non-public
document may not declare anything else — both directions are checked.

**Status:** enforced — `tools/docgen/models.py` `Surface`; `tools/docgen/classification.py`
`validate_header()`, `_coerce_surface()` (unparseable → `Surface.NONE`).

## L4 — Secret material, PII, internal paths and hostnames

No literal credential, token, key, personal identifier, internal filesystem path or internal
hostname may appear in an exportable document. This is a security law and sits at the top of the L1
spine.

**Status:** enforced — `tools/docgen/export_sanitizer.py` Gate 3 (`secret_value`) and Gate 3b
(`pii_path_internal`).

## L5 — The required metadata header

Every document carries a metadata header. Its fields are the `DocHeader` contract: an `id` of the
shape `<PREFIX>-<NNN>`, a title, a `classification` (L2), a `surface` (L3), and an `export_allowed`
boolean. A missing or malformed header is a blocking finding — the document does not build.

**Status:** enforced — `tools/docgen/models.py` `DocHeader`; `tools/docgen/classification.py`
`parse_header()`, `validate_header()`. Header ↔ registry agreement is checked by
`check_manifest_drift()` against `DOC_MANIFEST.md` (see L10/L18).

## L6 — Detector-internal net

Implementation-internal specifics — thresholds, weights, confidence cutoffs, internal feature names
— must not appear in a public document. This net is deliberately paraphrase-fragile and is **not**
the sole moat; L4 and L18 are the hard boundaries.

**Status:** advisory — `tools/docgen/export_sanitizer.py` `gate_detector_internal()`, Gate 4
(`detector_internal`), lowest rank on the L1 spine. It sets `blocking=strict`, so it is non-blocking
in the default posture and becomes blocking under `--strict` (L13).

## L7 — Generated-file guard

Every generated artifact is stamped with a `generated-by` marker and the SHA-256 of all content
preceding the stamp. The stamp makes a hand-edited build artifact detectable.

**Status:** enforced — `tools/docgen/generator.py` `_stamp_generated()` and `_content_sha256()`;
the emitted marker is `<!-- generated-by docgen · content-sha256:… -->`, hashing everything before
the stamp.

## L8 — Every numeric datum is sourced

A number that appears in a figure must resolve to a declared source. An unsourced number is treated
as unverified. Read together with **L16**, which is the same law applied at the render gate.

**Status:** enforced — `tools/docgen/geo_map.py`: `GeoPoint.value` is documented as "if set, MUST be
sourced (L16)", and `check_geo_map_collisions()` emits the blocking `geomap.source` finding for any
value with no `DataSource`.

## L9 — Locked-rule change protocol

> **Any change to a locked rule MUST bump `VERSION.json`, append a `CHG-700` changelog entry, and
> record an ADR.**

The mechanical half is the rulebook hash-gate: the files listed in `VERSION.json`'s `rulebook_files`
are read in listed order, their **raw bytes concatenated**, and SHA-256'd. The digest is compared to
`rulebook_sha256`. A mismatch means a locked rule changed without a recorded version bump, and is a
**blocking** finding.

Fail-closed throughout. A missing or malformed `VERSION.json`, an absent or malformed
`rulebook_files` list, or **any** listed file missing from disk each produce a blocking finding —
never a silent pass.

**First run / re-baseline.** When `rulebook_sha256` begins with the sentinel `PENDING` (matched after
strip and upper-case), the computed hash is accepted and, with `--write-hash`, written back. **This
is the only path on which the gate mutates its own input.**

Re-baselining therefore takes **two steps, in this order**:

```bash
# 1. authorise the write by resetting the sentinel
#    (edit docs/design/doc-system/VERSION.json: "rulebook_sha256": "PENDING")
# 2. compute and record
python3 -m tools.docgen.validate_doc_system --write-hash
```

`--write-hash` on a **live mismatch does nothing** — it is not a way to silence drift, and the gate
stays red until the sentinel is set deliberately. Verified by execution 2026-08-20.

The `CHG-700` and ADR halves are a human process, checked by review. The gate does not verify them
and does not claim to.

**`VERSION.json` keys.** `rulebook_files` and `rulebook_sha256` are read by the gate. `version` and
`gate` are **declarative metadata** — `gate` names the module that owns the hash-gate, per
`ENGINE_PLAN.md` §4b, and **no code reads `gate`**. *(Corrected 2026-08-22, `OG-91`: this said no code reads EITHER key. `tools/health/checks.py` reads `version` as `CONS-08`'s ground truth for every rulebook-version claim in the handover documents — so the one key described as inert is the one a check depends on.)* They are recorded so a reader can find the
enforcing module from the data file; they are not inputs.

**Status:** enforced — `tools/docgen/validate_doc_system.py` `check()`, `compute_hash()`,
`_load_version_json()`, `_resolve_rulebook_files()`. Reached from
`tools/docgen/cli.py` `_cmd_check()` and from
`python3 -m tools.docgen.validate_doc_system`.

## L10 — Change impact (blast radius)

A change of a known type resolves to the set of dependent doc-type prefixes that must be reviewed,
plus the public-sanitisation rule that applies. The recognised change types are
`DETECTOR_CHANGE`, `VISUAL_STYLE_CHANGE`, `USER_POLICY_CHANGE`, `ARCHITECTURE_CHANGE`, and
`RULE_CHANGE`, and they are read from `update_impact_map.json` — not hardcoded.

An unrecognised change type yields a non-blocking advisory naming the gap, so an unmapped type is
visible rather than silently empty.

**Status:** advisory (fail-open by contract) — `tools/docgen/adjudication.py` `load_impact_map()`,
`compute_change_impact()`. Reached via `validate_doc_system.consult_governance()` and
`python3 -m tools.docgen.validate_doc_system --change-type <TYPE>`.

## L11 — Contradiction tie-breakers

Recurring conflicts between laws are resolved once, in `CONTRADICTION.md`, and that recorded
resolution is attached to any blocking finding whose gate belongs to the conflict class — so an
operator reads how the rulebook already resolved the conflict instead of re-deriving it.

Consultation is **purely additive**: every attached finding is `INFO` and non-blocking, no existing
finding is dropped, reordered or unblocked, and `GateResult.ok` is unchanged. A missing or malformed
matrix degrades to an empty consultation with a logged warning — it is never faked into a false
"consulted OK".

**Status:** advisory (fail-open by contract) — `tools/docgen/adjudication.py`
`load_contradictions()`, `annotate_with_contradictions()`, `_GATE_TO_CONTRADICTION_TOKENS`.

## L12 — Path isolation

An input path is canonicalised before use and must resolve **inside** the repository root. A path
that escapes the root — via `..`, a symlink, or an absolute path — is refused.

**Status:** enforced, fail-closed — `tools/docgen/generator.py` `build()` (canonicalise, then assert
containment).

## L13 — Strict mode

`--strict` promotes advisory findings to blocking. It is one flag that tightens every gate that can
be tightened. Gates whose findings are already unconditionally blocking — the L9 hash-gate among
them — are unaffected, and accept the flag only for a consistent CLI story.

**Status:** enforced — `tools/docgen/cli.py`; `export_sanitizer.run_gates(..., strict=...)`;
`validate_doc_system.check(..., strict=...)`.

## L14 — Export

**Only a `public` document may be committed or exported.** `export_allowed` may be true only on a
public document; any other combination is a blocking finding.

**Status:** enforced — `tools/docgen/models.py` `Tier` docstring; `tools/docgen/classification.py`
`validate_header()` (tier ↔ `export_allowed` agreement); `tools/docgen/export_sanitizer.py` Gate 1
(`tier`).

## L15 — Design tokens and fonts

Visual output derives from the declared design tokens and vendored fonts. Colours are not invented
at the call site; fonts are embedded so output stays self-contained and offline.

**Status:** enforced — `tools/docgen/tokens.py` (tokens → CSS), `tools/docgen/fonts.py`
(vendored faces → self-contained `@font-face`). The visual engine's own suite asserts themes derive
from these tokens rather than from invented colours.

## L16 — Sourced numbers at the render gate

A number with no resolvable `DataSource` **fails the render**. This is L8 stated at the point of
enforcement: the figure does not render rather than rendering an unattributed number.

**Status:** enforced in two postures, and the split is stated because it is real (`OG-196`, 2026-08-24).

**Blocking, fail-closed, no guessing:** a figure kind that declares a data series must name a resolvable `DataSource` — a non-empty `ref` or `url`. `tools/docgen/generator.py` `check_figure_provenance()` (gate `figure_provenance`) enforces this over every kind declared data-carrying in its dispatch table, and `tools/docgen/geo_map.py` `check_geo_map_collisions()` (gate `geomap.source`) and `check_choropleth_collisions()` (gate `choropleth.source`) enforce it per point, the latter also failing the render on an unmatched country name rather than silently omitting it. This is a structural check: the question *did you declare a source* has an exact answer.

**Advisory, heuristic, explicitly not the moat:** a number written into a figure's free TEXT — a node label, a caption, a note — is detected by a quantity heuristic and reported non-blocking, promoted to blocking by `--strict`. It is advisory for the reason Gate 4 states for itself: a semantic net over prose is paraphrase-fragile. **A blocking version was built first and refuted** — it missed the very example that justified it once re-punctuated, and it refused a build on a patent number, which teaches authors to route around the gate. What it does not detect is written down in `OG-196` rather than implied away — bare measurements, unit-suffixed figures, scientific notation, a scale word between an amount and its currency code, and numeric series inside raw `mermaid` source — and a retained probe asserts that residual, so it cannot drift silently in either direction.

> **Citation corrected twice, 2026-08-20.** L8 and L16 originally cited `tools/docgen/visual.py`,
> which contains **zero** `DataSource` occurrences — the gate has always lived in `geo_map.py`. The
> first correction then invented `check_choropleth_rules()`, which also does not exist; the real
> symbol is `check_choropleth_collisions()`. Both were caught by the Phase 1 deep verification pass,
> the second only after `CONS-07` was extended to scan a whole `Status:` block rather than its first
> line. **Fixing a false citation with another false citation is exactly why the guard is mechanical
> and not a promise to be careful.**

## L17 — Reserved

**Status:** reserved — no enforcement site; **zero code references**. The only occurrences of `L17`
in this tree are governance notes (this entry and the records that describe it as unallocated). No
semantics are asserted for it.

## L18 — Variant registry and the cross-tier moat

A document type's permitted tiers (`variants`) are declared once, per type, in `DOC_MANIFEST.md`.
Content belonging to one variant must never appear in another — the cross-tier leak is the moat this
law exists to hold.

**Status:** enforced — `tools/docgen/export_sanitizer.py` Gate 9 (`variant_overlap`);
`tools/docgen/doc_manifest.py` (registry reader). The manifest's commercial-facing word
`commercial` maps to `Tier.PUBLIC` via `_VARIANT_WORD_TO_TIER`.

> **Scope, stated precisely 2026-08-22 (`OG-93`).** The gate runs on **every** export — `run_gates`
> reaches it through `_variant_overlap_against` — and it is **fail-closed**: a document declaring
> `variants` whose sibling text is not supplied is BLOCKED, never treated as "no overlap". What it
> cannot do is compare against a sibling nobody hands it, and `generator.build` does not supply
> siblings, so in this repository — where no governed document declares `variants` — the gate
> correctly has nothing to compare. That is a true no-op, not a broken gate, and it is written down
> here rather than left for a future reader to rediscover. All four behaviours are now retained
> counter-examples in `tools/tests/test_fail_closed.py`.

## L19 — Storyboard authorship roles

A video-script storyboard separates authorship: the architect writes the topic and outline, the
builder writes the scene detail. The exporter emits a storyboard structure; it does not generate
video.

**Status:** declared, with a structural exporter — `tools/docgen/video_script.py`,
`tools/docgen/models.py` (storyboard model). No gate enforces the authorship split.

## L20 — Brand manifest

Ownership and mark usage (©, ™, the mark itself, and the design-token pointer) are declared in a
vendored in-repo `BRAND_MANIFEST.md`.

**Status:** declared — referenced by `tools/docgen/ENGINE_PLAN.md` §4b. **No `BRAND_MANIFEST.md` is
bundled with this engine** and no code reads one. A host project that needs L20 supplies it.

## L21 — Design system

Rendered components follow the declared design system: shared partials, one token source, and
consistent typography. Components are not restyled ad hoc at the call site.

**Status:** enforced for the bundled components — `tools/docgen/components.py`,
`tools/docgen/tokens.py`, `tools/docgen/fonts.py`. WCAG-AA text legibility is checked by Gate 10
(`wcag_contrast`).

## L22 — Reserved

**Status:** reserved — no enforcement site; **zero code references**. As with L17, the only
occurrences are governance notes recording it as unallocated. No semantics are asserted for it.

## L23 — In-repo artifacts

Every **asset** the engine renders from is in-repo and vendored: fonts, design tokens, map geometry,
the graph library, and the golden baselines. Rendering is **offline** — a build fetches nothing, and
output is self-contained. Optional external renderers may be used only where their absence degrades
gracefully.

**What this law does NOT claim.** The engine is not dependency-free. The Python side requires
`PyYAML`; `tools/visual-engine` requires `echarts`, `@resvg/resvg-js`, `zod` and the MCP SDK;
`tools/mermaid-engine` requires `beautiful-mermaid`. These are **pinned and reinstallable, not
vendored** — `node_modules/` is deliberately gitignored (native bindings are platform-specific), so
a fresh clone runs `npm install` before the JS suites can run.

**Status:** enforced for assets, by construction and asserted by the suites — the visual engine's
simulations prove a direct adapter that works with no server process, self-contained HTML with a
static fallback, and embedded fonts. `ENGINE_PLAN.md` §4b records that L23 was amended to **in-repo**
artifacts.

> **Wording corrected 2026-08-20.** This entry previously claimed "no dependency outside the tree",
> which the repository's own `package.json` files and `.gitignore` contradict. The true, checkable
> claim is *offline rendering from vendored assets*, not *zero dependencies*.

---

## Locked-file set

The files whose bytes form the rulebook hash are listed in `VERSION.json`'s `rulebook_files`, in
that order. The set is the governance data layer that exists in this engine:

| # | File | Why it is locked |
|---|---|---|
| 1 | `RULEBOOK.md` | The laws themselves |
| 2 | `TAXONOMY.md` | The doc-type prefix registry (L2/L5) |
| 3 | `CONTRADICTION.md` | The L11 tie-breaker matrix |
| 4 | `update_impact_map.json` | The L10 blast-radius map |
| 5 | `DOC_MANIFEST.md` | The variant registry (L18) |
| 6 | `DOC_WRITING_DOCTRINE.md` | The method law — how documents get written and verified |
| 7 | `DEEP_VERIFICATION_PASS.md` | The process law — how a phase ends, and the separation-of-duties rule |
| 8 | `tools/hooks/install.sh` | The moat's installer — it *generates* the chain script, so an edit here can switch a project's pre-existing hook off without touching either hook (measured: `OG-67`) |
| 9 | `tools/hooks/pre-push` | The push-time moat's own executable (OG-29) |
| 10 | `tools/hooks/pre-commit` | The commit-time moat itself (OG-29) |

**Laws are locked; ledgers are not.** Entries 6 and 7 live outside `docs/design/doc-system/` but are
*law files*: they state binding procedure, so a silent edit to either is exactly the drift L9 exists
to catch. Entries 8 and 9 are not documents at all — they are the git moat's own executables, locked
on 2026-08-20 after an independent pass reduced both to `exit 0` stubs and health still reported them
*"installed, current, and still gating"*. `STRUCT-03`/`STRUCT-04` assert the installed hook is
byte-identical to its source, so locking the source is what turns neutering the moat into a declared,
recorded act. It is the only structural defence `pre-push` has against a subtle weakening:
`pre-commit` is additionally probed behaviourally on every health run, but `pre-push` cannot be,
because it runs health itself and the probe would recurse. Deliberately **not** locked are the files that change every session by design —
`CHANGELOG.md`, `OPEN_GATES.md`, `LESSONS.md`, `HANDOFF.md`, `NEXT_SESSION.md`. Locking a ledger
would force a re-baseline every time a lesson is recorded, which trains people to bypass the gate.
Those are guarded instead by `tools/health` `STRUCT-01`, which fails if any of them disappears.

`ENGINE_PLAN.md` §4b also named `CLASSIFICATION.md`, `DESIGN_SYSTEM.md`, `BRAND_MANIFEST.md` and a
`calibration/` directory as locked. **None of those exist in this engine**, and the hash-gate fails
closed on a listed file that is missing — so they are deliberately absent from `rulebook_files`. A
host project that adds them adds them to the list and re-baselines under L9.

**Replacing `DOC_MANIFEST.md`** — which the bundled file explicitly invites a host project to do —
changes the rulebook hash and will correctly trip the L9 gate. Re-baseline with the two-step
procedure above plus a `version` bump. That is the protocol working, not a false positive.

*Change history*

| date | change |
|------|--------|
| 2026-08-19 | Rulebook restored from enforcement sites (Phase 1). Semantics read from code, not reconstructed from memory. L17/L22 recorded as reserved; L20 recorded as declared-without-artifact. |
