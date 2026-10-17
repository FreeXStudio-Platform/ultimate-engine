<!-- title: SESSION STATE -->
<!-- session-state: WORK-COMPLETE-VERIFICATION-PENDING @ fe55da5 on 2026-10-17 via public-readiness-1.1.2 -->
<!-- afa8691 is the commit the WORK landed in (licence, policies, templates, CI, README, scrubs, two defect fixes, version). `python3 -m tools.health --full` read 38 passed, 0 failed, 0 skipped
     on the engine at the previous work commit and on a clean snapshot of it; the pre-push health gate and the GitHub `health` job read green on the commits after. This record lands
     one commit later (`OG-150`). No independent pass has adjudicated this work, so nothing above WORK-COMPLETE-VERIFICATION-PENDING may be claimed. -->
# Session State — the crash-recovery record

**Status:** PROCESS — **rewritten in place, never appended. One session, one state.**

> **Session of 2026-10-16 (evening) — the repository was audited for publication and made ready to be public.**
> Project `1.1.2` (`PROJECT_VERSION`), rulebook `1.2.17` (unchanged — no hash-locked file was touched), no phase-blocking register row.
>
> **What the audit found.** Settings were sound: a branch ruleset requiring a pull request and the `secret-scan` check with no bypass, read-only
> workflow token, no secrets, keys or webhooks, no open dependency alerts. gitleaks over all 188 commits: no findings. The gaps (`OG-310`): no licence
> (and one package declared `UNLICENSED`), no contribution, conduct or security policy, no issue or pull-request templates, no dependency-update or
> pull-request CI, a README written for a private audience, and the operating-system username inside absolute paths in two documents.
>
> **What was done.** Apache-2.0 `LICENSE` and `NOTICE`; the policy and template files; `ci.yml` (additive); a README that says what the engine is and how to
> start; the manifests declare Apache-2.0 with both attestations re-derived; the username and workspace paths replaced by placeholders, which leaves
> `PROVENANCE.md`'s stamp declared NEEDS RE-HARDENING in `HANDOFF.md`.
>
> **What cannot be fixed in place.** Seven commits carry a personal address in their metadata. History cannot drop it without a rewrite, so the public
> repository is created from a snapshot of this tree; this repository stays the private archive.
>
> **Not claimed:** no independent pass has adjudicated this work (implementer-verified, the residue `OG-209` records).
>
> **Next:** `docs/plan/START_NEXT_SESSION.md` — the first item is `OG-262`.


> ## ⛔ IF YOU ARE A FRESH SESSION READING THIS AFTER A CRASH — START HERE
>
> **Nothing below needs redoing.** Everything marked `DONE` is committed at the stamped commit and
> pushed. Re-running it wastes a session and risks reverting a fix.
>
> 1. Confirm the stamp is still valid: `git rev-parse --short HEAD` should be the stamped commit
>    **or a descendant**. If HEAD is *behind* it, someone reset — stop and ask.
>    (`tools.health` `STRUCT-06` checks this for you and fails loudly if it does not hold.)
> 2. Confirm the floor: `python3 -m tools.health --full` → **38 passed, 0 failed, 0 skipped**.
> 3. Read `## What is NOT done` at the bottom. That, and only that, is the remaining work.
>
> This file holds **one** state, rewritten in place (`OG-211`). Per-session history belongs in
> `CHANGELOG.md` and `docs/process/VERIFICATION_LOG.md`, both of which have it in full.

---

## The stamp — what it is and how to read it

The HTML comment on line 2 of this file is machine-greppable and carries four fields:

```
<!-- session-state: <STATE> @ <commit> on <YYYY-MM-DD> via <pass-name> -->
```

| `<STATE>` | meaning |
|---|---|
| `NEEDS-RE-STAMP` | The stamp's commit no longer covers this file's body — content landed after it. The checklist may still be accurate; what is NOT true is that anything verified it at the stamped commit. Cleared by the next closeout that re-verifies and re-stamps. |
| `IN-PROGRESS` | A session is actively writing. The tree may be inconsistent. **Do not trust the checklist.** |
| `WORK-COMPLETE-VERIFICATION-PENDING` | All planned work is committed and pushed; independent verification has been **dispatched and has not returned**, or is the declared work of a named later phase. The checklist is trustworthy; the *quality* claim is not yet. **This is the current state.** |
| `VERIFIED` | Work complete **and** an independent pass returned without breaking a claim. |
| `VERIFIED-WITH-OPEN-GATES` | As `VERIFIED`, but named rows remain open in `docs/process/OPEN_GATES.md`. **This is the normal resting state of this project** — it is honest, not a failure. |

**The commit in the stamp is the commit the WORK landed in — not necessarily the commit this file
landed in.** This record is written after the work it describes, so it normally lands one commit
later, and that is expected. What the stamp asserts is: *at the named commit, the checklist below
was true.*

**It goes stale when the tree moves past it without this file being rewritten.** So:

- `HEAD` **is** the stamped commit, or a descendant that only added this record → stamp valid.
- `HEAD` is a descendant carrying *other* work → **the stamp is stale.** Re-derive the checklist from
  `git log` and `CHANGELOG.md` before believing it, then rewrite this file.
- `HEAD` is *behind* the stamped commit → someone reset. **Stop and ask** before doing anything.

`tools.health` `STRUCT-06` enforces the mechanical half — that a stamp exists, parses, names a real
commit, and uses a state from the table above. It cannot judge whether the checklist is *honest*;
only a reader can — which is why `CONS-08` also reads this file's stated project version, rulebook
version and health floor against their machine-readable sources.

---

## Definition of done — the bar in this project

A checklist item may be marked `DONE` only when **all four** hold. Anything less is `PARTIAL` or
`NOT DONE`, written as such.

1. **It runs.** There is a command, and its real output was read — not inferred from source.
2. **It was shown red first.** For a gate or a guard: the defect was reproduced *before* the fix, in
   the artifact the gate actually certifies, and the fix was then re-falsified.
3. **It is written down** in `CHANGELOG.md` with date, file and evidence — not only here.
4. **It survives the session.** Committed. `git status` clean, `git status --branch` in sync.

**"Done" never means "I believe it works".** Every `DONE` below names where its proof lives.

---

## Checklist — this session's work (public readiness)

| # | item | state | proof |
|---|---|---|---|
| P1 | Settings, rulesets, security features and community profile read | **DONE** | repository API: ruleset `moat-server-side` active, no bypass actors; 0 secrets, hooks, deploy keys; 0 open dependency alerts; community profile 28% before this work |
| P2 | Full history and current files scanned for secrets and personal data | **DONE** | gitleaks over all refs: no leaks (188 commits); current files: no e-mail addresses, IP addresses or tokens; the OS username in two documents (fixed); one personal address in 7 commits' metadata (not fixable in place) |
| P3 | Licence, policies, templates, CI, dependency updates added | **DONE** | `LICENSE` (Apache-2.0, 11358 bytes, the canonical text), `NOTICE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CITATION.cff`, `.github/` forms, template, `CODEOWNERS`, `dependabot.yml`, `ci.yml` |
| P4 | Gates green | **DONE** | `python3 -m tools.health --full` → 38 passed, 0 failed, 0 skipped (engine, then a rehearsal clean snapshot of it); the pre-push health gate green on every push; the GitHub `ci.yml` `health` job green on a Linux runner after `OG-311` and the fixture fix; `corpus_check` clean; `blueprint verify` clean |
| P5 | Landed through a pull request with a merge commit, and tagged | **PENDING, by design** | This record lands IN that pull request. After the merge: `git log --merges -1` and `git tag -l v1.1.2` |
| P6 | Clean public repository created, set up and checked | **PARTIAL** | The empty PRIVATE repository `FreeXStudio-Platform/ultimate-engine` exists and is configured (description, website, 18 topics, discussions, secret scanning with push protection, dependency alerts and updates, read-only workflow token). A rehearsal snapshot (two commits, author `FreeXStudio`) passed `python3 -m tools.health --full` 38 of 38. Not done: pushing the snapshot (after this PR is merged and tagged `v1.1.2`), the branch ruleset, code scanning, and publishing — which waits for the owner's explicit go |

---

## Open loop — what is outstanding, and where

**In this repository: nothing blocking.** `docs/process/OPEN_GATES.md` carries zero blocking rows. **Outside it:** pushing the clean snapshot into the (private) organization repository and publishing it — only on the operator's explicit go; `PROVENANCE.md` needs a re-hardening pass (three-pass, pass 3).

---

## What is NOT done — read this before starting anything

**`docs/process/OPEN_GATES.md` is the authority. This is a pointer, not a second copy.**

- **`OG-262` — the nine native chart kinds do not carry the per-mark contract.** A feature, not a repair; the design is written
  (`FIGURE_SYSTEM.md` §2–§4). It is the first item of `docs/plan/START_NEXT_SESSION.md`.
- **Not verified:** Firefox, Safari, a screen reader, and any independent adjudication. One test skips by design: the host-documents test unless
  `ENGINE_TEST_HOST_ROOT` is set (`OG-305`); the three real-browser tests skip where Playwright is absent. `ci.yml` has not yet run on GitHub.
- **The inherited field-trial programme is unchanged** — round 2 is decided and not yet designed; do not re-review round 1.
- **Known and deliberately kept:** `python3 -m tools.health --full` takes many minutes and the pre-push hook runs it; a TIMEOUT under load is a
  verdict to repeat, never a pass (`OG-212`). Run it with a `python3` that has PyYAML first on `PATH`.

A row closes in exactly one of three ways: **fixed with a red-first falsification recorded**, **demoted to `NOT_A_DEFECT` with reasoning a future
verifier can attack**, or **scheduled to a phase whose plan row names that work** (unavailable now — there is no next phase). Nothing else counts.
