#!/usr/bin/env bash
# graphify interactive system graphs — build + open as an app window. MANUAL, local-only, no VPS.
#  App-window launch (below) tries the browser candidate paths from engine.config.json's
#  "browsers" section (via a small Node helper — see tools/lib/print-browser-path.mjs) — falls
#  back to the OS `open`/`xdg-open` command, then to just printing the URL if neither works.
#   bash tools/graphify/open.sh            # structure graph (where things live)
#   bash tools/graphify/open.sh deps       # dependency graph (what depends on what / risky core)
#   bash tools/graphify/open.sh pipeline   # curated stage-flow diagram
#   bash tools/graphify/open.sh coverage   # detectors ↔ SWC classes ↔ tags
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
cd "$ROOT"
G="${1:-graph}"   # graph (default) | deps | pipeline | coverage
case "$G" in
  graph)    node tools/graphify/build.mjs ;;
  deps)     node tools/graphify/build-deps.mjs ;;
  pipeline) node tools/graphify/build-pipeline.mjs ;;
  coverage) node tools/graphify/build-coverage.mjs ;;
  *) echo "unknown graph '$G' (use: graph | deps | pipeline | coverage)"; exit 1 ;;
esac

# graph-view.html reads its ?g= query via a script-injected fetch, which browsers block under the
# file:// origin's security model — must be served over http(s)://. Prefer the configured python
# (engine.config.json's tools.python) so this works even if bare `python3` isn't on PATH.
PYBIN="$(node "$HERE/../lib/print-tool-path.mjs" python 2>/dev/null || echo python3)"
PORT=8934
( "$PYBIN" -m http.server "$PORT" --directory "$ROOT" >/dev/null 2>&1 & echo $! > "$HERE/.open-server.pid" )
sleep 0.4
F="http://localhost:$PORT/tools/graphify/graph-view.html?g=$G"

# launch the browser binary directly with --app + a dedicated profile -> a REAL standalone app window
CHROME="$(node "$HERE/../lib/print-browser-path.mjs" chrome 2>/dev/null || true)"
EDGE="$(node "$HERE/../lib/print-browser-path.mjs" edge 2>/dev/null || true)"
PROFILE="$HOME/.cache/graphify-graph-window"
if [ -n "$CHROME" ] && [ -x "$CHROME" ]; then
  "$CHROME" --app="$F" --user-data-dir="$PROFILE" --window-size=1320,900 --no-first-run --no-default-browser-check >/dev/null 2>&1 &
elif [ -n "$EDGE" ] && [ -x "$EDGE" ]; then
  "$EDGE" --app="$F" --user-data-dir="$PROFILE" --window-size=1320,900 >/dev/null 2>&1 &
elif command -v open >/dev/null 2>&1; then
  open "$F" 2>/dev/null || echo "open $F"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$F" 2>/dev/null || echo "open $F"
else
  echo "open $F"
fi
echo "graph → $F   (local static server on :$PORT; re-run to refresh; fully offline — no CDN, both 2D and 3D libs are vendored)"
echo "stop the server when done: kill \$(cat $HERE/.open-server.pid)"
