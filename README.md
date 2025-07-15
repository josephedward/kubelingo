 # kubelingo

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
python3 cli_quiz.py --yaml-edit

# Set your preferred editor (default: vim)
export EDITOR=nano  # or vim, emacs, etc.
python3 cli_quiz.py --yaml-edit
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
# Standard kubectl command quiz
python3 cli_quiz.py -n 10 -c "Pod Management"

```bash
# Interactive YAML editing exercises
python3 cli_quiz.py --yaml-exercises

```bash
# Vim commands practice
python3 cli_quiz.py --vim-quiz

```bash
# View performance history
python3 cli_quiz.py --history

# List available categories
python3 cli_quiz.py --list-categories
```

## Data Utilities
Utilities for maintaining and validating quiz data sources.
_Note: The following scripts are for legacy data management and may be deprecated in future versions._
```bash
# Install dependencies (includes PyYAML)
pip install -r requirements.txt

# Merge multiple JSON sources into a single deduplicated file
python3 scripts/merge_quiz_data.py

# Verify JSON structure and YAML syntax of quiz data
python3 scripts/verify_quiz_data.py
```

```bash
# Cloud-Specific YAML editing exercises
python3 cli_quiz.py --cloud-mode --exercises aws_cloud_exercises.json --cluster-context ckad-practice
```

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
- PyYAML (`pip install -r requirements.txt`)
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
├── cli_quiz.py           # Main CLI entrypoint
├── data/                 # Quiz data (JSON) separate from code
├── kubelingo/            # Core application package (CLI, modules, tools)
├── logs/                 # Quiz session logs & history
├── kubelingo-work/       # Runtime workspace for YAML editing
├── docs/                 # Project documentation (Markdown and API refs)
└── requirements.txt      # Python dependencies
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
