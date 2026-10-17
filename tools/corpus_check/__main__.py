"""``python3 -m tools.corpus_check`` — the package's executable entry point.

Delegates to :func:`tools.corpus_check.run.main`. The ``if __name__`` guard is what makes the module
safe to import as well as to run — the guards' own probes import this package, and a bare
``sys.exit`` at module scope would end the test process instead.
"""

import sys

from tools.corpus_check.run import main

if __name__ == "__main__":
    sys.exit(main())
