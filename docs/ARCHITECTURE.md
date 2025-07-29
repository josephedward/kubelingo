# Architecture Overview

This document outlines the high-level structure and organization of the Kubelingo codebase, which uses a hybrid Python/Rust architecture.

## Directory Structure

```
.
├── Cargo.toml            # Rust dependencies and workspace configuration
├── pyproject.toml        # Python package metadata and build configuration (PEP 621)
├── kubelingo/            # Core Python application package
│   ├── __init__.py
│   ├── cli.py            # Main CLI entrypoint (argparse, interactive menus)
│   ├── bridge.py         # Python-Rust bridge for invoking Rust binary
│   ├── sandbox.py        # PTY and Docker sandbox launchers
│   ├── constants.py      # Centralized constants (paths, etc.)
│   ├── utils/            # Shared utility functions
│   │   ├── __init__.py
│   │   └── ui.py         # UI helpers (colors, banners)
│   └── modules/          # Pluggable modules for different study topics
│       ├── base/         # Base classes for sessions and loaders
│       ├── kubernetes/   # Kubernetes-specific quizzes and exercises
│       │   ├── session.py
│       │   └── vim_yaml_editor.py
│       ├── custom/       # Module for user-provided quizzes
│       └── llm/          # Module for LLM integration
├── question-data/        # Quiz data in various formats
│   ├── json/
│   ├── yaml/
│   └── md/
├── src/                  # Rust source code for performance-critical components
│   ├── main.rs           # Rust CLI entrypoint
│   ├── cli.rs            # clap-based CLI definition
│   └── lib.rs            # PyO3 module for Python interop (validation functions)
├── tests/                # Pytest unit and integration tests
├── scripts/              # Helper scripts for data management
└── docs/                 # Project documentation
```

## Key Components

1.  **Python CLI (`kubelingo/cli.py`)**:
    - The main user-facing entrypoint.
    - Uses `argparse` for command-line argument parsing.
    - Uses `questionary` to provide interactive menus for quiz and mode selection.
    - Delegates to the appropriate `StudySession` module to run exercises.

2.  **Modular Sessions (`kubelingo/modules/`)**:
    - Each sub-directory represents a "study module" (e.g., `kubernetes`, `custom`).
    - The `StudySession` class in `base/session.py` defines the interface for a quiz session (`initialize`, `run_exercises`, `cleanup`).
    - `kubernetes/session.py` implements the logic for command quizzes, YAML exercises, and live cluster interactions.

3.  **Rust Core (`src/`)**:
    - A compiled Rust binary provides performance-critical features.
    - **Native Functions (`src/lib.rs`)**: Functions like `validate_yaml_structure` are exposed to Python via a `PyO3` native extension for speed.
    - **PTY Shell (`src/cli.rs`, `src/main.rs`)**: Provides a robust, cross-platform PTY shell implementation, which is more reliable than Python's `pty.spawn`. This is invoked from Python via the bridge.

4.  **Python-Rust Bridge (`kubelingo/bridge.py`)**:
    - A simple layer responsible for finding the compiled Rust binary (`kubelingo` or `kubelingo-rust`).
    - Provides Python functions (`run_pty_shell`) that execute the Rust binary as a subprocess. This avoids `PyO3` complexity for features that don't need shared memory.

5.  **Sandboxes (`kubelingo/sandbox.py`)**:
    - Provides isolated environments for exercises.
    - Prioritizes the Rust PTY shell via the `bridge`, with a fallback to Python's `pty` module.
    - Manages building and launching a Docker container for a fully isolated environment.

6.  **Centralized Configuration (`kubelingo/constants.py`, `kubelingo/utils/`)**:
    - `constants.py`: A single source of truth for file paths, avoiding duplication.
    - `utils/ui.py`: Shared UI elements like `colorama` setup and helper functions.

## Data Flow for a Kubernetes Quiz

1.  User runs `kubelingo`.
2.  `kubelingo.cli.main` displays an interactive menu.
3.  User selects "K8s" quiz.
4.  `cli.py` loads the `kubernetes` module's `NewSession`.
5.  `kubernetes.session.run_exercises` is called.
6.  It loads questions from a JSON file specified in `kubelingo.constants`.
7.  The user is prompted with a question. If it's a live exercise, `kubelingo.sandbox.spawn_pty_shell` is called.
8.  `sandbox.py` calls `kubelingo.bridge.run_pty_shell`.
9.  `bridge.py` executes the Rust binary with the `pty` command.
10. The Rust process spawns a `bash` shell in a PTY.
11. After the user exits the shell, control returns to the Python script for validation.
