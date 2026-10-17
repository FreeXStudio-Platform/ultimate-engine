"""The artifact index — what this project has produced, and whether each piece still resolves.

``PROJECT_INDEX.json`` is the register; :mod:`tools.project_index.index` reads and writes it,
:mod:`tools.project_index.cli` is the command surface (``python3 -m tools.project_index.cli``), and
:mod:`tools.project_index.dashboard` renders it as a browsable page.

Distinct from ``blueprint/``, which maps the CODE. This maps the OUTPUT: registered documents,
galleries and reports, each with the path it should still be reachable at — so a deliverable that
was moved or deleted is a finding rather than a discovery six months later.
"""
