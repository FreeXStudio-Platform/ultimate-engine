#!/usr/bin/env bash
# Retained counter-examples for the git moat — the twelve attacks that broke it, kept runnable.
#
# WHY THIS FILE IS IN THE REPOSITORY. An adversarial pass broke the moat twelve ways. Each was
# reproduced red, fixed, and re-attacked — in a throwaway script under /tmp, which was then thrown
# away. `CHANGELOG [0.3.2]` cited "12-case harness, all red first, 12 passed 0 failed" as the
# evidence for every moat CRITICAL, and `THREAT_MODEL.md` claimed the cases "are re-run by the
# harness". Neither was true: no harness existed in the tree, and nothing re-ran anything.
#
# The ninth verifier found that, and it is `docs/process/RULES.md` Rule 1 violated on the single
# most load-bearing claim this project makes: *a falsification performed once by hand and not
# retained does not count*. This file is that falsification, retained.
#
# Run:  bash tools/tests/hook_attacks.sh        (exit 0 = every attack still refused)
#   or: python3 -m tools.health --full          (the same attacks, reported as SUITE-06)
#
# ⚠ **BOTH invocations must cost the same, and until 2026-08-23 they did not.** Each of the ~20
# lab pushes below runs the real pre-push hook, which runs `tools.health`, which starts
# `STRUCT-04`'s own ~72 s behavioural hook probe — the same evidence this harness is already
# producing, once per push. `tools/health/checks.py` suppresses that nesting with a probe marker
# (a random token plus a marker file only the minting process owns), and ONLY `tools.health` minted
# one. So the invocation written on the line above — the one this header has always documented —
# did not terminate: measured at HEAD, `timeout 600 bash tools/tests/hook_attacks.sh` reached 7 of
# 21 verdicts and was killed, while `python3 -m tools.health --full` ran all 21 in ~5 min. A
# documented command that does not finish is worse than an undocumented one, because the reader
# concludes the moat is broken rather than the instructions. The harness now mints its own marker
# below (respecting one it inherits from SUITE-06), so the documented run IS the supported run.
#
# Health runs it as SUITE-06 under --full; it is too slow for every commit (real git, real remotes).
#
# Each case builds a lab from the CURRENT working tree — not from HEAD — so it tests what you are
# about to commit, which is the only version that matters.
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROOT="$(mktemp -d)"
LAST_OUT="$(mktemp -t hookattack-out)"      # see run_quiet(); created here so ONE trap owns it
PROBE_DIR="$(mktemp -d)"
# ⚠ **ONE trap per signal, or the earlier one silently stops firing.** Bash keeps only the LAST
# trap set for a given signal. This file used to set `trap 'rm -rf "$ROOT"' EXIT` here and
# `trap 'rm -f "$LAST_OUT"' EXIT` forty lines further down, so the second replaced the first and
# `$ROOT` — a full `git ls-files` copy of this tree plus a bare remote and four helper dirs,
# measured at 13 MB — was leaked into /var/folders on EVERY run, of a harness whose whole job is
# to run ~20 times in a row. Everything this script creates is removed by this one handler.
trap 'rm -rf "$ROOT" "$PROBE_DIR"; rm -f "$LAST_OUT"' EXIT
# Mint the nesting marker `tools/health/checks.py` looks for, unless SUITE-06 already gave us one
# (never clobber an inherited marker — the outer run owns its own lifetime). Without it every lab
# push below re-runs the ~72 s hook probe this harness is itself performing; with it, the two
# documented invocations above cost the same. The token names a file only this process can have
# created, so a stale exported variable in someone's shell suppresses nothing.
#
# The two sentinel comments below are LOAD-BEARING, not decoration:
# `tools/tests/test_health_guards.py` extracts the lines between them and executes THIS text, so
# the counter-example for "the documented invocation costs the same as the supported one" runs the
# real block rather than a paraphrase of it. Renaming a sentinel turns that test red on purpose.
# >>> probe-marker mint
if [ -z "${ENGINE_HOOK_PROBE_MARKER:-}" ]; then
  ENGINE_IN_HOOK_PROBE="$(od -An -tx1 -N16 /dev/urandom | tr -d ' \n')"
  ENGINE_HOOK_PROBE_MARKER="$PROBE_DIR/$ENGINE_IN_HOOK_PROBE.marker"
  printf '%s' "$ENGINE_IN_HOOK_PROBE" > "$ENGINE_HOOK_PROBE_MARKER"
  export ENGINE_IN_HOOK_PROBE ENGINE_HOOK_PROBE_MARKER
fi
# <<< probe-marker mint
KEY='AKIA''IOSFODNN7EXAMPLE'                    # split so this file is not itself a scannable secret
SEC='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
# The scanner matches the FIELD NAME, not just the value, so the literal is assembled at runtime
# too. This file describes secret-shaped inputs for a living; it must not contain one. (The moat
# refused this very file on its first commit — which is the gate working, on its own test suite.)
SECFIELD='aws_secret''_access_key'
pass=0; fail=0; fail_attack=0; fail_control=0

# A verdict's EXPECTED value is its class: `verdict 1` asserts an attack is REFUSED,
# `verdict 0` asserts a legitimate operation is ACCEPTED (a positive control). Those two failing
# mean opposite things — a failed attack is a hole in the moat, a failed control is a broken lab or
# a red health of some unrelated kind — and the summary reported both as "N moat attack(s) are no
# longer refused". Twice measured: once earlier and again in round 4, where 2 failing controls
# (untracked new modules absent from a `git ls-files` lab) were read as 2 un-refused attacks and
# cost a full misdiagnosis each time. The counts are split at the source so the reader downstream
# cannot re-merge them.
verdict() {  # $1 expected $2 actual $3 label
  if [ "$1" = "$2" ]; then printf '   PASS  %s\n' "$3"; pass=$((pass+1)); return; fi
  if [ "$1" = "0" ]; then
    printf '   FAIL  [control] %s (exit %s, expected %s)\n' "$3" "$2" "$1"
    fail_control=$((fail_control+1))
  else
    printf '   FAIL  [attack]  %s (exit %s, expected %s)\n' "$3" "$2" "$1"
    fail_attack=$((fail_attack+1))
  fi
  fail=$((fail+1))
  # ⚠ **A FAILING ATTACK MUST SAY WHY** (`OG-138`). Every push here is `>/dev/null 2>&1`, so a
  # failure printed an exit code and nothing else. When the POSITIVE control ("a clean commit and
  # push are accepted") failed, the report read "1 moat attack(s) are no longer refused" — which
  # points at the moat, while the actual cause was `CONS-06` failing on an unrelated documentation
  # path: pre-push runs `tools.health`, so a red health of ANY kind fails the clean-push control.
  # Two symptoms, one cause, and the message named the wrong one. Whatever the last command wrote
  # is the evidence; print its tail.
  if [ -s "${LAST_OUT:-/dev/null}" ]; then
    printf '         └─ last output:\n'
    sed -e 's/^/            /' "$LAST_OUT" | tail -8
  fi
}

# Capture-and-report wrapper: run a command with its output kept for `verdict` to show on failure.
# Use in place of `cmd >/dev/null 2>&1` where the exit code feeds a verdict.
# `$LAST_OUT` is created at the top of this file, under the single EXIT trap.
run_quiet() { : > "$LAST_OUT"; "$@" > "$LAST_OUT" 2>&1; }

setup_base() {   # ONE tree copy for the whole run
  mkdir -p "$ROOT/repo"
  ( cd "$SRC" && git ls-files -z | xargs -0 tar -cf - ) | tar -x -C "$ROOT/repo"
  ( cd "$SRC" && git diff --name-only --diff-filter=d ) | while read -r f; do
      [ -f "$SRC/$f" ] && cp "$SRC/$f" "$ROOT/repo/$f"
  done
  cd "$ROOT/repo" || exit 1
  export GIT_AUTHOR_NAME=a GIT_AUTHOR_EMAIL=a@b GIT_COMMITTER_NAME=a GIT_COMMITTER_EMAIL=a@b
  git init -q -b master . >/dev/null 2>&1
  git add -A >/dev/null 2>&1
  git commit -q -m base --no-verify >/dev/null 2>&1
  bash tools/hooks/install.sh >/dev/null 2>&1
  BASE_SHA="$(git rev-parse HEAD)"
}

lab() {  # $1 = case name — reset the ONE repo to base and re-seed a fresh bare remote
  # Reuse rather than re-copy. Copying the tree per case cost ~50 s each and made the harness too
  # slow to be a gate — and a gate nobody runs is the opt-in problem this engine already fixed once.
  # Every knob a case can turn is reset here explicitly; anything missed would silently leak state
  # from one attack into the next, which is its own false result.
  cd "$ROOT/repo" || exit 1
  git checkout -q -B master "$BASE_SHA" >/dev/null 2>&1
  git reset -q --hard "$BASE_SHA" >/dev/null 2>&1
  git clean -qfdx -e node_modules >/dev/null 2>&1
  rm -f .git/info/attributes
  git config --remove-section filter.scrub >/dev/null 2>&1
  for b in $(git for-each-ref --format='%(refname:short)' refs/heads | grep -v '^master$'); do
    git branch -q -D "$b" >/dev/null 2>&1
  done
  for t in $(git tag); do git tag -d "$t" >/dev/null 2>&1; done
  for r in $(git remote); do git remote remove "$r" >/dev/null 2>&1; done
  rm -rf "$ROOT/remote.git" "$ROOT/peer" "$ROOT/other" "$ROOT/fakebin" "$ROOT/quietbin"
  git init -q --bare "$ROOT/remote.git" >/dev/null 2>&1
  git remote add origin "$ROOT/remote.git" >/dev/null 2>&1
  # Seeded with --no-verify: this is SETUP, not a case, and running the full gate 15 times would
  # triple the harness for no signal.
  git push -q --no-verify origin master >/dev/null 2>&1
  echo "$ROOT"
}

setup_base

echo "== controls =="
L=$(lab ctl); cd "$L/repo"
echo note > n.txt; git add n.txt; git commit -q -m ok >/dev/null 2>&1
run_quiet git push origin master; verdict 0 $? "a clean commit and push are accepted"
printf 'AWS_ACCESS_KEY_ID=%s\n' "$KEY" > tip.txt; git add tip.txt
git commit -q -m tip --no-verify >/dev/null 2>&1
git push origin master >/dev/null 2>&1; verdict 1 $? "a secret at the tip is refused"

echo "== the twelve =="
L=$(lab a); cd "$L/repo"
printf 'creds.env export-ignore\n' > .gitattributes; git add .gitattributes
git commit -q -m attr --no-verify >/dev/null 2>&1
printf 'AWS_ACCESS_KEY_ID=%s\n' "$KEY" > creds.env; printf 'ok\n' > i.txt
git add creds.env i.txt; git commit -q -m y --no-verify >/dev/null 2>&1
git push origin master >/dev/null 2>&1; verdict 1 $? "export-ignore (tracked .gitattributes)"

L=$(lab b); cd "$L/repo"
printf 'local.env export-ignore\n' > .git/info/attributes
printf 'AWS_ACCESS_KEY_ID=%s\n' "$KEY" > local.env; printf 'ok\n' > o.txt
git add local.env o.txt; git commit -q -m y --no-verify >/dev/null 2>&1
git push origin master >/dev/null 2>&1; verdict 1 $? "export-ignore (untracked .git/info/attributes)"

L=$(lab c); cd "$L/repo"
git config filter.scrub.smudge 'sed s/AKIA[A-Z0-9]*/SCRUBBED/'; git config filter.scrub.clean cat
printf 'f.env filter=scrub\n' > .gitattributes
printf 'AWS_ACCESS_KEY_ID=%s\n' "$KEY" > f.env
git add .gitattributes f.env; git commit -q -m y --no-verify >/dev/null 2>&1
git push origin master >/dev/null 2>&1; verdict 1 $? "a smudge filter rewriting the scanned bytes"

L=$(lab d); cd "$L/repo"
git clone -q "$L/remote.git" "$L/peer" >/dev/null 2>&1
( cd "$L/peer" && git config user.email p@e && git config user.name p && git checkout -q -b wip \
  && printf 'AWS_ACCESS_KEY_ID=%s\n' "$KEY" > peer.env && git add peer.env && git commit -q -m wip ) >/dev/null 2>&1
git remote add peer "$L/peer" >/dev/null 2>&1; git fetch -q peer >/dev/null 2>&1
git checkout -q -b integrate peer/wip >/dev/null 2>&1
printf 'notes\n' > r.txt; git add r.txt; git commit -q -m i --no-verify >/dev/null 2>&1
git push origin integrate >/dev/null 2>&1; verdict 1 $? "commits inherited from a PEER remote"

L=$(lab e); cd "$L/repo"
git clone -q "$L/remote.git" "$L/other" >/dev/null 2>&1
( cd "$L/other" && git config user.email o@e && git config user.name o && printf 'x\n' > ot.txt \
  && git add ot.txt && git commit -q -m o && git push -q origin master ) >/dev/null 2>&1
printf 'AWS_ACCESS_KEY_ID=%s\n' "$KEY" > mid.env; git add mid.env
git commit -q -m mid --no-verify >/dev/null 2>&1
git rm -q mid.env; git commit -q -m redact --no-verify >/dev/null 2>&1
git push --force origin master >/dev/null 2>&1; verdict 1 $? "an unresolvable range must not fall back to endpoints"

L=$(lab f); cd "$L/repo"
mkdir -p kit; printf '#!/bin/sh\nAWS_ACCESS_KEY_ID=%s\n' "$KEY" > kit/secret-scan.sh
printf 'note\n' > kit/README.md; git add kit
git commit -q -m vendor --no-verify >/dev/null 2>&1
git push origin master >/dev/null 2>&1; verdict 1 $? "a file named secret-scan.sh (S2 instructs vendoring one)"

L=$(lab g); cd "$L/repo"
printf 'ok\n' > m.txt; git add m.txt
git commit -q -m "revoke old key $KEY / $SEC" --no-verify >/dev/null 2>&1
git push origin master >/dev/null 2>&1; verdict 1 $? "a secret in a COMMIT MESSAGE"

L=$(lab h); cd "$L/repo"
printf 'f1.txt working-tree-encoding=UTF-16\n' > .gitattributes
printf '%s = %s\n' "$SECFIELD" "$SEC" | iconv -f UTF-8 -t UTF-16 > f1.txt
git add f1.txt >/dev/null 2>&1
git commit -q -m enc >/dev/null 2>&1; verdict 1 $? "an encoding filter at commit time"

L=$(lab i); cd "$L/repo"
printf 'innocent\n' > casetest.txt; git add casetest.txt
BLOB=$(printf 'AWS_ACCESS_KEY_ID=%s\n%s = %s\n' "$KEY" "$SECFIELD" "$SEC" | git hash-object -w --stdin)
git update-index --add --cacheinfo 100644,"$BLOB",CASETEST.TXT >/dev/null 2>&1
git commit -q -m case >/dev/null 2>&1; verdict 1 $? "a case-collision in the index"

L=$(lab j); cd "$L/repo"
mkdir -p .venv/bin; printf '#!/bin/sh\nexit 0\n' > .venv/bin/python; chmod +x .venv/bin/python
printf 'AWS_ACCESS_KEY_ID=%s\n' "$KEY" > v.env; git add v.env
git commit -q -m venv >/dev/null 2>&1; verdict 1 $? "a fake .venv interpreter must not neuter the gates"

L=$(lab k); cd "$L/repo"
printf -- '---\nid: TST-9\ntitle: t\nclassification: secret\nsurface: none\naudience: a\nowner: o\nstatus: draft\nlast_reviewed: 2026-01-01\n---\n\n# x\n' > leak.md
git add leak.md >/dev/null 2>&1
git commit -q -m classified >/dev/null 2>&1; verdict 1 $? "a classified document outside the vault"

L=$(lab l); cd "$L/repo"
printf -- '---\nid: TST-8\ntitle: t\nclassification: secret\nsurface: none\naudience: a\nowner: o\nstatus: draft\nlast_reviewed: 2026-01-01\n---\n\n# x\n' > side.md
git add side.md; git commit -q -m c --no-verify >/dev/null 2>&1
git push origin master >/dev/null 2>&1; verdict 1 $? "a classified document committed with --no-verify is caught at PUSH"

echo "== the ninth verifier's additions =="
L=$(lab m); cd "$L/repo"
printf 'ok\n' > t.txt; git add t.txt; git commit -q -m t --no-verify >/dev/null 2>&1
git tag -a probe-tag -m "rotate old key $KEY" >/dev/null 2>&1
git push origin refs/tags/probe-tag >/dev/null 2>&1
verdict 1 $? "a secret in an ANNOTATED TAG message"

L=$(lab n); cd "$L/repo"
mkdir -p "$L/fakebin"; printf '#!/bin/sh\nexit 0\n' > "$L/fakebin/python3"; chmod +x "$L/fakebin/python3"
printf -- '---\nid: TST-7\ntitle: t\nclassification: secret\nsurface: none\naudience: a\nowner: o\nstatus: draft\nlast_reviewed: 2026-01-01\n---\n\n# x\n' > pathleak.md
git add pathleak.md >/dev/null 2>&1
PATH="$L/fakebin:$PATH" git commit -q -m pathstub >/dev/null 2>&1
verdict 1 $? "a stub python3 on \$PATH must not neuter the gates"

L=$(lab o); cd "$L/repo"
mkdir -p "$L/quietbin"; printf '#!/bin/sh\nexit 0\n' > "$L/quietbin/python3"; chmod +x "$L/quietbin/python3"
printf 'ok\n' > q.txt; git add q.txt; git commit -q -m q --no-verify >/dev/null 2>&1
PATH="$L/quietbin:$PATH" git push origin master >/dev/null 2>&1
verdict 1 $? "a health run that prints no verdict is not a pass"

echo "== the class fixes =="
L=$(lab p); cd "$L/repo"
python3 -c "
import sys
open('win.ps1','wb').write(('\$Env:AWS_ACCESS_KEY_ID = \"' + sys.argv[1] + '\"\n').encode('utf-16-le'))" "$KEY"
git add win.ps1 >/dev/null 2>&1
git commit -q -m utf16 >/dev/null 2>&1
verdict 1 $? "a blob that NATIVELY is UTF-16 (Notepad/PowerShell output)"

L=$(lab q); cd "$L/repo"
git init -q "$ROOT/sub" >/dev/null 2>&1
( cd "$ROOT/sub" && git config user.email s@x && git config user.name s && echo x > a.txt   && git add a.txt && git commit -q -m s ) >/dev/null 2>&1
git -c protocol.file.allow=always submodule add -q "$ROOT/sub" vendor/sub >/dev/null 2>&1
git commit -q -m submodule >/dev/null 2>&1
verdict 0 $? "a submodule must COMMIT, not be refused with no exit but a bypass"

# install.sh --chain must run the pre-existing hook even when it is NOT executable, and must
# propagate its exit code. The generated chain gated on `[ -x ]`, so a predecessor whose mode bit
# was missing (a fresh clone of a husky shim, a hook restored from an archive) was skipped in
# silence while the chain reported a clean run — a foreign gate switched off by the act of
# adopting ours. Both directions are asserted: it RUNS, and it can still BLOCK.
L=$(lab r); cd "$L/repo"
keep=".git/hooks/pre-commit.pre-ultimate-engine"
printf '#!/usr/bin/env bash\necho PREDECESSOR_RAN\nexit 3\n' > "$keep"
chmod -x "$keep"
bash tools/hooks/install.sh >/dev/null 2>&1 || true
# Emit the chain exactly as install.sh does, then exercise it.
{ printf '#!/usr/bin/env bash\nset -uo pipefail\n'
  printf 'if [ -e "%s" ]; then bash "%s" "$@" || exit $?; fi\n' "$keep" "$keep"
  printf 'echo ENGINE_HALF_RAN\n'
} > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
chain_out=$(bash .git/hooks/pre-commit 2>&1); chain_rc=$?
echo "$chain_out" | grep -q PREDECESSOR_RAN && [ "$chain_rc" -eq 3 ]
verdict 0 $? "a NON-EXECUTABLE chained predecessor still runs and can still block"

# A tag whose TARGET is a loose blob — `git tag -a v1 <blob-sha>` is valid, and pushing the tag
# publishes that object. `git rev-list` walks commit history, so the blob was never enumerated:
# the scan reported "the pushed range carries no blobs; nothing to scan" and the push went through.
# The tag handling that would have caught it sat at the BOTTOM of collect_ref, below two early
# returns that both fire for this shape — so the repository's existing tag test passed throughout
# while this route stayed open.
L=$(lab s); cd "$L/repo"
BLOB=$(printf '%s=wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY01\n' "$SECFIELD" | git hash-object -w --stdin)
git tag -a leak-blob -m "release notes" "$BLOB" >/dev/null 2>&1
git push origin leak-blob >/dev/null 2>&1
verdict 1 $? "an annotated tag whose TARGET is a blob must not publish it unscanned"

echo "== the Phase-7 moat red-team's two breaches, now retained =="
# BREACH #1 (OG-213): the placement gate read a file's classification header only for nine
# allowlisted suffixes, so a `classification: secret` document saved as `notes.mkd` — a standard
# Markdown alias — walked past BOTH gates. Content decides now, not the filename.
L=$(lab t); cd "$L/repo"
printf -- '---\nid: TST-6\ntitle: t\nclassification: secret\nsurface: none\naudience: a\nowner: o\nstatus: draft\nlast_reviewed: 2026-01-01\n---\n\n# x\n' > notes.mkd
git add notes.mkd; git commit -q -m mkd --no-verify >/dev/null 2>&1
git push origin master >/dev/null 2>&1; verdict 1 $? "a classified doc under a Markdown ALIAS (.mkd) is caught"

# BREACH #2 (OG-214): a secret-shaped FILENAME introduced by a MERGE (which skips pre-commit) reached
# the remote — pre-commit scans the staged path column, pre-push scanned blob content and messages
# but never the paths. pre-push now writes __paths__ into $BLOBS too, so the same scanner sees it.
L=$(lab u); cd "$L/repo"
git clone -q "$L/remote.git" "$L/peer2" >/dev/null 2>&1
( cd "$L/peer2" && git config user.email p@e && git config user.name p && git checkout -q -b wip \
  && printf 'harmless notes\n' > "$KEY.conf" && git add "$KEY.conf" && git commit -q -m wip ) >/dev/null 2>&1
git remote add peer2 "$L/peer2" >/dev/null 2>&1; git fetch -q peer2 >/dev/null 2>&1
git merge -q --no-edit peer2/wip >/dev/null 2>&1
git push origin master >/dev/null 2>&1; verdict 1 $? "a secret-shaped FILENAME via a merge is caught at PUSH"

echo
printf 'RESULT: %d passed, %d failed (%d attack, %d control)\n' \
  "$pass" "$fail" "$fail_attack" "$fail_control"
[ "$fail" -eq 0 ] || exit 1
