"""Retained counter-examples for the engine's own guards.

**Why this package exists.** Every guard in this engine was falsified by hand when it was written —
shown red, then restored to green — and the falsification was then thrown away. Nothing re-ran it.
So each guard decayed from *proven* to *assumed*, and four independent verification passes found
203 defects, the large majority of which were guards that no longer did what their name said.

`OG-32` recorded the structural cause: there were zero automated tests for 36+ Python modules, so
there was nowhere to PUT a counter-example. This package is that place.

**The rule these tests exist to serve:** an assertion ships with the input that makes it fail.
A falsification performed once by hand and not retained does not count — see `docs/process/RULES.md`.
"""

from tools import gitenv

# The tests run `git init` / `git commit` in scratch directories; an inherited GIT_DIR makes the scratch repository the real one (OG-291).
gitenv.scrub()
