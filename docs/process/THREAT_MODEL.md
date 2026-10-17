---
id: SYS-1
classification: public
title: Threat model — what the git moat defends against, and what it does not
surface: repo
audience: technical
owner: doc-system
status: active
export_allowed: true
last_reviewed: 2026-08-30
verified_state: verified
---
<!-- artifact-hardened: Verified @ fe55da5 on 2026-08-30 via three-pass-v1 -->

# Threat model — what the git moat defends against, and what it does not

**Status:** PROCESS — normative for `tools/hooks/*`. Written 2026-08-21. **Brought under governance
and stamped `verified` at the Phase-7 close (2026-08-30).** The moat's three modules
(`tools.docgen.hooks` and its two children) measure at rung 5 (`detail`) — the ladder's top rung,
reached because this document, which owns that container, is governed and claims a verified state —
and the body-certifying stamp it now carries lifts them to `verified` in `blueprint/COMPLETENESS.md`:
the project's first non-zero `verified` count, and a consequence of the moat having been
independently re-attacked (Pass 9, which found and closed two real breaches — `OG-213`, `OG-214`),
not a number that was aimed at. The `moat` container's `depthFloor` is raised 4 → 5 to keep that
earned depth (`CONS-12`).

**Why this file exists.** The moat's claim was wrong before its implementation was. It was described
in `HANDOFF.md`, in `CHANGELOG.md` and in its own headers as though it made leaking *impossible*.
Eight independent adversarial verifiers broke that claim twelve ways in a single pass. Some of those
holes were real accidents waiting to happen and are now closed. Others could only be reached by
deliberately editing the hook that was supposed to stop you — and **no client-side hook can survive
that, ever.** Continuing to harden against it is an arms race with no end state, which is why the
scope is now written down instead of implied.

---

## What this moat IS

> **A guard against ACCIDENTAL publication of secrets and misplaced classified documents, by a
> developer who is cooperating with it.**

That is a genuinely useful thing and it is achievable. It is what the moat now does, and every
defence below has been falsified red before being trusted.

## What this moat is NOT

> **It is not a security boundary, and it never can be.**

`git commit --no-verify` and `git push --no-verify` disable every hook with exit 0, no output, and
no artifact for an audit to inspect. Nothing client-side can prevent that. Anyone who can edit
`.git/hooks/` can also delete it. **A local hook constrains accidents, not adversaries.**

Real enforcement requires a **server-side required check**, and Phase 7 delivered one (`OG-31`,
closed 2026-08-30): a branch ruleset on the default branch requires a pull request and a
GitHub-hosted `secret-scan` check before anything merges, so a `git push --no-verify` to `master` is
refused by the server, and a secret inside a pull request cannot be merged.

**The bound this does NOT remove, stated because a stamp certifies this body.** This repository is
private with no GitHub Advanced Security, so there is no *push-time content scan* server-side. A
secret force-pushed to a throwaway **feature branch** still reaches `origin` until its pull request is
flagged; what closed is the **merge path to the protected branch**. That is the honest ceiling of a
server-side moat on a no-GHAS private repo, and it is the same shape as everything else on this page:
named rather than pretended away.

**A second bound, on the push-time filename check (`OG-214` residual).** The pre-push placement gate
scans the NAME of every blob that is NEW to the pushed range, so a classified document pushed under a
misleading name is caught. It does not re-scan the name of a blob already on the remote: a `git mv` of
an already-published file introduces the new name only in the commit's tree object, not as a new
blob, so that rename alone is invisible to the push-time filename check. The **commit-time** gate sees
it for an ordinary `git mv && commit` — the renamed path is in the index — but not for a commit that
skips pre-commit: a rename inherited from a **merge**, a **cherry-pick**, or a **peer's fetched
branch** creates the new name without pre-commit ever running (the same accidental class the *content*
scan already handles at push time), and `--no-verify` skips it deliberately. The push-time filename
check catches none of these, because it lists only NEW-blob names. What still holds the line for the
protected branch is the server-side ruleset (`OG-31`), which refuses any push to `master` that did not
go through a pull request. Low harm regardless: a filename, not content, and the blob's content was
scanned when it was first published. Widening the push-time check to diff names against the remote
(`git diff --name-only <remote>..<local>`) would need a second re-baseline of the hash-locked hook for
a bounded, low-harm gap, so it is recorded here rather than built (`OG-214`).

---

## In scope — accidental vectors, all closed and falsified

Each was proven exploitable by an independent verifier on commit `c9f61be`, then fixed, then
re-attacked. All twelve cases in `tools/hooks/` are re-run by the harness described in
`CHANGELOG.md` `[0.3.2]`.

| vector | why it is an ACCIDENT, not an attack |
|---|---|
| A secret added in one commit and removed or redacted in a later one, pushed together | The single most common way a key reaches a remote: you commit it, notice, fix it, push the pair. |
| A secret staged with `git add`, then redacted in the working tree | Ordinary "oh no" reflex — fix the file, forget the index. |
| `.gitattributes` with `export-ignore`, or a smudge filter | Both are legitimate packaging configurations. They silently removed files from, or rewrote files inside, what the gate scanned. |
| `working-tree-encoding=UTF-16` | A legitimate configuration for a repository with UTF-16 sources. |
| Two paths differing only in case | Arrives routinely from case-sensitive Linux and CI collaborators; collides on macOS APFS. |
| Commits inherited from a **peer** remote (`fetch` a colleague's branch, add a commit, push) | A completely ordinary collaboration workflow. |
| An unresolvable remote sha (force-push race, shallow clone, rewritten remote) | The hook's own comment calls this routine. |
| A file named `secret-scan.sh` anywhere in the tree | **Portfolio rule S2 explicitly instructs projects to vendor the scanner**, so this is not hypothetical — it is instructed. |
| A key pasted into a **commit message** | Extremely common; `git-secrets` and `gitleaks` both scan messages for this reason. |
| A staged **symlink** whose target string is the credential | Not a regular file, so a directory walk skipped it. |
| A broken or non-Python `.venv/bin/python` | A half-built virtualenv is an accident; the hooks preferred it and every Python gate silently no-opped. |
| `rulebook_sha256` left at `PENDING` | The sanctioned two-step re-baseline **has a window where the rule set is unlocked**, and forgetting step two left it unlocked with no visible signal. |
| An empty `confidentialDir` in `engine.config.json` | A one-character config error disabled the L14 placement gate entirely. |

## Out of scope — by design, and named rather than pretended away

| vector | why no client-side hook can address it |
|---|---|
| `git commit --no-verify` / `git push --no-verify` | Git disables the hook before it runs — no client-side hook can defend against it. **Closed server-side for the protected branch (`OG-31`, 2026-08-30):** a branch ruleset refuses a `--no-verify` push to `master`, and the required `secret-scan` check refuses a secret in a pull request. A feature-branch push on this no-GHAS private repo is the residual (see above). |
| Editing or deleting the installed hook | Whoever can install a hook can uninstall it. Mitigated, not solved: the hook sources are hash-locked into `rulebook_files`, `STRUCT-03`/`STRUCT-04` assert the installed copy is byte-identical to its source, `STRUCT-04` probes pre-commit behaviourally, and each hook asserts its own gate count so deleting a gate takes two coordinated edits instead of one. All of that raises cost; none of it is prevention. |
| `core.hooksPath` pointed elsewhere, or `git -c core.hooksPath=/dev/null` | Same class. |
| A hostile `$SCANNER` via `ENGINE_SECRET_SCAN` | Now announces itself on stderr every run, because an override must be as loud as a bypass — but a determined user can still set it. |
| Anything already published | The moat guards the boundary, not history. Rotate the credential; the repository is not the authority on whether a key is live. |
| Base64/hex-encoded or gzip-compressed secrets | Secrets that are base64-encoded, hex-encoded, gzip-compressed, or otherwise transformed are indistinguishable from benign data by static analysis. A pattern that detects *transformed* secrets detects almost everything. Detection boundaries are declared in the pattern set itself, not here. |

---

## The rule this file exists to enforce

**Do not describe this moat as making anything impossible.** Describe what it prevents: *accidental*
publication by a cooperating developer. When a verifier breaks a claim, the first question is not
"how do I patch this hole" but **"was that claim ever achievable?"** — because a claim that cannot
be true is not fixed by another patch, and chasing it consumes the sessions that should have been
building the product (`docs/CHARTER.md`).
