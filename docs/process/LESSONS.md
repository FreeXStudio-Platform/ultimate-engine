<!-- title: LESSONS -->
# Lessons — what this project learned, and how to apply it

**Status:** PROCESS — durable. Append-only in spirit: a lesson is corrected in place when proven
wrong, never quietly deleted.

Every entry is a lesson **paid for** — it came from a real defect, a real wrong claim, or a real
near-miss in this repository. Each carries the evidence that bought it, so a future session can
judge it rather than obey it.

Format: **what happened → why it matters → how to apply it.**

---

## L-01 · A data file with no consumer activates nothing

**What happened.** Phase 1 was specified as "create five missing data files". Four of them had live
parsers. `TAXONOMY.md` had **no parser at all**, and its validator `check_taxonomy_prefix()` had
**zero callers** — it was dead code. Writing the file and declaring the phase complete would have
produced a confident, entirely false "restored" claim.

**Why it matters.** The most convincing kind of false claim is one where the artifact genuinely
exists. Presence is not activation. Nothing would have failed; the gate simply would never have run.

**How to apply.** Before creating any declarative/config/data file, **find its consumer**. Grep for
a parser, then grep for the parser's callers. If either is missing, the work is *data + wiring*, and
the wiring is the part that matters. State the consumer in the task before starting.

---

## L-02 · Read the code; the plan is a hypothesis

**What happened.** `BUILD_PLAN.md` §3 was wrong in five checkable ways: it named a `VERSION.json`
`gate` key that **no code reads**; claimed 4 CLI commands when 6 exist; claimed the hash-gate was
unwired when `_cmd_check` already called it; listed 8 laws when the rulebook is L1–L23; and treated
`TAXONOMY.md` as data-only (see L-01).

**Why it matters.** A plan written from a prior session's memory decays fastest exactly where it is
most specific. Every one of those five errors was cheap to check and expensive to inherit.

**How to apply.** Treat a plan's *decisions* as binding and its *facts* as claims to verify. Verify
the facts first, in one cheap pass, and **write the corrections back into the plan** — a falsified
fact left standing will be inherited by the next session.

---

## L-03 · Record the unknown as unknown

**What happened.** The rulebook is canonically L1–L23, but **L17 and L22 have zero references**
anywhere in the tree. It would have been effortless to invent two plausible laws and complete the
sequence.

**Why it matters.** An invented law is indistinguishable from a real one to every later reader, and
it would be enforced, cited, and reasoned from. A gap that is *labelled* costs nothing; a gap that is
*filled with fiction* is unrecoverable without archaeology.

**How to apply.** Give the unknown a named status (`reserved`, `declared`, `CANNOT_VERIFY`) and say
what evidence is absent. Completeness of *form* is never worth correctness of *content*.

---

## L-04 · Fail-closed means the empty case blocks

**What happened.** `load_taxonomy_prefixes()` returns an empty set when the file is missing,
unreadable, or malformed. The consuming gate treats an empty set as *"cannot validate — block every
document"*, not *"nothing to check — pass"*.

**Why it matters.** The natural implementation of "no data" is "no findings", which reads as green.
That single default inverts a security gate into a rubber stamp, silently, at exactly the moment the
gate is most needed.

**How to apply.** For every gate, ask explicitly: **what does it do when its input is missing?** Then
*test that path* — falsify it against a **valid** document and confirm the valid document is
blocked. Fail-open is legitimate only when written into the contract (as L10/L11 advisories are).

---

## L-05 · A green suite can be regenerating what it checks

**What happened.** `npm run simulate` **rewrites the golden files** that `npm test` compares against.
Running them in the wrong order silently re-baselines any drift and reports success.

**Why it matters.** The check and the baseline share a file. Ordering, not logic, decides whether the
suite is a test or a rubber stamp.

**How to apply.** `npm test` **before** `npm run simulate` — the documented `&&` is load-bearing.
Generally: never let a run that *regenerates* baselines precede a run that *checks* them, and read
the check result before regenerating anything.

---

## L-06 · Diff the key, not the file

**What happened.** After a simulation run, 12 golden files showed as modified. The instinct is either
"something broke" or "just noise, restore it". Both are guesses. Inspecting *which key* changed showed
only `render_ms` — every `*_sha256` identical, which is the actual determinism guarantee.

**Why it matters.** File-level dirtiness carries almost no information. The same 12-file diff could
have been a genuine non-determinism defect.

**How to apply.** When generated files change, extract the **set of changed keys** before judging:
`git diff -U0 <path> | grep -oE '"[a-z_]+"' | sort -u`. Timing fields are noise; a changed hash is a
finding.

---

## L-07 · A docstring is not a contract

**What happened.** `validate_doc_system.py`'s own module docstring says the gate is *"VERSION.json's
`gate`"*, and `ENGINE_PLAN.md` repeats it. **No code reads a `gate` key.** The gate reads exactly two
keys. The plan inherited the docstring's claim as a requirement.

**Why it matters.** Prose next to code is trusted far more than prose far from code, and it decays
identically. This one propagated from a design doc into a plan into a task specification.

**How to apply.** Confirm a key/flag/field is real by finding the **read site** — `grep 'get("key")'`
— not by finding a mention. Document the difference explicitly when it exists, as `VERSION.json`'s
notes field now does.

---

## L-08 · Measure the baseline before claiming "no regression"

**What happened.** Claiming the edited files were ruff- and mypy-clean required knowing the
*pre-existing* error count. Extracting the pristine versions (`git show <base>:<path>`) and linting
those showed 2 identical ruff errors before and after — so zero introduced — while mypy surfaced 19
pre-existing errors that make the README's "mypy-strict clean" claim **stale**.

**Why it matters.** "Clean" and "no worse" are different claims. Without the baseline, a tool's
output is unattributable, and an inherited defect gets blamed on the current change (or worse, the
current change hides inside the inherited noise).

**How to apply.** Lint/typecheck the **pre-change commit** into a temp dir and diff the error sets.
Report *introduced* separately from *pre-existing*, and file the pre-existing count as its own finding.

---

## L-09 · Sequence verification after the work, or it verifies the wrong world

**What happened.** An extraction workflow's verifier stage ran *after* the implementation had landed.
It duly "refuted" the extractors' correct statements ("TAXONOMY.md does not exist", "the validator has
no caller") — because by then the files existed and the caller was wired.

**Why it matters.** A verifier compares a claim against the world *at verification time*. If the world
moved, its verdicts are noise that reads exactly like signal, and a hasty reader concludes the
extraction was wrong.

**How to apply.** Either finish verification before mutating the tree, or pin verification to a commit
(`git show <sha>:<path>`) so it judges the world the claim described. When a verdict looks
surprising, check the timestamps before believing it.

---

## L-10 · The one who fixed it cannot be the one who clears it

**What happened.** Operator directive at the close of Phase 1, now the load-bearing law of
`docs/process/DEEP_VERIFICATION_PASS.md`.

**Why it matters.** A model verifying its own output converges on its own blind spots — it goes quiet
long before it goes correct. Self-verification reliably converts *unverified* into *verified* while
doing no work, which is strictly worse than no verification, because it removes the doubt that would
have prompted a real check.

**How to apply.** Fresh verifier agents that never saw the implementer's reasoning; they re-derive
from artifacts. The implementer may orchestrate and synthesise, never green-light. Absence of a
verifier is a **red** light.

---

## L-11 · Write it down or lose it

**What happened.** Operator directive: *"no work from memory: all findings, decisions, new work,
everything should be written down so no open gates get forgotten under a heavy load of the one big
project."*

**Why it matters.** A finding held in conversation context is deleted by the next session, a context
compaction, or a crash. The bigger the project, the more certainly an unwritten open gate is a
permanently open gate — and it will be rediscovered later at full cost, or never.

**How to apply.** Every finding lands in `docs/process/OPEN_GATES.md` with a severity and a
disposition, the moment it is found. Every change lands in `CHANGELOG.md` with date, time, version,
file and section. Save as you go, so a crash costs minutes rather than a session.

---

## L-12 · A gate piped into `tail` reports the pipe's exit code, not its own

**What happened.** Checking whether the hash-gate had gone red, the command was
`validate_doc_system 2>&1 | tail -2`. The shell reported **exit 0** while the gate had actually
exited **1** — `$?` was `tail`'s status. Re-running with a redirect showed the truth immediately.

**Why it matters.** This inverts the exact signal you are trying to read, in the direction that
looks like success. Had it not been noticed, a red gate would have been recorded as green in a
document whose whole purpose is to be trustworthy.

**How to apply.** Never pipe a gate, test, or build into `tail`/`head`/`grep` and then test `$?`.
Redirect to a file, check `$?`, then read the file:
`cmd > /tmp/out 2>&1; echo "exit: $?"; head -3 /tmp/out`.

---

## L-13 · A check that derives its universe from the thing it checks cannot fail

**What happened.** `CONS-04` verified that "every mapped gate has a firing contradiction row" by
iterating **the mapping itself**. A gate missing from that mapping was therefore also missing from
the set under test — so the one defect the check existed to catch was structurally invisible. Once
the universe was derived independently (from `export_sanitizer.PRECEDENCE`), it immediately found
two genuinely unmapped gates.

**Why it matters.** The check passed, looked meaningful, and was named accurately. Nothing about its
output suggested a blind spot. This is the quiet cousin of "a checker that cannot fail is worse than
none" — it *can* fail, just never in the direction that matters.

**How to apply.** For any completeness check, ask: **where does the list of things-to-check come
from?** If it comes from the same place as the answer, the check is a tautology. Derive the universe
from source (an enum, a registry, the filesystem) and the expectation from the artifact — never both
from one side. Then falsify it by removing an entry.

## L-14 · A check's pattern is part of its universe — and so is its suppression list

**What happened.** `CONS-06` ("every cited repo path resolves") carried two silent holes, both
found in one session and neither visible in its output:

1. Its regex ended `\.[A-Za-z0-9]{1,5}` — a **five-character extension cap**. So it could not see
   `pre-push.sample`, `world-countries-110m.geojson`, or anything ending `.template` /
   `.properties`. It reported *"every cited repo path resolves across 50 tracked doc(s)"* while two
   tracked documents cited a file deleted in that very session.
2. It built its "declared absent" exemption set by running that regex over **the whole of**
   `ABSENT_PATHS.md` — including the third column, which names *what replaced* each absent file.
   Measured: **7 real files were exempt from the check repo-wide**, among them `RULEBOOK.md`,
   `DOC_WRITING_DOCTRINE.md` and `OPEN_GATES.md`. Deleting any of them would have broken every
   citation of them in the corpus, unflagged. (Counts here are stated **with their conditions**,
   because an independent verifier re-ran them and got different integers by using the *older*
   regex: with the widened pattern over the registry as it then stood, the exemption set went
   **21 → 14**, of which 0 exist; with the pre-fix `{1,5}` pattern the same registry yields 20.
   A count without its measurement conditions is exactly the defect `OG-02` carried for two
   phases, and this lesson is not entitled to an exemption from its own rule.)

**Why it matters.** L-13 said a check must not derive its universe from the thing it checks. These
are the same defect wearing different clothes: the **pattern** decides what exists as far as the
check is concerned, and the **suppression list** decides what is allowed not to. Both silently
shrink the universe, and neither shows up in a green report — hole 2 actually *grew* every time
someone wrote a helpful "what serves its role here" note, so the check got weaker as the docs got
better.

**How to apply.** For any pattern-based check, ask two questions before trusting it:
*what can this pattern not match?* — then construct one such case and confirm the check misses it.
And *where does the exemption set come from?* — parse exemptions from the narrowest possible
source (here, the first column of the row, never the row). A suppression registry must be able to
excuse only the thing each row is **about**, never everything a row happens to mention.

## L-15 · Scope a gate to the artifact it certifies, not to the convenient thing nearby

**What happened.** The new `pre-push` hook took the list of files to secret-scan from git history
(`git diff --name-only <remote> <local>`) and then handed the scanner **the bytes on disk**. On the
new-branch path it was worse: it ran `git ls-files`, which lists the branch you are *standing on*.
So in the most ordinary git workflow there is — commit on a side branch, switch away, push it — the
hook scanned an entirely different branch, found nothing, and printed a confident clean pass while
the secret went to the remote.

Four deliberate falsifications had already been run against that hook and all four passed, because
every one of them put the probe in the working tree. The gate was proven to *fire*; it was never
proven to be *looking at the right thing*.

**Why it matters.** A gate certifies a specific artifact: a push certifies commits, a commit
certifies the index, a build certifies its inputs. Any gate that reads a *different* artifact than
the one it certifies is not weak — it is answering a different question, and it will answer it
correctly and reassuringly forever.

**How to apply.** For every gate, write down the artifact it certifies and the artifact it reads.
If they differ, that is the defect, whatever the test results say. Then falsify it by making the
two disagree — put the probe **only** in the certified artifact and nowhere else. For git, that
means `git archive <sha>` into a temp tree and scanning *that*, never the checkout.

---

## L-16 · An optimisation that skips a gate inherits the gate's entire contract

**What happened.** The build cache keyed on the source document, its sibling spec, the requested
formats, a flag, and a hash of `tools/docgen/*.py`. On a hit it synthesized a **passing**
`GateResult` and skipped the build. Everything not in that key was therefore free to change without
invalidating anything — and an independent pass proved five classes of wrong hit: `assets/glyphs.py`
(one directory below a non-recursive glob), `assets/tokens.json` (not a `.py` file), the embedded
`fonts/*.woff2`, the output directory, and — the serious one — **the entire doc-governance rule
layer**. Editing `DOC_MANIFEST.md` to make a document illegal left it building green from cache,
with the stale artifact on disk and the CLI reporting success. A blocking gate, bypassed by a
performance feature, with no flag involved.

**Why it matters.** The cache's own docstring reasoned carefully about determinism and even about
`--strict` advisories, and was right about both. It simply never enumerated *what the gates read*.
A skip is a claim that re-running would change nothing — which is a claim about every input to
everything being skipped, not just the inputs the optimisation happens to know about.

**How to apply.** Before shipping any skip-if-unchanged mechanism, enumerate the inputs of
**everything the skip bypasses**, gates included, and put them all in the key. Prefer a recursive,
content-typed fingerprint over a curated list: a curated list is a second thing to keep in sync, and
this one was already out of sync on the day it was written. Over-hashing costs a rebuild; under-
hashing serves a stale artifact under a success message. Version the key format so that widening it
invalidates rather than trusts old entries.

*Change history*

| date | change |
|------|--------|
| 2026-08-20 | Register created at the Phase 1 deep pass. L-01…L-11 recorded from Phase 0/1 evidence. |
| 2026-08-20 | L-12 and L-13 added from defects found *during* the deep pass itself. |
| 2026-08-20 | L-14 added from two `CONS-06` blind spots found while closing OG-10 in Phase 2. |
| 2026-08-20 | L-15 and L-16 added from the two CRITICALs found by the Phase 2 deep verification pass — both in work that had already been falsified and reported green. |

---

## L-17 · `UnicodeDecodeError` is a `ValueError`, and `except (OSError, JSONDecodeError)` misses it

**What happened.** Twelve file-reading sites across the engine caught `(OSError,
json.JSONDecodeError)` and believed that covered "the file is unreadable". It does not.
A non-UTF-8 file raises `UnicodeDecodeError`, which is a subclass of `ValueError` and **not** of
either — so it escaped every one of those handlers. `engine_config._raw_config()` is called at import
time by `cli`, `generator`, `adjudication` and `validate_doc_system`, and from `run.py`'s `main()`
*before* the fail-closed wrapper exists — so one bad byte in `engine.config.json` took down every
entry point in the package, `tools.health` included, with a raw traceback.

The class had been fixed **twice, site-locally**, in `classification.py` and `build_cache.py`, each
with a comment explaining it. Never swept, never generalised, never written down. So the third
occurrence was guaranteed, and the fourth would have been too.

**The lesson.** `except (OSError, ValueError)` for anything that decodes text. And when you fix a
bug twice in two files, that is the signal to grep for the class — a defect fixed twice locally is a
defect you have decided not to understand.

**Corollary, the sharper half.** `_load()` returning an empty default on a corrupt file is not
"graceful": `tools/project_index/index.py` swallowed an unparseable index into `{"artifacts": []}`
and the next `_save()` wrote that empty list back over the file. Every registered artifact
destroyed, exit code 0, nothing printed. **Absent and unparseable are different questions and only
one of them has a safe default.**

---

## L-18 · A number nobody compares is decoration

**What happened.** `tools.health` printed `visual-engine suite green (expected 30/30)` on every full
run. The string `"expected 30/30"` was a display literal passed in as an argument and interpolated
into the summary — never parsed from the suite's output, never compared to anything. The check
asserted the process **exit code** and nothing else, so it could see a test that FAILED and was
structurally blind to a test that had been **deleted or skipped**, while printing the number 30 as
though it had checked it. `30/30` was then quoted as fact in two handover documents.

The same shape, twice more in the same pass: `OG-02` quoted a lint error count that was wrong in
three different documents across two phases because nothing measured it; and this session's own
edits took ruff from 22 to 26 silently, caught only because a human ran it by hand.

**The lesson.** If a document or a check states a count, something must **derive** that count and
fail when it drifts. Otherwise it is not a measurement, it is a decoration that gets more trusted
the longer it survives. `SUITE-04` and the pinned `lint_baseline.json` exist for exactly this.

---

## L-19 · A set difference over an empty set passes vacuously

**What happened.** `CONS-01` and `CONS-02` computed `declared - known` and passed when the result
was empty — which is vacuously true when `declared` is empty. Running health where the rule layer
could not be found produced `[PASS] CONS-01 every impact-map dependent prefix is a registered doc
type` over an **empty map and an empty prefix set**, and `[PASS] CONS-02 all 0 manifest id(s) are
registered`. They cost nothing at the time only because sibling `RULE-` checks caught the emptiness
upstream, so the operator still saw red overall — an accident of ordering, not a property.

**The lesson.** Every containment or difference check needs an explicit **non-empty precondition**
on both sides. Write the emptiness guard at the same time as the comparison, not after a verifier
finds it: `all 0 of 0` is the single most confident-sounding way for a check to say nothing at all.

---

## L-20 · Document the bypass you cannot close

**What happened.** The engine goes to real trouble to make its own escape hatches loud —
`ENGINE_SKIP_PREPUSH=1` and `ENGINE_SKIP_PRECOMMIT=1` both print a warning, on the stated principle
that *a silent bypass is indistinguishable from a gate that ran*. It then shipped alongside
`git commit --no-verify` and `git push --no-verify`, which skip every hook with **exit 0, no output,
and no artifact for an audit to inspect** — and the string `--no-verify` appeared **nowhere** in the
tracked tree. Measured, not inferred: zero hits at `d12a13e`.

A near-identical case sat one file over. `ENGINE_SECRET_SCAN` overrides the scanner path and did not
announce itself, so pointing it at any binary that exits 0 replaced the secret gate with nothing,
under the hook's ordinary affirmative *"secret scan clean"* line — strictly worse than a bypass that
at least says so.

**The lesson.** When you cannot close a bypass, **name it** — in the handover, in the hook's own
header, in the configuration reference. An undocumented bypass is worse than a documented one,
because the next reader builds on a false premise about what the moat guarantees. And where you
*can* make an override loud, do: an override must be as loud as a bypass.

---

## L-21 · Scan the object, not a rendering of it

**What happened.** The push-time secret gate was rewritten three times, and each rewrite scanned
something that *represented* the published content rather than the content itself. v1 read the
working tree. v2 read the endpoint diff. v3 materialised each commit with `git archive` — which
looks index-true and is not. Eight independent adversarial verifiers broke v3 four different ways
in one pass, none of them requiring a bypass flag:

- `git archive` honours `export-ignore` from a **tracked or untracked** `.gitattributes`, so a path
  simply vanishes from the scan while the real blob reaches the remote;
- it applies smudge filters and `working-tree-encoding`, so the scanned bytes are provably not the
  recorded bytes;
- two paths differing only in case collide when written to one directory on a case-insensitive
  filesystem, and one blob silently overwrites the other;
- `find -type f` skips symlinks, whose blob content is the target string.

The commit-time gate had the same shape with `git checkout-index`, which is explicitly git's
*working-tree rendering* of the index.

**The lesson.** Every one of those is a property of the RENDERING, not of the content. `git archive`,
`git checkout-index` and a filesystem walk are all lossy, configurable projections of the object
store — and every knob that configures them is a hole in any gate built on top.

**`git cat-file blob <sha>` is the object.** Enumerate the exact objects (`git rev-list --objects`,
`git diff --cached --raw`), read each one directly, and write it to a file named by its **SHA, never
its path** — which additionally defeats basename-based exclusions and makes case collision
impossible. This is L-15 one level deeper: it is not enough to scan the right *artifact* if you scan
it through a transform that someone else controls.

---

## L-22 · When a verifier breaks a claim, ask whether the claim was ever achievable

**What happened.** Twelve CRITICAL findings landed against the git moat in one pass. The reflex —
patch all twelve — was wrong, and following it would have consumed the session. Three of the twelve
could only be reached by **deliberately editing the hook that was supposed to stop you**, and no
client-side hook can survive that: `git commit --no-verify` disables every hook with exit 0 and no
output, and whoever can install a hook can delete it.

So those three were never fixable. The defect was not in the implementation; it was in the
**claim** — the moat had been described in three documents as making leaking *impossible*.

**The lesson.** A broken claim has two possible repairs, and the first question decides which:

1. **Was the guarantee achievable?** Then fix the implementation and re-falsify.
2. **Was it never achievable?** Then fix the *claim* — scope it to what is true, write down what is
   explicitly out of scope and why, and move the unachievable part to where it can actually hold.

Skipping that question turns a finite engineering task into an unwinnable arms race, and the arms
race is always more urgent-feeling than the product. The moat is now scoped, in writing, to
*accidental publication by a cooperating developer* (`docs/process/THREAT_MODEL.md`) — which it
achieves, and which is worth having. Everything it cannot do is named rather than implied.

**Corollary.** Nine of the twelve WERE ordinary accidents — a colleague's fetched branch, a
force-push race, a repo that legitimately uses `.gitattributes`, a key in a commit message, a
vendored scanner that portfolio rule S2 instructs you to create. Scoping a claim is not an excuse to
stop fixing things. It is what tells you *which* things.

---

## L-23 · An exemption is a switch that turns the guard OFF

**What happened.** The `present-tense` guard exempts a paragraph carrying a marker of absence — a
sentence saying a file *is missing* must not be reported for describing a missing file. One entry in
that list was the bare word `" deliberately"`, intended for "deliberately absent".

`docs/plan/BUILD_PLAN.md`'s Phase 3 row says *"every guard **deliberately** falsified first and shown
red"*. Nothing to do with absence. That one word exempted the whole row — the single row in the
corpus describing `tools/corpus_check/` in the present tense while it did not exist, which is
precisely the finding the guard had been written to produce. The guard reported CLEAN.

**Why it matters.** An exemption list is not a list of hints. Every entry is a switch that disables
the guard for everything it matches, so a broad word there is not a small inaccuracy — it is a
silent hole, and it is silent *in the direction of passing*. `CONS-08` learned this twice already:
its "bump" exemption skipped a whole line rather than the version claim on it, and its arrow
exemption cancelled the check on the most important floor claim in the repository.

**How to apply it.**

1. **Every entry in an exemption list must be about the thing it exempts.** `" deliberately absent"`
   is a marker of absence; `" deliberately"` is a word.
2. **Audit the list against the corpus, not against your intent.** For each marker, count the
   findings it is *currently suppressing* and read them. A marker suppressing something real is
   either too broad or hiding a defect, and either way you need to know which.
3. **Retain the probe.** `test_over_broad_exemption_does_not_disarm_present_tense` plants a
   paragraph containing the innocent word beside a real defect and requires the red.

---

## L-24 · A guard's own documentation can recreate the defect it documents

**What happened.** `test-refs` derives its vocabulary of valid check ids from string literals in
source. A test fixture quoting `"OG-998"` as a deliberately-bad probe entered that vocabulary, which
taught the guard that `OG-` was a check prefix — after which **every** `OG-` citation in
`CHANGELOG.md` became a HIGH finding. 155 of them, from one fixture.

The fix excluded the test tree. Then the **docstring explaining that exclusion** quoted the same
probe id, in the same double-quoted form the scanner matches, and it happened again: **158 findings,
from the sentence describing why there had been 155.**

**Why it matters.** A ground truth assembled by scanning text is widened by any text that mentions
it — including the text explaining that it must not be widened. The failure is not carelessness; it
is that prose and data were being read by the same pattern.

**How to apply it.** **Parse, do not scan, when the source has structure.** Python sources are now
read with `ast` and module, class and function docstrings are dropped before literals are collected:
a docstring is prose *about* the code, not code. Where no structure exists (`.mjs`, `.sh`), the
scan stays textual and the risk is stated. And when a guard's ground truth can be widened by a
document, that is the defect — not the document.

---

## L-25 · An environment fact is not a finding about the artifact

**What happened.** The `rendered-output` guard builds the governed corpus and inspects the HTML.
`node_modules` is gitignored by design, so it is absent in a fresh clone, in CI, and in every
`git archive` verification lab. With it absent the build fails on every mermaid figure — and the
guard reported a **CRITICAL corpus defect**.

The consequence was not local. `CONS-11` went red, `tools.health` went red, and **the pre-push hook
runs health** — so the moat refused a *clean* push. In a fresh clone, nothing could be pushed at all.

It was caught by the moat attack harness's **positive control**: *"a clean commit and push are
accepted"*. Every one of the twenty adversarial cases still passed. Only the half that asks whether
the gate lets good work through could see it.

**Why it matters.** "The artifact is wrong" and "this machine cannot check the artifact" are
different answers, and a gate that cannot tell them apart fails closed on the innocent. That is
worse than a false green in one specific way: it trains people to bypass the gate.

**How to apply it.**

1. **SKIP is the answer for an environment fact**, with the cause named — never PASS (the question
   is still open) and never FAIL (nothing is wrong with the corpus). `SUITE-01` and `SUITE-02`
   already did exactly this for the same missing dependency; the new guard simply had to agree.
2. **A SKIP must propagate as a SKIP.** `CONS-11` originally collapsed skip and fail into
   "not green", which reintroduced the problem one layer up.
3. **Keep the positive control.** A two-sided gate is not symmetry for its own sake — here the
   negative half was flawless while the gate was unusable.
4. **Corollary, same session, same shape:** never `raise SkipTest` from `setUpClass`. unittest drops
   the whole class from the run *count*, which is indistinguishable from the broken-import defect
   `SUITE-05` exists to catch — it turned a lab run red on *"111 defined but only 104 ran"*. Let
   each test skip itself; a self-skip is counted.

---

## L-26 · A fix that narrows a hole must be attacked at its NEW edge

**What happened.** Twice in one session, on the same day, a fix that closed a hole was reported as
closed while a sibling of it stood.

* `stamps` granted a **blanket amnesty**: any handover carrying `NEEDS RE-HARDENING` excused every
  drifted stamp in the corpus. That was found and narrowed to *"a handover that names this
  document"* — and a retained regression probe was written for it. Three independent verifiers then
  broke the narrowed version the same way: `HANDOFF.md` carries the marker on one line about a
  *different* file and quotes the rule verbatim on another, while its document index names sixteen
  documents elsewhere. **51 of 57 documents were auto-excused** *(re-derived 2026-08-22: the figure long recorded here was `14 of 57`, which counted `HANDOFF.md`'s mentions alone and even for that file measures 17. **Seven** tracked files carried the marker at `c956619`, and the union of the documents they name is 51 — the blast radius was materially worse than the number that was reported. `OG-107`'s sibling: a count nobody derived.)*, and a genuinely drifted stamp
  was reported compliant. The probe could not see it because it planted its drift on a filename no
  handover contains.
* `present-tense` was disarmed by a bare `" deliberately"` in its *absence* list. That list was
  narrowed and `L-23` was written. `_FUTURE_MARKERS` — the list beside it, with identical
  blast radius — was not, and a verifier walked a false claim past the guard using the word `if`.
  Narrowing *that* then exposed a **third** list, `text._PAST_MARKERS`, gating three guards at once.

**Why it matters.** `docs/process/RULES.md` Rule 1 already says the counter-example must cover the
CLASS, not the instance. These are what it looks like when that clause is *nearly* obeyed: a real
fix, a real probe, and a hole that simply moved one step. The probe was written against the defect
that was found, not against the defect that remained.

**How to apply it.** After narrowing anything — an exemption, an amnesty, a scope, a pattern — ask
**one more question before writing the test**: *what is the widest input that still gets through?*
Then write the probe for **that**, not for the case you just fixed. Concretely:

1. **Enumerate the siblings.** One list narrowed means every list of the same shape is suspect. Grep
   for them. There were three.
2. **Measure the blast radius, do not estimate it — including this lesson's own number.**
   "N of 57 documents" is computable with the guard's own helper, and computing it is what turned
   "narrowed" into "still broken". This clause said **14 of 57** for two passes. Nobody ran the
   helper: a later verifier did, and the real figure is **51 of 57** — seven tracked files carried
   the marker, not one, and even `HANDOFF.md` alone excused 17. The lesson that says *measure it*
   was carrying an estimate, which is the most exact demonstration of the lesson available.
3. **Choose the probe's input adversarially.** A probe on `PROBE_STAMP.md` proves nothing about a
   guard whose hole is triggered by names a handover happens to contain.

---

## L-27 · Verify the finding, not only the fix

**What happened.** A Pass-6 analyzer reported that Gate 9 (`variant_overlap`), the declared L18
moat, "has zero counter-example and **can never pass in the build path**". The first half was
exactly right. The second was wrong: `run_gates` reaches the gate on every export through
`_variant_overlap_against`, and measured directly, it fails closed on a declared-but-missing sibling
and refuses a real overlap.

Had the finding been accepted as written, the "fix" would have been to wire machinery that already
worked — and the true defect, the missing counter-example, would have been closed by accident or
not at all.

**Why it matters.** `DEEP_VERIFICATION_PASS.md` §1 says *verify the thing, not the report* about the
implementer's report. It applies with equal force to the **verifier's** report. A finding is a claim
like any other, arriving with more authority than most because it is adversarial and well-evidenced.
Eleven agents producing eighty findings will produce some that are half right, and half right is the
most dangerous shape: the evidence is real, so the conclusion reads as proven.

**How to apply it.** Before fixing, re-derive the finding from the artifact yourself — it usually
costs one command. Then write down which half was true. The register row for `OG-93` says *"the
finding was half right"* and names both halves, so the next reader inherits the correction rather
than the original claim.

---

## L-28 · A guard that reads only source cannot certify output

**What happened.** Three defects in one pass, one shape.

* `build.py` was deleted, and **seven instructions to run it survived in tracked rendered HTML** —
  invisible to `built-claims`, which read Markdown only. The source was clean; the artifact was not.
* `python3 -m tools.docgen.cli render` had raised `AttributeError` on **every** invocation for seven
  commits. `built-claims` proved the subcommand and its flags were *declared* — it reads argparse
  source — and nothing anywhere *ran* it.
* `rendered-output`'s only CRITICAL pattern matched `<!-- figure:` against text that had comments
  stripped first, so it could never fire. The pattern was correct; the input was wrong.

**Why it matters.** This is `L-21` ("scan the object, not a rendering of it") and doctrine §8.4
("grep the outputs") arriving from the opposite direction: not *reading a rendering of the object*,
but *reading the object and never the rendering*. Both are the wrong-artifact class, and the gap
between **declared** and **runs**, or between **source** and **built**, is where it lives.

**How to apply it.**

1. **A guard over commands must read built output too.** `built-claims` now scans tracked `.html`
   alongside Markdown; a command surviving only in a rendered page is still an instruction.
2. **Declared is not runs.** If a surface is documented, something must *invoke* it —
   `tools/tests/test_cli_surface.py` exists for exactly that, and it found nothing only because it
   was written after the defect.
3. **Check what your pattern is actually being handed.** Assert the control: a probe that produces
   no finding in a clean artifact and a finding in a planted one proves the input reaches the
   pattern. `rendered-output`'s CRITICAL had been green for its whole life without that control.

---

## L-29 · A probe that iterates what a fix DELETED passes for free, forever

**Paid for by:** Pass 7, `OG-116`'s neighbourhood — the single most valuable result of the pass.

A retained counter-example — since replaced by
`test_no_exemption_marker_excuses_a_claim_in_ANOTHER_sentence`, and named at the time for the
ordinary English it claimed to cover — looped over seven words — `if`, `when`, `after`, `until`, `may`, `should`, `could` — and asserted
that each still got caught. Every one of those words had already been **removed** from the exemption
list when the test was written. It therefore proved that the guard ignores words the guard does not
know: true, unfalsifiable, and worth nothing. Meanwhile `" will "` and `" shall "` remained in the
list and were never probed.

The test was green, the register row said the hole was closed, and the hole was open.

**The rule.** A probe's inputs must be **derived from the live data structure at run time**, never
copied from the diff that changed it. Iterate `_FUTURE_MARKERS`, `CLAIMS`, `_RESIDUE_PATTERNS`,
`GUARDS` — the thing itself. Then adding an entry probes it automatically, and removing one cannot
leave a test quietly passing over an empty set. Where a derived list could legitimately be empty,
assert a floor (`assertGreater(len(markers), 10)`) so the loop cannot become vacuous.

`docs/process/RULES.md` Rule 1 says an assertion must cover the CLASS. This is its sharpest corner:
**the class is defined by what remains, not by what was fixed.**

---

## L-30 · The type checker is a gate — it found a crash no test did

**Paid for by:** `OG-135`.

Adding a third return value to `inspect_contrast` left one exit — the path taken when a built
document declares no colour custom properties — still returning two. Every caller unpacks three, so
that path raised `ValueError: too many values to unpack`: a crash, in the guard whose entire job is
to report exactly that condition. 196 tests were green. `mypy --strict` named the line.

The tests could not see it because no fixture produced a document with no theme block — the corpus
has none, and a probe has to be *written* to reach a branch. Static analysis does not need a fixture
to reach a branch; it reads all of them.

**The rule.** Treat `ruff` and `mypy --strict` ceilings as health checks that can fail a run, not as
tidiness. `SUITE-04` pins both (0 and 22) and **the ceiling may only go DOWN**. When a change pushes
the count up, the errors it added are the finding — read them before raising anything.

---

## L-31 · Measure a fix's COST on the real corpus before shipping it

**Paid for by:** `OG-116`, the finding that was built and then deliberately rejected.

The hole was real: a bare filename declared in `ABSENT_PATHS.md` was excused in any sentence,
including a false present-tense claim about it working. The fix was implemented, and run: **12
findings, 11 of them on correct prose** — a rulebook saying no brand manifest ships, a skill
describing its own runtime output, three external files cited as measurement evidence.

Shipping it would have meant widening the exemption lists to silence eleven true sentences, using
exactly the ordinary English (`no`, `output`, `supplies`) that had already produced three over-broad
lists in this package. The cheaper-looking option was the one that damages the gate.

**The rule.** A guard change is not done when it catches the probe; it is done when it has been run
against the whole corpus and the findings have been *read*. If most of them are on correct prose,
the guard is wrong even though the hole is real — and the honest deliverable is the measurement,
recorded, not a half-built fix. A guard that reports eleven correct sentences to catch one wrong one
is a guard people switch off, and `docs/process/OPEN_GATES.md` records what that costs.

Some classes genuinely have no mechanical answer. `present_tense`'s own docstring names this one:
*direction-and-soundness errors — no grep finds that; a careful reader does.*

---

## L-32 · A subtitle is not a record — infer nothing from the SHAPE of text

**Paid for by:** `OG-140`, the widest single hole this project has recorded.

`under_dated_heading` decided a line was history because a date appeared in some enclosing heading.
It is a reasonable-sounding rule and it was wrong by 2458 lines: **29.6% of all corpus prose** was
exempt from five guards *and* from `CONS-06`, which the pre-push moat runs. `CHANGELOG.md` at 96.9%
and `VERIFICATION_LOG.md` at 97.2% are correct — those really are append-only records. But three
**live normative policies** were 78–88% exempt for one reason: each carries a version strapline as
an `###` heading, and every line beneath a document's subtitle is structurally beneath a dated one.

The rule inferred a *property of the document* from a *property of the text*, and text resembles
things it is not.

**The rule.** When an exemption turns a guard off, the thing being exempted must **declare itself**.
`ABSENT_PATHS.md` is this project's own precedent: deliberate absence is legal because it is written
down and reviewable, not because a path looks absent. Record-ness is now the same —
`<!-- record: append-only -->` — and the shape test only decides *which part* of a declared record
is exempt. Two conditions, and the narrow one alone is never enough.

The tell that this was wrong all along: the fix RAISED coverage everywhere it touched (`cross-doc`
395→469, `built-claims` 344→420, `test-refs` 135→147, `present-tense` 110→119) and immediately
surfaced a defect that had been sitting invisible. An exemption that is silently removing a third of
your corpus is not a nicety.

---

## L-33 · A check the measured thing can satisfy is not a check

**Paid for by:** `OG-155`, while writing a fix for a different defect.

The new assertion was "every `gate_*` function must be called somewhere", implemented as
`f"{fn}(" in source`. It passed on a deliberately inert gate, because `def gate_x(` **contains**
`gate_x(` — every function satisfied "is called" by its own definition. The check was written to
close a hole and reproduced the hole in the same breath.

`test_refs._defined_ids` already carries this lesson in its docstring — *"A ground truth that
documentation can widen is not a ground truth"* — and strips Python docstrings with `ast` because
its own explanation of the defect once recreated it. `cross_doc` has the same shape open today.

**The rule.** Derive a ground truth from **structure, not text**: `ast` call nodes, not substrings;
parsed tables, not greps. And falsify every new check by planting the thing it claims to catch —
this one was caught within a minute of being written, because it was falsified before being trusted
(`L-15`). A check nobody planted a defect against is a check nobody has seen work.

---

## L-34 · A coverage number that FALLS after you add a check is the finding

**Paid for by:** `OG-143`.

Adding `node <script>` detection to `built-claims` took its coverage from 344 to **264**. Adding a
pattern cannot reduce coverage, so the number was the bug report: over-escaping in the edit had
broken the pre-existing `_NPM_RE` into a literal-backslash pattern that matched nothing. Fixed, the
same edit measured 420.

**The rule.** Every guard here reports what it examined. Read that number on every change, and treat
a fall as a defect until proven otherwise — it is the cheapest regression detector in the system and
it costs nothing to look at. The corollary is why the number must exist at all: a guard that reports
only pass/fail cannot tell you it stopped looking.

---

## L-35

**An agent handed a lab recipe will run it against the live checkout, and `git checkout --` is a
destructive write.**

Measured twice on 2026-08-23, in one session, by two different actors.

*First:* a triage agent was given a `mktemp` + `git archive` recipe and told the repository was
read-only. It ran its mutations in the real tree and **committed them to `master`** — `add 11th
guard` and `move tier to end`, two probes that neuter a registry and invert the security spine.
They sat on the branch until a later step noticed the author line `t <t@t>`, the throwaway identity
from the lab recipe. *Second:* a fix lane ran `git stash` to isolate a lint baseline while five
other lanes had uncommitted work; 58 files reverted to `HEAD` and survived only inside `stash@{0}`.
*Third — and this one was me:* I ran `git checkout --` on two test files to undo a bad edit of my
own, and discarded roughly 600 lines of lane work, after writing the rule that forbids it.

**The rule.** In any prompt that hands an agent a lab recipe, name the destructive verbs
explicitly — `commit`, `add`, `stash`, `reset`, `revert`, `clean`, and **`checkout -- <path>`** —
because "read-only" does not read as "do not run the recipe here", and `checkout` does not read as
destructive at all. It is the only one of those verbs whose everyday meaning is *navigate*. To undo
your own edit, re-edit it or restore from a copy you made first; never ask git.

**And keep the wreckage.** All three were fully recovered, and in every case because the destroying
step left something behind: an unpushed commit, an undropped stash, an agent transcript that still
held the write operations and could be replayed. Recovery came from the artifact, never from
memory. Verify a recovery by **content** — the classes and tests that should be present — never by
line count, which agrees with itself while being wrong.

---

## L-36

**We built a token-saving engine and never switched it on for ourselves; every agent paid full
price for a map the engine exists to hand them.**

Measured 2026-08-23, at the close of Phase 3. The navigation layer was empty in every one of its
parts at once: `PROJECT_INDEX.json` held **1** artifact for 295 tracked files, the content index had
never been generated, and the dependency graph reported **0 nodes / 0 links** across ~75 real
modules — in a gitignored directory, so nothing survived to the next session even when it did build.
The graph was empty for a one-line reason: its source root was still the shipped example's `src`,
and this repository's Python lives in `tools/`. The walker fails open on a missing directory, so it
scanned nothing, wrote an empty graph, and **exited 0**.

The consequence was the whole session's cost. Roughly thirty dispatched agents each began with
`git ls-files` and a grep across the tree — **200-350k tokens each**, measured — rebuilding by hand
a map that is 1,354 tokens when derived. The map is **0.08%** of the tree it orients you in.

**The rule.** A project whose purpose is to make other work cheaper must be its own first customer,
and "we will use it once it is finished" is how it never gets used. Two mechanical corollaries, both
paid for here: **a builder that emits an empty result must exit non-zero** — an empty map is not a
result, it is a confident lie that every downstream reader believes; and **a derived artifact must
be committed and ratcheted**, or it is not a source of truth, it is a cache. `blueprint check` runs
inside the retained suite, so a stale map fails the push; that ratchet, not the map, is what makes
it trustworthy.

---

## L-37

**A probe must CREATE or DERIVE its condition, never borrow it from the corpus — because a corpus
that is expected to improve will break every probe anchored to how bad it is now.**

Measured three times on 2026-08-23, and each break happened at the exact moment the thing being
measured got **better**:

1. The phase-gate probes planted a second blocking row by **copying an existing one**. They broke
   the day the last blocker was closed and there was none to copy — reporting *"the register no
   longer carries a row to copy"*. Zero blockers is the state this project should spend most of its
   life in, so those probes were built to fail during normal operation.
2. A probe planted the old false wording *"carries zero blocking rows"* and required a finding. That
   finding stops firing the moment the truth genuinely **is** zero, because the sentence is then
   true. The probe silently stopped testing anything and then failed for the one reason that is not
   a defect.
3. A probe hardcoded four documents as carrying a stale count. One of them had that count
   **deleted** — the correct repair under Rule 2, since a fact code owns should not be restated in
   prose. **Obeying a rule broke a test that depended on violating it.**

**The rule.** A probe owns its fixture. Synthesise the row, plant the claim, build the tree — and
anchor on something structural (a table header, a registry's shape) rather than on a data row whose
existence is precisely what varies. When the subject set genuinely must come from the live corpus,
**derive it and assert it is non-empty**, so the probe says *"there is nothing left to test here"*
instead of silently passing over an empty set.

**The corollary, learned inside the third fix.** Deriving that subject set, the first attempt
searched for the claim family's internal NAME (`registered corpus guards`) and found nothing: the
documents spell the count as an English word followed by *"guards"*, and share not one token with
the name the code uses. **The label a fact carries in code is not the words a document says it
in.** (The example was originally written out in full, numeral and all — and the `counts` guard
refused it the day an eleventh guard landed, which is this file agreeing with Rule 2 about its own
sentence.) That is Rule 2's own lesson pointed back at the test that enforces it.

---

## L-38

**A convention a gate reads, and that nothing enforces, is a gate with an expiry date.**

Measured 2026-08-29, at the Phase-6 closeout. `cross_doc`'s rule-2 machinery refuses a
`SCHEDULED (Phase N)` register row whose phase the plan marks COMPLETE, on the stated ground that
*a deferral to finished work is parked forever*. It answers *is N complete?* by looking for a
completion marker **inside phase N's own table row** — `✅`, `— DONE <sha>`, five more spellings
added after a verifier defeated the first two.

Phases 1-3 carry a marker. Phases 4, 5 and 6 shipped without one, because completion had quietly
migrated into the status paragraph at the top of the same file. Nobody decided to stop marking rows;
the convention simply lapsed. **The branch therefore could not fire for two entire phases**, and
`OG-07` and `OG-63` — both deferred to Phase 4, both actually finished *inside* Phase 4 — sat in the
register's `## Open` table ever since, over-reporting the open-defect count while every gate
reported clean.

Note what did *not* fail. The guard ran. Its tests passed. Its docstring described the protection
accurately. The corpus was green on the same run that carried two stale deferrals. **A gate does not
announce that its input convention has gone away** — it just stops finding things, and stopping is
indistinguishable from success.

**The rule.** When a check reads a hand-maintained marker, that marker needs its own check. Prefer
deriving the fact instead; where it genuinely must be authored, state it **twice in independent
places and reconcile them**, which is what `CONS-02` does for the manifest against the taxonomy and
what `CONS-13` now does for the plan's prose against its rows. And write the reconciliation so it
**fails when it can derive neither side** — a vacuous pass rebuilds the same blindness one layer up,
which is `L-19` and `L-37` arriving at the same door from a third direction.

**The tell, for a reviewer.** Ask of any gate: *what would make this silently stop finding things?*
If the answer is "somebody stops writing X by hand", the gate is not finished.

---

## L-39

**Fixing the source and re-reading the source proves nothing about the artifact you publish.**

Measured 2026-08-29, in Phase 6's second verification round. The completeness report's three state
definitions were wrong, a verifier said so, and the fix corrected them in the code **and** in the
docstring — which then announced that the offending word was *"gone from both"*. It was not gone: the
renderer held a **third**, hardcoded copy of the definitions, and that copy is the one the published
`blueprint/COMPLETENESS.md` carried. The artifact contradicted itself 79 lines apart, and most of
its nodes still failed the definition printed above them.

The corrected docstring is the sharpest part of the evidence. *"Both"* was an honest count of the
places the author had looked, asserted as a count of the places that exist.

**The rule.** A fix to derived output is not landed until the **output** is re-read. Grep the whole
tree for the string being corrected before believing a count of copies — and where the same fact is
rendered in more than one place, make it **data with one owner** rather than three literals that
happen to agree today. `completeness.STATE_DEFINITIONS` is that owner now, and the renderer emits
from it rather than restating it.

**The corollary.** "Both", "all three", "everywhere" in a commit message or a docstring is a
*claim*, not a summary. Derive it or drop the quantifier.

---

## L-40

**A ratchet whose memory is `HEAD` has no memory, and a lab that `git init`s its own tree cannot
test one.**

Measured 2026-08-29, in Phase 6's second verification round, as two halves of one defect.

*The invariant.* The depth ratchet remembers the highest floor each container has ever been
committed with, so a container cannot quietly get shallower. The first implementation read that
history from `HEAD` — and `HEAD` is written by the very commit under scrutiny. Lower a floor,
commit, and the memory now contains the lowered value: **one extra commit defeats it**, which is not
an attack so much as ordinary work.

*The blind spot that let it ship.* Every probe for the ratchet runs inside a lab, and a lab
`git init`s its own tree — so inside a probe there **is** no prior history, and `HEAD` is the state
under test. The loosening direction was not merely untested; it was **inexpressible**. A verifier
lowered a floor, committed it, and watched every probe pass, including the one the author had
labelled *"the positive control"*.

**The rule.** Any *highest-ever* or *never-decreases* invariant must read a history that **the
change under test cannot write**, and must be adjudicated somewhere that history is real. The
ratchet now takes the maximum floor across the spec's whole git history and is enforced by
`CONS-12` against the actual repository root, precisely because the retained probes structurally
cannot see it. **When a probe's environment lacks the dimension the invariant lives in, the probe is
not weak evidence — it is no evidence**, and something outside the lab has to carry the check.
