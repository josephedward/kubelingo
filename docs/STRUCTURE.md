Kubelingo Repo Structure

- Package code (source of truth)
  - `kubelingo/` — all production modules and the main CLI implementation
    - Entry point: `kubelingo.kubelingo:cli` (run via `kubelingo`)
    - `__main__.py` supports `python -m kubelingo`

- Test shims (for fast, isolated tests)
  - `cli.py` — minimal CLI used by tests to simulate menus/flows
  - `question_generator.py` — simplified generator used by tests
  - `backend_integrator.py` — simplified backend adapter used by tests
  - `k8s_manifest_generator.py` — simplified manifest generator used by tests
  - `InquirerPy/` — tiny stub exposing `inquirer` with `select()` and `text()`

Notes

- For implementing features, fix bugs, or making architectural changes,
  update modules under `kubelingo/`.
- The single application command is `kubelingo`. Do not invoke `cli.py`
  for the real app; it exists only to satisfy the test suite.

