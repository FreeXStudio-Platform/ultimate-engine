# CONTRADICTION.md — the L11 tie-breaker matrix

Recurring conflicts between laws, resolved **once**, here. When a gate blocks and its concern class
appears below, the recorded resolution is attached to the finding as an advisory note, so an
operator reads how the rulebook already settled the conflict instead of re-deriving it under
pressure.

**This consultation never changes an outcome.** Every attached finding is `INFO` and non-blocking;
no existing finding is dropped, reordered, or unblocked. A missing or malformed matrix degrades to
an empty consultation with a logged warning — never to a faked pass. The hard moat is the leak-gate,
not this file.

**This file is locked** — it is listed in `VERSION.json`'s `rulebook_files`.

## How a row is matched to a finding

The `Rule(s)` cell is tokenised for `L<n>` rule ids and `Gate <n>` names. A fired gate matches a row
when the row cites **any** token mapped to that gate. Rows that cite no recognised token are
documentation only — they parse, and they never fire. The mapping is
`adjudication._GATE_TO_CONTRADICTION_TOKENS`; keep the `Rule(s)` cells below in step with it, or a
row silently stops firing.

| # | Conflict | Resolution | Rule(s) |
|---|----------|------------|---------|
| 1 | A document is more useful to its audience at a wider tier than its classification allows. | Security wins over reach. The tier boundary is never widened to improve an audience fit; publish a separate public document instead of relaxing the original's tier. | L1, L14, Gate 1 |
| 2 | A worked example is only reproducible if it contains real credential material. | Security wins over reproducibility. Use an obviously-fake placeholder of the same shape and state that it is fake. A reproducible example is never worth a live secret. | L4, Gate 3 |
| 3 | A debugging or support document is clearest when it names the real internal host or path. | Security wins over diagnostic convenience. Refer to the role, not the address. Operators resolve roles from the environment; readers outside it must not be able to. | Gate 3b |
| 4 | Shared prose duplicated across tier variants drifts; deduplicating it means one body serving several tiers. | The moat wins over DRY. Cross-tier reuse is the leak this law exists to prevent. Duplicate the prose and let the variants drift rather than sharing one body across a tier boundary. | L18, Gate 9 |
| 5 | A document's header and its registry row disagree about the type's permitted tiers. | The registry wins. The header is the claim; the registry is the record. Fix the header, or change the registry deliberately and re-baseline — never let a build pass on the header's word alone. | L5 |
| 6 | Explaining *why* a result occurred reads best with the internal threshold or weight that produced it. | Restraint wins, but this net is advisory and paraphrase-fragile — it is not the boundary. Describe the behaviour and its direction without the internal constant. Treat a hit here as a prompt to re-read, not as proof of a leak. | L6 |
| 7 | A locked rule is wrong and the fix is urgent; the change protocol is slower than the fix. | The protocol wins. Bump the version, record the changelog entry, and write the decision record. Urgency is exactly when an undeclared rule edit does the most damage, because nobody is reading carefully. | L9 |
| 8 | A number is central to the argument but its source cannot be produced right now. | The source requirement wins. Cut the number or mark the claim unverified. An unsourced number that survives review becomes a fact by repetition. | L16 |
| 9 | A more expressive visual reads better but drops text contrast below the legibility floor. | Legibility wins. Expressiveness is bounded by the contrast floor; restyle within it rather than granting an exception. | L21 |

### Which rows can actually fire, measured

Consultation only annotates **blocking** findings (`adjudication.annotate_with_contradictions`
skips non-blocking ones), so a row's reach depends on whether its gate blocks:

| rows | gate | fires |
|---|---|---|
| 1–5, 7 | `tier`, `secret_value`, `pii_path_internal`, `variant_overlap`, `manifest_drift`, `header`, `hash_gate`, `identity` | Always — these gates block by default. `identity` joined 2026-08-24 (`OG-195`): it had no precedence position and no mapping at all, because it is written as `gate=GATE` against a module constant and every scan looked for a string literal. Row 5 fits it exactly one layer over — the header claims `revision: 0`, the archive holds the bytes, and the record wins. |
| 6 | `detector_internal` | **Only under `--strict`.** Gate 4 sets `blocking=strict`, so in the default posture it is advisory and no tie-breaker is attached. |
| 9 | `wcag_contrast`, the `*.collision` figure gates, and `chart.rule`, `iso3d.rule`, `layered.rule` | Whenever Gate 10 blocks, and whenever a figure's labels overlap or fall below a minimum gap. `wcag_contrast` was mapped 2026-08-20; the collision gates joined 2026-08-24 (`OG-191`), when a widened scan revealed that sixteen dotted gate labels had never been visible to the coverage check at all. **Stated imprecision:** this row's text names the *contrast* floor, and a collision is a legibility failure of a different kind — the resolution (*legibility wins; expressiveness is bounded*) is the right advice, the wording is narrower than the attachment. Recorded here rather than left for a reader to notice, exactly as the rows 2/6 `L4` overlap is below. **The three `*.rule` gates joined 2026-08-24** (`OG-195`), when a verifier read their messages: each also emits a legibility CAP — a 6-slice cap, a 24-box cap, a 4-layer cap — which is this row's tie and not malformed input, so exempting them contradicted the reasoning applied to their `.collision` siblings. A gate maps as a whole, so their malformed-spec messages receive this advisory too; that over-attachment is the same kind as the one above. |
| 8 | `figure_provenance`, `geomap.source`, `choropleth.source` | Whenever any L16 provenance gate blocks. **Mapped 2026-08-24 (`OG-63`)** — it previously read *"Never — `L16` carries no gate-token mapping"*, which was accurate and was also the record of a rule with no enforcement: every data-carrying figure kind except `geo_map` and `choropleth` accepted numbers with no source at all. The gate now covers every such kind, so the row it resolves is reachable. |

One deliberate imprecision: rows 2 and 6 both cite `L4`, and `detector_internal` maps to both `l4`
and `l6`, so a blocking detector finding attaches **two** advisories. Both are on-topic (they are
the same security concern class) and advisories are non-blocking, so the duplication is noise rather
than a defect — but it is stated here rather than left for a reader to discover.

*Change history*

| date | change |
|------|--------|
| 2026-08-19 | Matrix created (Phase 1). Rule(s) cells written against the live gate-token map so consultation is active, not merely parseable. |
