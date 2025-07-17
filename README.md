 # kubelingo

[![Kubelingo CI](https://github.com/YOUR_USERNAME/kubelingo/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/kubelingo/actions/workflows/ci.yml)

kubelingo is a modular CLI package for mastering `kubectl` commands, Kubernetes YAML editing, and cloud-backed EKS exercises.

## Features

- **Command Quiz Mode**: Categorized kubectl questions with randomized order
- **YAML Editing Mode**: Interactive Vim-based YAML editing with semantic validation
- **Vim Commands Quiz**: Master essential Vim commands for YAML editing
- **CKAD Exam Prep**: Extensive exercises covering all CKAD exam topics
- **Semantic Validation**: YAML answers graded by meaning, not text matching
- **Performance Tracking**: Session history and progress statistics
- **LLM Integration**: Optional detailed explanations (requires OpenAI API key)

## YAML Editing Mode

Practice real-world Kubernetes scenarios by editing YAML manifests in Vim with intelligent validation:

```bash
# Run interactive YAML editing exercises
kubelingo --yaml-exercises

# Set your preferred editor (default: vim)
export EDITOR=nano  # or vim, emacs, etc.
kubelingo --yaml-exercises
```

### How YAML Editing Works

1. **Template Provided**: Start with a skeleton YAML file containing TODO comments
2. **Edit in Your Editor**: File opens in Vim (or your preferred `$EDITOR`)
3. **Semantic Validation**: Your YAML is validated by meaning, not exact text match
4. **Immediate Feedback**: Get specific error messages and hints for corrections
5. **Multiple Attempts**: Up to 3 tries per question with helpful guidance

### Validation Features

- **Syntax Checking**: Catches YAML parsing errors with line numbers
- **Semantic Comparison**: Compares parsed objects, not raw text
- **Field Validation**: Checks required Kubernetes fields (apiVersion, kind, metadata)
- **Smart Hints**: Specific guidance on what's missing or incorrect
- **Flexible Grading**: Different key orders, spacing, and styles all accepted


## Usage Examples

```bash
# List available categories
python3 -m kubelingo.cli --list-categories

# Standard kubectl command quiz
python3 -m kubelingo.cli -n 10 -c "Pod Management"

# Interactive YAML editing exercises (alias: --yaml-edit)
python3 -m kubelingo.cli --yaml-exercises

# Vim commands practice
python3 -m kubelingo.cli --vim-quiz

# View performance history
python3 -m kubelingo.cli --history
```

See [docs/VIM_INTEGRATION.md](docs/VIM_INTEGRATION.md) for an in-depth guide on integrating Vim into the Kubelingo CLI.


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

## Requirements

- Python 3.8+
- `pip` for installing the package (`pip install -e .`)
- Vim or preferred editor (set via `$EDITOR`)
- kubectl, eksctl (for command validation and cloud exercises)
- Go and GoSandbox CLI (for cloud exercises)

## CKAD Exam Coverage

Comprehensive coverage of all CKAD exam domains:

- **Core Concepts (13%)**: Pods, ReplicaSets, Deployments
- **Configuration (18%)**: ConfigMaps, Secrets, Environment Variables  
- **Multi-Container Pods (10%)**: Sidecar, Ambassador, Adapter patterns
- **Observability (18%)**: Probes, Logging, Monitoring, Debugging
- **Pod Design (20%)**: Labels, Selectors, Annotations, Jobs, CronJobs
- **Services & Networking (13%)**: ClusterIP, NodePort, Ingress
- **State Persistence (8%)**: Volumes, PersistentVolumes, Storage Classes

## File Structure

```
. (project root)
├── kubelingo/cli.py      # Main CLI entry point (console script: kubelingo)
├── setup.py              # Packaging and installation script
├── pyproject.toml        # Project metadata and dependencies
├── requirements.txt      # Python dependencies for development
├── LICENSE               # Project license
├── MANIFEST.in           # Package manifest
├── README.md             # Project overview and usage
├── docs/                 # Documentation (Markdown files)
└── kubelingo/            # Core application package
    ├── __init__.py
    ├── cli.py            # Main CLI implementation
    ├── data/             # Bundled quiz data (JSON)
    ├── modules/          # YAML editor and related modules
    └── tools/            # Cloud integration and session management
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
