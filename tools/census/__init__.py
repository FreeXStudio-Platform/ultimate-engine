"""Project census — measure a project's documentation system from its own git tree, and draw it.

Answers, with counts and the rule that produced each count: how many documents does the project hold; how many were touched
recently and how many were not; how many are crossed out (archived, marked superseded or retired, or deleted from the tree);
how many carry a source-of-truth stamp, whether each stamp still holds, and whether the rest of the documents actually cite
them; what is covered and what is not. It also reads a Python source tree into a module hierarchy for the explorer figure.

The measurement (``measure``) is plain data and deterministic for a given commit and reference date. The report (``report``)
turns it into a document built by ``tools.docgen`` with a varied set of figures. A project describes its own conventions in a
profile (``profile``); nothing here knows any project's name.

Stdlib only; reads git, writes only where it is told.
"""
