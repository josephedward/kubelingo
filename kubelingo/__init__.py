"""Kubelingo package initializer.

Adds a compatibility alias so tests that do `import cli` can resolve to
`kubelingo.cli_shim` without requiring a top-level `cli.py` file. This helps
in environments where tests import `cli` directly but only the packaged
implementation exists.
"""

# Best-effort alias: if anything imports top-level `cli`, point it to our
# `kubelingo.cli_shim` module. This only works if the kubelingo package has
# already been imported in the process before `import cli` occurs.
try:  # pragma: no cover - defensive init path
    import sys as _sys
    from . import cli_shim as _cli_mod
    if 'cli' not in _sys.modules:
        _sys.modules['cli'] = _cli_mod
except Exception:
    # Safe fallback: nothing to do if aliasing fails
    pass
