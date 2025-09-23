# Kubelingo: Strengths and Current Approach

## Overview
Kubelingo is a CLI study companion for the CKAD exam. It blends hands-on Kubernetes practice (kubectl commands and YAML manifests) with sensible validation, performance tracking, and optional AI assistance, while remaining useful entirely offline.

## Major Strengths
- Practical, exam-aligned workflow: Prompts cover core CKAD domains with both command- and manifest-based tasks that mirror real test actions.
- Dual-mode answering: Accepts either imperative kubectl commands or full manifests, validating both fairly.
- Robust validation pipeline: Structural manifest equivalence, tool-based checks (yamllint, kubeconform, kubectl dry-run, kube-score, Trivy), and optional LLM feedback.
- Thoughtful grading model: Ignores non-essential differences (names, field order) and focuses on functional correctness.
- Solid question model: Topic-scoped YAML with standardized fields, clear suggestions, and a doc/source-first mindset.
- Source hygiene: Utilities to audit, check, and assign reputable documentation links; interactive and bulk workflows included.
- Productive UX: Colored diffs, YAML syntax highlighting, vim-based editing flow, and normalization of kubectl commands and aliases.
- Learning loop: Tracks correct questions per topic, supports retries, back/next navigation, and quick performance snapshots.
- Extensible design: Clear module boundaries (questions, validation, generation, study session, sources, utils), .env-based configuration, pluggable LLM providers.
- Offline-first: Works without network or LLMs; gracefully degrades features while preserving core practice and validation.

## Current Approach
- Session flow
  - Topic selection → randomized questions → per-question loop with retry/back/next.
  - Command questions: capture user input; dry-run to YAML when possible; compare/grade.
  - Manifest questions: open starter buffer in vim; compare against canonical solution; show color diff and feedback.

- Validation strategy
  - Functional equivalence: Normalize solution and user manifests (remove non-essential fields, sort lists) and compare.
  - Tooling gates (configurable levels):
    - Permissive: yamllint.
    - Moderate: + kubeconform (schema).
    - Strict: + kubectl server/client dry-run, kube-score, and Trivy security scan.
  - AI assist (optional): Gemini/OpenAI/OpenRouter used to judge edge cases and provide concise feedback.

- Question content
  - Curated YAML banks per topic in `questions/*.yaml` with consistent schema.
  - Deterministic programmatic generator for common kinds (Pod, Deployment, Service, PVC, ConfigMap, Secret, Job) with both command and manifest suggestions.
  - Source-first posture: Prefers official Kubernetes docs; helper flows to audit and fill missing sources.

- Performance tracking
  - Persists per-topic correctness in `user_data/performance.yaml`.
  - Retry queue for missed items; progress indicators; backup utility for performance data.

- Tooling and ergonomics
  - Alias expansion and flag normalization for fair command comparison.
  - Colorized diffs and YAML highlighting to accelerate learning.
  - Minimal dependencies for core use; optional extras detected and used when available.

## Why This Works Well for CKAD
- Emphasizes doing over reading, matching the time-pressured, CLI-heavy CKAD format.
- Validates correctness the way Kubernetes does (apply/dry-run and schema), not by exact text matches.
- Encourages muscle memory with vim/YAML editing and kubectl command fluency.
- Keeps users grounded in official documentation via required or auto-assigned sources.

## Notable Extensibility Hooks
- LLM provider abstraction via `.env` (`KUBELINGO_LLM_PROVIDER`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`).
- Pluggable validation levels and tool flags through environment config.
- Modular generators and source management utilities for future topic expansion.

## Tools & Value
- kubectl
  - Value: Client/server dry-run to validate manifests and convert commands to YAML for fair comparison; mirrors real CKAD workflows without mutating the cluster.
- yamllint
  - Value: Fast syntax checks to catch indentation and structure errors early.
- kubeconform
  - Value: Strict Kubernetes schema validation to detect invalid apiVersion/fields across resources.
- kube-score
  - Value: Best-practice linting (probes, resources, labels) to encourage production-ready manifests.
- Trivy (config scan)
  - Value: Surfaces misconfigurations and high/critical risks to improve security awareness.
- yq / jq
  - Value: Lightweight YAML/JSON manipulation for question preparation and transformations in generator workflows.
- Jsonnet (scripts)
  - Value: Parametric question/manifest generation for repeatable, complex scenarios.
- googlesearch (optional)
  - Value: Auto-finds reputable documentation links to fill missing `source` fields for question hygiene.
- thefuzz
  - Value: Fuzzy matching to map consolidated source data to local questions during bulk source assignment.
- vim (or $EDITOR)
  - Value: Familiar, fast manifest authoring matching real exam ergonomics.
- Pygments + Colorama
  - Value: Colorized diffs and YAML syntax highlighting for higher signal during review.
- python-dotenv
  - Value: Simple, file-based configuration for LLM provider and validation levels without code changes.

## Known Limitations and Next Steps
- LLM-dependent flows are disabled without API keys; messages inform but cannot replace deterministic checks.
- Source auto-assignment depends on `googlesearch` and network access; falls back gracefully.
- Advanced adaptivity (difficulty scaling, conceptual clustering) is on the roadmap but not yet active.

See also: `docs/usage.md`, `docs/roadmap.md`, and `docs/shared_context.md`.
