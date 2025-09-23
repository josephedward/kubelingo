Kubelingo Repo Structure

- Package code (source of truth)
  - `kubelingo/` — all production modules and the main CLI implementation
    - Entry point: `kubelingo.kubelingo:cli` (run via `kubelingo`)
    - `__main__.py` supports `python -m kubelingo`

- Test shims (for fast, isolated tests)
  - `kubelingo/cli_shim.py` — minimal CLI used by tests to simulate menus/flows
  - All former top-level shims have been removed to avoid duplication.
  - `InquirerPy/` — tiny stub exposing `inquirer` with `select()` and `text()`

Notes

- For implementing features, fix bugs, or making architectural changes,
  update modules under `kubelingo/`.
- The single application command is `kubelingo`. The test CLI surface is
  `kubelingo.cli_shim` and is not used by the real app.
