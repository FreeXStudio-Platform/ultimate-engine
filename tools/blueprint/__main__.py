"""``python3 -m tools.blueprint`` — the package's executable entry point.

Delegates to :func:`tools.blueprint.cli.main`. The split exists so the CLI stays importable and
testable without executing anything on import, which is what lets the probes call ``main(argv)``
directly instead of shelling out for every assertion.
"""

from tools.blueprint.cli import main

raise SystemExit(main())
