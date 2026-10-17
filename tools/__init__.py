"""The engine's namespace package — every tool in this repository lives under ``tools.``.

Deliberately empty of code. It is a namespace, not a module: putting anything importable here would
make every entry point pay for it at startup, and would give the dependency graph a root that
everything depends on and nothing describes.

**Why it has a docstring at all.** Phase 5's depth ladder measured this file at rung 0 (`sketch`)
because it said nothing about itself, and that reading held the whole `lib` container at depth 0.
The honest fix is not to add code — it is to say what the file is for, which is exactly what rung 1
asks. `OG-198`.
"""
