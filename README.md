 # kubelingo

[![Kubelingo CI](https://github.com/josephedward/kubelingo/actions/workflows/ci.yml/badge.svg)](https://github.com/josephedward/kubelingo/actions/workflows/ci.yml)

kubelingo is a modular CLI package for mastering `kubectl` commands, Kubernetes YAML editing, and cloud-backed EKS exercises.

## Features

- **Command Quiz Mode**: Categorized kubectl questions with randomized order
- **YAML Editing Mode**: Interactive Vim-based YAML editing with semantic validation
- **Vim Commands Quiz**: Master essential Vim commands for YAML editing.
- **CKAD Exam Prep**: Extensive exercises covering all CKAD exam topics.
- **Semantic Validation**: YAML answers are graded by meaning, not just text matching.
- **Performance Tracking**: Session history and progress statistics are stored locally.
- **Sandboxed Environments**: Practice in a safe PTY shell or an isolated Docker container.
- **LLM Integration**: Get optional, detailed explanations for quiz questions (requires an OpenAI API key).

## YAML Editing Mode

Practice real-world Kubernetes scenarios by editing YAML manifests in your local editor (`$EDITOR`) with intelligent validation.

```bash
# Launch Kubelingo's interactive menu
kubelingo
```

```bash
# View your OpenAI API key
kubelingo config view openai
# Set your OpenAI API key
kubelingo config set openai YOUR_KEY_HERE
```

From the menu, navigate to `K8s (preinstalled)` -> `YAML Editing Quiz`.

### How It Works

1.  **Template Provided**: You start with a skeleton YAML file.
2.  **Edit in Your Editor**: The file automatically opens in Vim (or your configured `$EDITOR`).
3.  **Semantic Validation**: After you save and exit, your solution is validated by its semantic structure, not by an exact text match. Key order and comments don't matter.
4.  **Immediate Feedback**: Get specific error messages and hints for corrections.
5.  **Multiple Attempts**: You get multiple tries per question with helpful guidance.

### Validation Features

- **Syntax Checking**: Catches YAML parsing errors with line numbers
- **Semantic Comparison**: Compares parsed objects, not raw text
- **Field Validation**: Checks required Kubernetes fields (apiVersion, kind, metadata)
- **Smart Hints**: Specific guidance on what's missing or incorrect
- **Flexible Grading**: Different key orders, spacing, and styles all accepted


## Usage Examples

```bash
# List available categories
kubelingo --list-categories

# Launch interactive menu (recommended)
kubelingo

# Run a 10-question quiz on Pod Management (using flag)
kubelingo --k8s -n 10 -c "Pod Management"
# Or equivalently via module alias:
kubelingo k8s -n 10 -c "Pod Management"

# Run a quiz on only the questions you've flagged for review
kubelingo --k8s --review-only

# View performance history
kubelingo --history
```

```bash
# View your OpenAI API key
kubelingo config view openai
# Set your OpenAI API key
kubelingo config set openai YOUR_KEY_HERE
```

See `docs/ARCHITECTURE.md` for a high-level overview of the project structure.


## Question Types

### Standard Questions
Traditional kubectl command questions with text-based answers.

### YAML Editing Questions
Hands-on YAML editing with these fields:
- `question_type`: "yaml_edit"
- `prompt`: Task description
- `starting_yaml`: Template with TODO comments
- `correct_yaml`: Expected solution for validation
- `explanation`: Learning objectives

Example:
```json
{
  "question_type": "yaml_edit",
  "prompt": "Create a Pod named 'web-server' using nginx:1.20",
  "starting_yaml": "apiVersion: v1\nkind: Pod\nmetadata:\n  name: # TODO\n...",
  "correct_yaml": "apiVersion: v1\nkind: Pod\nmetadata:\n  name: web-server\n...",
  "explanation": "Basic pod creation exercise"
}
```

## Installation

To install `kubelingo` from PyPI, simply run:

```bash
pip install kubelingo
```

### Development Setup

If you want to contribute to the project, follow these steps to set up a development environment.

1.  Clone the repository:
    ```bash
    git clone https://github.com/josephedward/kubelingo.git
    cd kubelingo
    ```

2.  Install dependencies and build the Rust extension for development:
    ```bash
    pip install -r requirements.txt
    maturin develop
    ```
    This command compiles the Rust extension and installs `kubelingo` in editable mode.

## Releasing to PyPI

To publish a new version to PyPI, you first need to [generate an API token](https://pypi.org/help/#apitoken) from your PyPI account settings.

The recommended way to provide credentials for publishing is through environment variables. `maturin` uses `twine` for uploading, which expects the API token to be provided as the password with the username `__token__`.

```bash
# Set credentials in your shell
export TWINE_USERNAME="__token__"
export TWINE_PASSWORD="pypi-your-api-token-goes-here"

# Build and publish the package
maturin build --release
maturin publish
```

## Requirements

- Python 3.8+
- Rust toolchain (install from [rustup.rs](https://rustup.rs/))
- `pip` and `maturin`
- Vim (with `+clientserver` support for integration tests) or preferred editor (set via `$EDITOR`)
- `kubectl`, `eksctl` (for command validation and cloud exercises)
- Go and GoSandbox CLI (for cloud exercises)
  
### Container Sandbox Mode

Kubelingo can launch a Docker container to provide an isolated environment similar to the CKAD exam:

- **Isolation**: No network access (container run with `--network=none`), only the pre-installed tools (`bash`, `vim`, `kubectl`).
- **Reproducibility**: Consistent environment across machines.
- **Requirements**: Requires Docker Engine to be installed and running. (Tip: run `docker info` to verify your Docker setup.)

To enter the container sandbox, run:

```bash
kubelingo --sandbox-mode container
```

On first run, Kubelingo will build a local Docker image (`kubelingo/sandbox:latest`) from
`docker/sandbox/Dockerfile`. This requires internet access to download the base image and kubectl binary.
Subsequent runs reuse the built image.

Inside the container, your current working directory is mounted at `/workspace`, so you can run
`kubelingo` and kubectl commands against exercises as usual. Exit with `exit` or Ctrl-D.

## CKAD Exam Coverage

Comprehensive coverage of all CKAD exam domains:

- **Core Concepts (13%)**: Pods, ReplicaSets, Deployments
- **Configuration (18%)**: ConfigMaps, Secrets, Environment Variables  
- **Multi-Container Pods (10%)**: Sidecar, Ambassador, Adapter patterns
- **Observability (18%)**: Probes, Logging, Monitoring, Debugging
- **Pod Design (20%)**: Labels, Selectors, Annotations, Jobs, CronJobs
- **Services & Networking (13%)**: ClusterIP, NodePort, Ingress
- **State Persistence (8%)**: Volumes, PersistentVolumes, Storage Classes
  
For quick reference on multi-step Killercoda CKAD quiz tasks, see [Killercoda CKAD Quick Reference](docs/killercoda_ckad_cheat_sheet.md).

## File Structure

A high-level overview of the monorepo structure:

```
.
├── kubelingo/            # Core Python application package
│   ├── cli.py            # Main CLI entrypoint with argparse/questionary
│   ├── bridge.py         # Python-Rust bridge
│   ├── sandbox.py        # PTY and Docker sandbox launchers
│   ├── constants.py      # Shared file paths and constants
│   ├── utils/            # Shared utilities (e.g., UI helpers)
│   └── modules/          # Pluggable quiz modules (kubernetes, custom, etc.)
├── src/                  # Rust source code for high-performance components
│   ├── main.rs           # Rust CLI entrypoint
│   ├── cli.rs            # clap-based CLI argument parsing
│   └── lib.rs            # PyO3 native extension functions
├── question-data/        # Quiz content in JSON, YAML, and Markdown
├── tests/                # Pytest tests for Python code
└── docs/                 # Project documentation
```

## Creating Custom Questions

### Standard Questions
```json
{
  "prompt": "Create a pod named nginx",
  "response": "kubectl run nginx --image=nginx",
  "explanation": "Basic pod creation command"
}
```

### YAML Editing Questions
```json
{
  "question_type": "yaml_edit",
  "prompt": "Create a ConfigMap with database configuration",
  "starting_yaml": "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: # TODO\ndata:\n  # TODO",
  "correct_yaml": "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: db-config\ndata:\n  host: localhost\n  port: \"5432\"",
  "explanation": "ConfigMap creation with key-value data"
}
```



## License

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Scripts Consolidation

The `scripts/` directory now contains a consolidated entrypoint for common tasks, `kubelingo_tools.py`.  All other legacy helper scripts have been moved to `scripts/legacy/` and are preserved for reference but are not part of the active workflow.

Usage:
```bash
# Show available commands
python3 scripts/kubelingo_tools.py --help

# Run a specific task, for example:
python3 scripts/kubelingo_tools.py manage organize --dry-run
python3 scripts/kubelingo_tools.py ckad export --help
```

## Troubleshooting

Before running these commands, ensure you are using the local development version of Kubelingo (not an older global install):

  pip uninstall kubelingo
  pip install -e .

If you need to restore your question bank, legacy helper scripts are available in `scripts/legacy/`.

For a full restore (DB, YAML, JSON imports):
```bash
python3 scripts/legacy/restore_all.py
```

To restore only the database, YAML, or JSON parts, see:
```bash
python3 scripts/legacy/restore_db_from_backup.py   # Restore database from backup
python3 scripts/legacy/restore_all.py --step yaml  # Restore YAML question files only
python3 scripts/legacy/restore_all.py --step json  # Restore JSON question files only
```

For help with any of these commands, run:

  kubelingo --help
  
## Data Management Details

Kubelingo relies on a SQLite database seeded from legacy JSON, YAML, and Markdown question files.
For a deep-dive into how quizzes are categorized, how the database is initialized, and the migration scripts workflow,
see `shared_context.md` at the project root.
This document explains:
- Quiz categories and validation strategies
- Importing legacy JSON/YAML/MD into the database
- Database backup and restore procedures
- Duplicate question cleanup
- Unified sandbox-based execution flow
These details help contributors and maintainers understand the data pipelines and recovery steps.
