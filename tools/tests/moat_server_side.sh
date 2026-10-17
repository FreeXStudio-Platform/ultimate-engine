#!/usr/bin/env bash
# A-7 / OG-31 — prove that a `git push --no-verify` carrying a planted secret is rejected by the
# SERVER, not by any local hook. Run against the live repo + `origin` AFTER the `moat-server-side`
# branch ruleset is active (see PROVENANCE.md's OG-31 record and `.github/workflows/secret-scan.yml`).
#
# WHICH OF OG-31'S TWO CONTROLS THIS EXERCISES — stated honestly, because the refusal below does NOT
# depend on the planted secret. OG-31 is two controls: (1) a branch ruleset that REQUIRES A PULL
# REQUEST, so a direct `--no-verify` push to `master` is refused server-side no matter what it carries;
# and (2) a required GitHub-hosted `secret-scan` (gitleaks) check that fails a PULL REQUEST containing
# a secret. This script exercises CONTROL 1 — it forces the hostile push down the one path the bypass
# flag cannot open, and a benign push would be refused identically; that is the point, since it means
# `--no-verify` can publish NOTHING to the protected branch. Control 2 is exercised separately by
# opening a PR that carries the planted secret and confirming the `secret-scan` check fails and blocks
# the merge (the closeout PR itself is that exercise). Do not read the exit-0 line as "the secret was
# detected" — read it as "the bypass flag could not reach the protected branch at all".
#
#   exit 0 = the hostile --no-verify push was correctly REFUSED by the require-PR repository rule (control 1 holds).
#   exit 1 = BREACH (the push was accepted) OR the refusal was not a server-rule refusal (inconclusive).
#   exit 2 = could not set up the demonstration (no gh, no origin, or no active require-PR ruleset with an empty bypass list).
#
# This deliberately uses `--no-verify`, the one sanctioned use of the bypass flag (HANDOFF.md standing
# rule 17): every local hook is skipped so that the ONLY thing that can refuse the push is the server.
# Nothing in the working tree, the index, or any real branch is touched — the probe commit is built in
# a throwaway index via plumbing — and the planted secret never reaches `origin`, because the ruleset
# rejects the push in pre-receive and git discards the quarantined objects.
#
# FALSIFY IT: disable the ruleset (`gh api -X PUT repos/<owner>/<repo>/rulesets/<id> -f enforcement=disabled`)
# and re-run — the push then lands on the throwaway ref and this script reports BREACH. Re-enable it.
# Do NOT force-push and do NOT leave the ruleset disabled.
set -uo pipefail

REMOTE="${1:-origin}"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not a git repository"; exit 2; }
cd "$REPO_ROOT" || exit 2

# 1. The ruleset must be ACTIVE, require a pull request on the default branch, and have NO bypass
#    actor — a bypassing admin is the identity running this, which would let the hostile push SUCCEED,
#    so an EMPTY bypass list is part of what makes the refusal meaningful. This is verified from the
#    ruleset DETAIL (the list endpoint omits both `bypass_actors` and `rules`), never assumed: the old
#    version checked only `enforcement == active`, so a ruleset with an admin bypass actor, or one that
#    enforced something OTHER than require-PR, would have passed this precondition silently.
OWNER_REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)" \
  || { echo "gh not authenticated / no repo — cannot verify the server-side moat"; exit 2; }
RULESET_STATE="$(gh api "repos/$OWNER_REPO/rulesets" 2>/dev/null \
  | OWNER_REPO="$OWNER_REPO" python3 -c '
import json, os, subprocess, sys
owner_repo = os.environ["OWNER_REPO"]
try:
    rs = json.load(sys.stdin)
except (ValueError, json.JSONDecodeError):
    print("NONE"); sys.exit()
problems = []
for r in rs:
    if r.get("enforcement") != "active":
        continue
    rid = r.get("id")
    try:
        detail = json.loads(subprocess.run(
            ["gh", "api", f"repos/{owner_repo}/rulesets/{rid}"],
            capture_output=True, text=True, timeout=30, check=True).stdout)
    except Exception:  # noqa: BLE001 — cannot read the detail = cannot verify = fail closed
        problems.append(f"ruleset {rid}: detail unreadable"); continue
    rules = {rule.get("type") for rule in detail.get("rules", [])}
    bypass = detail.get("bypass_actors") or []
    if "pull_request" not in rules:
        problems.append(f"ruleset {rid}: active but does not require a pull request"); continue
    if bypass:
        problems.append(f"ruleset {rid}: requires a PR but has {len(bypass)} bypass actor(s)"); continue
    print("OK"); sys.exit()
print("PROBLEM: " + "; ".join(problems) if problems else "NONE")
' 2>/dev/null)" || RULESET_STATE="NONE"
if [ "$RULESET_STATE" != "OK" ]; then
  echo "⛔ no ACTIVE require-PR ruleset with an empty bypass list on $OWNER_REPO — the server-side"
  echo "   moat is not deployed as required, so a --no-verify push refusal would not be meaningful."
  echo "   detail: ${RULESET_STATE}"
  exit 2
fi

# 2. Build the probe commit in a THROWAWAY index, so the working tree and the real index never move.
PLANT="AKIA""IOSFODNN7EXAMPLE"     # AWS's own documented example key — pattern-matching but inert.
TMP_INDEX="$(mktemp)"
cleanup() { rm -f "$TMP_INDEX"; }
trap cleanup EXIT
BLOB="$(printf 'AWS_ACCESS_KEY_ID=%s\n' "$PLANT" | git hash-object -w --stdin)" || { echo "hash-object failed"; exit 2; }
GIT_INDEX_FILE="$TMP_INDEX" git read-tree HEAD || { echo "read-tree failed"; exit 2; }
GIT_INDEX_FILE="$TMP_INDEX" git update-index --add --cacheinfo 100644,"$BLOB",p7-hostile-leak.env \
  || { echo "update-index failed"; exit 2; }
TREE="$(GIT_INDEX_FILE="$TMP_INDEX" git write-tree)" || { echo "write-tree failed"; exit 2; }
PROBE_SHA="$(git -c user.email=probe@example -c user.name=probe commit-tree "$TREE" -p HEAD \
  -m 'PROBE: planted secret that must never land (OG-31 demonstration)')" || { echo "commit-tree failed"; exit 2; }

# 3. The hostile act: push the probe to the protected branch with EVERY local hook skipped.
echo "pushing a planted secret to $REMOTE:master with --no-verify (local hooks skipped)…"
OUT="$(git push --no-verify "$REMOTE" "$PROBE_SHA:refs/heads/master" 2>&1)"; RC=$?
echo "$OUT" | sed 's/^/    /'

# 4. Adjudicate. Non-zero alone is not proof — auth or non-fast-forward also exit non-zero. The
#    refusal must name a REPOSITORY RULE: the ruleset speaks in GH013 / "Repository rule violations" /
#    "Changes must be made through a pull request" / "protected branch", printed after "[remote rejected]".
if [ "$RC" -eq 0 ]; then
  echo "⛔ BREACH — the hostile push was ACCEPTED. A secret reached the remote via --no-verify."
  # Best-effort: undo the ref move we should never have achieved. (Never force-push in the standing path.)
  exit 1
fi
if printf '%s' "$OUT" | grep -qiE 'repository rule|Changes must be made through a pull request|protected branch|GH013'; then
  echo "✅ REFUSED by the require-PR repository rule on the server — NOT by a local hook (--no-verify skipped them)."
  echo "   OG-31 control 1 holds: the bypass flag cannot publish ANYTHING to the protected branch, secret or not."
  echo "   (Control 2 — the secret-scan check failing a PR that carries a secret — is exercised via a pull request, not here.)"
  exit 0
fi
echo "⛔ the push failed, but not with a repository-rule rejection (network, auth, or non-fast-forward?)."
echo "   Inconclusive — re-run with the branch up to date against origin/master."
exit 1
