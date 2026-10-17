#!/usr/bin/env bash
# Install the engine's git hooks into .git/hooks/. Idempotent; safe to re-run after every pull.
#
#   bash tools/hooks/install.sh          # install / refresh
#   bash tools/hooks/install.sh --force  # overwrite a foreign hook that is already there
#
# .git/hooks/ is not version-controlled, so a hook cannot ship with a clone — it has to be
# installed once per checkout. That is exactly why OG-10 stayed open: the moat existed as a file
# nobody copied. `python3 -m tools.health` (STRUCT-03) now FAILS when the hook is missing or has
# drifted from this source, so an inert moat is loud instead of invisible.
set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)" || exit 1
cd "$REPO_ROOT" || exit 1

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1
CHAIN=0
[ "${1:-}" = "--chain" ] && CHAIN=1

HOOK_DIR="$(git rev-parse --git-path hooks)"
mkdir -p "$HOOK_DIR"
STATUS=0

for name in pre-push pre-commit; do
  src="tools/hooks/$name"
  dst="$HOOK_DIR/$name"
  if [ ! -f "$src" ]; then
    echo "⛔ install: missing source hook $src" >&2
    STATUS=1
    continue
  fi
  if [ -e "$dst" ] && ! cmp -s "$src" "$dst"; then
    # Never clobber someone else's hook silently — a multi-hook runner is a legitimate setup.
    if ! grep -q 'ULTIMATE-ENGINE-' "$dst" && [ "$FORCE" -eq 0 ] && [ "$CHAIN" -eq 0 ]; then
      echo "⛔ install: $dst exists and is NOT this engine's hook." >&2
      echo "   A project already using husky / lefthook / pre-commit has three options:" >&2
      echo "     1. bash tools/hooks/install.sh --chain   # keep theirs, run ours after it" >&2
      echo "     2. bash tools/hooks/install.sh --force   # replace theirs" >&2
      echo "     3. add this line to your existing $name runner:" >&2
      echo "          \"\$(git rev-parse --show-toplevel)/$src\" \"\$@\"" >&2
      STATUS=1
      continue
    fi
  fi
  if [ "$CHAIN" -eq 1 ] && [ -e "$dst" ] && ! grep -q 'ULTIMATE-ENGINE-' "$dst"; then
    # Preserve the existing runner and invoke ours after it. Chaining rather than clobbering is the
    # difference between a project adopting this moat and going without one: a multi-hook runner is
    # a legitimate setup, and "replace theirs or do without" is a false choice.
    keep="$dst.pre-ultimate-engine"
    [ -e "$keep" ] || mv "$dst" "$keep"
    {
      printf '#!/usr/bin/env bash\n'
      printf '# ULTIMATE-ENGINE-CHAIN — runs the pre-existing hook, then this engine'"'"'s.\n'
      printf 'set -uo pipefail\n'
      printf 'ROOT="$(git rev-parse --show-toplevel)"\n'
      # Run the predecessor through `bash`, gated on EXISTENCE, not on the execute bit. The test
      # here used to be `[ -x "$keep" ]`, which silently SKIPPED a non-executable predecessor and
      # then reported a clean chain — so a project whose existing hook arrived without its mode bit
      # (a fresh clone of a husky shim, a hook restored from an archive) got a chain that ran only
      # our half while announcing it had run both. That is the same fail-open the comment below
      # already warned about, two lines above the line that caused it.
      printf 'if [ -e "%s" ]; then bash "%s" "$@" || exit $?; fi\n' "$keep" "$keep"
      # `bash <path>` rather than exec-ing directly: the chained script must work regardless of the
      # source file's mode, and a chain that silently dies on "Permission denied" after the foreign
      # hook has already passed would look exactly like a clean run.
      printf 'exec bash "$ROOT/%s" "$@"\n' "$src"
    } > "$dst"
    chmod +x "$dst"
    echo "✅ chained $dst (existing hook preserved at $keep)"
    continue
  fi
  cp "$src" "$dst" && chmod +x "$dst" || { echo "⛔ install: could not write $dst" >&2; STATUS=1; continue; }
  if cmp -s "$src" "$dst" && [ -x "$dst" ]; then
    echo "✅ installed $dst (byte-identical to $src)"
  else
    echo "⛔ install: $dst did not verify after copy" >&2
    STATUS=1
  fi
done

exit "$STATUS"
