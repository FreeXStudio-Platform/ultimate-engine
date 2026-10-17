"""``python3 -m tools.draft`` — the package's executable entry point.

Delegates to :func:`tools.draft.cli.main`, which splices a candidate document into a throwaway copy
of the working tree and reports the DIFFERENCE it would introduce — including findings that land on
other documents because this one moved a fact they state.
"""

from tools.draft.cli import main

raise SystemExit(main())
