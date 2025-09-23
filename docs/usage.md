# Kubelingo Usage Guide

A practical, example-driven guide to install, configure, and use Kubelingo for CKAD preparation. Includes workflows for command and manifest questions, validation settings, source management, and troubleshooting.

## Prerequisites
- Python 3.8+ (3.11+ recommended)
- `kubectl` in `PATH` (any context is fine; dry-run does not mutate)
- Optional editor: `vim` (Kubelingo launches `vim` for manifest questions)
- Optional tools for strict validation: `yamllint`, `kubeconform`, `kube-score`, `trivy`
- Optional AI: API keys for Gemini/OpenAI/OpenRouter (see Configuration)

## Installation

- From PyPI
```bash
pip install kubelingo
```

- From source (editable dev install)
```bash
git clone https://github.com/josephedward/kubelingo.git
cd kubelingo
pip install -r requirements.txt
pip install -e .
```

Verify install:
```bash
kubelingo --help
```

## Configuration

Create a `.env` in the project root to control validation and optional AI providers.

- Validation level (tool chain depth)
```dotenv
# one of: permissive | moderate | strict
KUBELINGO_VALIDATION_LEVEL=moderate
```

- Per-tool toggles (True/False) — enable/disable specific validators
```dotenv
KUBELINGO_VALIDATION_YAMLLINT=True
KUBELINGO_VALIDATION_KUBECONFORM=True
KUBELINGO_VALIDATION_KUBECTL-VALIDATE=True
KUBELINGO_VALIDATION_KUBE-SCORE=True
KUBELINGO_VALIDATION_TRIVY=True
```

- LLM provider (optional)
```dotenv
# one of: gemini | openai | openrouter
KUBELINGO_LLM_PROVIDER=gemini
GEMINI_API_KEY=...
# or
# KUBELINGO_LLM_PROVIDER=openai
# OPENAI_API_KEY=...
# or
# KUBELINGO_LLM_PROVIDER=openrouter
# OPENROUTER_API_KEY=...
```

Notes:
- Kubelingo works without AI; feedback falls back to deterministic checks.
- Strict mode uses more external tools; install them or toggle to False.

## Quick Start

Launch the interactive CLI:
```bash
kubelingo
```

- Choose a topic (pods, services, deployments, etc.) and how many questions to practice.
- Topic prompt suffixes:
  - `i` = study incomplete questions
  - `g` or `s` = generate a new question (requires 100% completion + API key)
  - digits (e.g., `5`) = practice that many questions
  - Enter = practice all questions
- Post-answer menu: `[n]ext`, `[b]ack`, `[i]ssue`, `[s]ource`, `[r]etry`, `[c]onfigure`, `[q]uit`.

## Answering Questions

### Command questions (kubectl)
Prompt example:
> Create a Deployment named 'nginx-deploy' with 3 replicas of the image 'nginx:1.20'.

Valid answer (one of several possibilities):
```bash
kubectl create deployment nginx-deploy --image=nginx:1.20 --replicas=3
```

Tips:
- Aliases normalized: `k`→`kubectl`, `deploy`→`deployment`, `-n X`→`--namespace X`.
- Flags are sorted; functional correctness is what matters.
- Kubelingo may perform a dry-run and convert to YAML to compare structurally.

Submitting:
- Enter your command and press Enter.
- For multi-line input, submit an empty line or type `done`.

### Manifest questions (YAML + vim)
You will be dropped into `vim` with the prompt commented at top and space to write your manifest.

Prompt example:
> Create a Service of type NodePort named 'web-svc' that exposes port 80 targetPort 80 for Pods labeled app=web.

Minimal valid answer:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-svc
spec:
  type: NodePort
  selector:
    app: web
  ports:
    - port: 80
      targetPort: 80
```

Save and quit (`:wq`). Kubelingo will:
- Compare structurally with the canonical solution (ignoring names, order, container-name fields).
- Run configured validators (yamllint, kubeconform, etc.).
- Show a colorized diff and concise feedback.

## Validation Details

Levels (`KUBELINGO_VALIDATION_LEVEL`):
- permissive: `yamllint`
- moderate: `yamllint`, `kubeconform`
- strict: `yamllint`, `kubeconform`, `kubectl` dry-run, `kube-score`, `trivy`

Notes:
- Missing tool? It’s skipped with a note. Install to enable.
- Structural equivalence focuses on apiVersion/kind/spec correctness.
- With an LLM configured, edge cases receive brief AI feedback.

## Managing Sources (Question Hygiene)

Ensure every question includes a reputable `source` URL.

- Check for missing sources
```bash
kubelingo --check-sources
```

- Add sources in bulk from a consolidated YAML
```bash
kubelingo --add-sources --consolidated /path/to/consolidated_questions.yaml
```

- Interactively search and assign sources (optional `--auto-approve`)
```bash
kubelingo --interactive-sources
kubelingo --interactive-sources --auto-approve
```

## Data & Progress

- Location: `user_data/`
  - `performance.yaml`: per-topic list of correctly answered questions
  - `missed_questions.yaml`: optional list of flagged misses
  - `issues.yaml`: user-reported question issues

- Backup performance data
```bash
python scripts/backup_performance_yaml.py
```

## Installing Optional Tools

- macOS (Homebrew)
```bash
brew install yamllint kubeconform kube-score trivy
```

- Debian/Ubuntu
```bash
sudo apt-get update && sudo apt-get install -y yamllint
# kubeconform/kube-score/trivy: use official releases for latest binaries
```

Verify tools:
```bash
yamllint --version && kubeconform -v && kube-score version && trivy --version
kubectl version --client
```

## Troubleshooting

- kubectl not found
  - Install kubectl and ensure it’s in `PATH`. Dry-run uses your context but doesn’t mutate.
- vim not found or prefer another editor
  - Install `vim` or adjust your environment; Kubelingo currently launches `vim` directly.
- Validation tools missing
  - Install them, lower `KUBELINGO_VALIDATION_LEVEL`, or set per-tool toggles to `False`.
- No AI feedback
  - Set `KUBELINGO_LLM_PROVIDER` and the corresponding API key in `.env`.
- Source search disabled
  - The `googlesearch` library or network may be unavailable. Use `--add-sources` or add sources manually.

## Testing & Coverage (contributors)

- Run tests
```bash
pytest
```

- Coverage report
```bash
pip install pytest-cov
pytest --cov=kubelingo --cov-report=term-missing
```

## References
- CKAD Curriculum: https://github.com/cncf/curriculum/blob/master/exams/ckad/
- Kubernetes Docs: https://kubernetes.io/docs/

