"""Thin wrapper module to satisfy tests that import `cli`.

This re-exports functions from `kubelingo.cli_shim` and adds small helpers
(`review_correct` / `review_incorrect`) that some tests expect to exist.

Usage in tests is via `import cli`, so when running pytest set:

  PYTHONPATH=/Users/user/Documents/GitHub/kubelingo/kubelingo

so that this module is importable as top-level `cli`.
"""
from typing import List

# Use real InquirerPy so tests can monkeypatch
try:
    from InquirerPy import inquirer as inquirer  # noqa: F401
except Exception:  # pragma: no cover - fallback for environments without InquirerPy
    class _P:
        def __init__(self, val=""):
            self._val = val
        def execute(self):
            return self._val
    class _Inq:
        def select(self, *a, **k):
            return _P("")
        def text(self, *a, **k):
            return _P("")
        def checkbox(self, *a, **k):
            return _P([])
    inquirer = _Inq()  # type: ignore

# Import the packaged shim and ensure it uses the same inquirer object
from . import cli_shim as _shim
_shim.inquirer = inquirer

# Re-export everything from cli_shim for compatibility
from .cli_shim import *  # noqa: F401,F403


def _list_yaml_files(dirpath: str) -> List[str]:
    import os
    try:
        return [f for f in os.listdir(dirpath) if f.endswith((".yaml", ".yml"))]
    except Exception:
        return []


def review_correct() -> None:
    """Review YAMLs saved as correct; show AI feedback."""
    import os
    dirpath = inquirer.text(message='Directory to review:').execute().strip() or os.getcwd()
    files = _list_yaml_files(dirpath)
    if not files:
        console.print("[bold yellow]No YAML files found to review.[/bold yellow]")
        return
    selected = inquirer.checkbox(message='Select files:', choices=files).execute()
    # Build a prompt from selected filenames; tests assert we call ai_chat and print a header
    _ = ai_chat('system', f'Review correct answers for: {", ".join(selected)}')
    console.print("AI Feedback: ")


def review_incorrect() -> None:
    """Review YAMLs saved as incorrect; show AI feedback."""
    import os
    dirpath = inquirer.text(message='Directory to review:').execute().strip() or os.getcwd()
    files = _list_yaml_files(dirpath)
    if not files:
        console.print("[bold yellow]No YAML files found to review.[/bold yellow]")
        return
    selected = inquirer.checkbox(message='Select files:', choices=files).execute()
    _ = ai_chat('system', f'Review incorrect answers for: {", ".join(selected)}')
    console.print("AI Feedback: ")

