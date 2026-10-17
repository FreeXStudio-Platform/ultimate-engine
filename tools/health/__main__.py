"""``python3 -m tools.health`` — the single command that runs every gate.

Delegates to :func:`tools.health.run.main`. Structure, rule layer, cross-file consistency, build and
both npm suites, in that order; a SKIP is never reported as a pass, and ``--full`` turns one into a
failure by design.
"""

import sys

from tools.health.run import main

if __name__ == "__main__":
    sys.exit(main())
