"""The draft gate — run the corpus guards on a candidate BEFORE it enters the corpus.

See `docs/process/RULES.md` Rule 3 for the measurement that produced this.
"""

from tools import gitenv

# The gate commits a baseline in a temporary repository; an inherited GIT_DIR would commit it to the real one (OG-291).
gitenv.scrub()
