"""Pytest configuration to ensure local modules are importable.

Adds the `kubelingo/` package directory and repository root to sys.path so
tests can `import cli`, `import question_generator`, etc., without editing
test files or requiring PYTHONPATH to be set.
"""
import os
import sys

REPO_ROOT = os.path.abspath(os.path.dirname(__file__))

# Ensure the repository root is on sys.path so the installed-style
# package import `import kubelingo` resolves to the package directory.
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Provide a compatibility alias so tests that do `import cli` resolve to
# the packaged test shim `kubelingo.cli_shim` without needing PYTHONPATH tweaks.
try:
    import kubelingo.cli_shim as _cli
    sys.modules.setdefault('cli', _cli)
except Exception:
    pass
