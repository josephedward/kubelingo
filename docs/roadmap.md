<!-- Kubelingo Roadmap -->
# Kubelingo Project Roadmap

This document outlines the vision, features, and enhancements planned for the Kubelingo CLI quiz tool. It is organized into key focus areas and milestone ideas.

## 1. Core Quiz Functionality
- Command-based quizzes (kubectl commands, flags, resource shortcuts)
- YAML edit quizzes (load starting YAML, apply edits, compare against expected)
- Vim command quizzes (interactive Vim shortcut and command practice)
- Live Kubernetes cluster quizzes (apply/validate on a real or simulated cluster)
- Question categories, randomization, and scheduling

## 2. Sandbox & Homelab Cluster Integration
- **Cloud Sandboxes** (AWS, GCP, Azure)
  - Authentication flows (gosandbox, AWS IAM, GCP service accounts)
  - Ephemeral cluster provisioning (eksctl, kind, kops)
  - Credential exporting and isolation per quiz
  - Cleanup logic and error handling
  - Command capture and logging for scoring
- **On-Prem / Homelab Clusters**
  - Support local kind, k3s, microk8s, minikube contexts
  - Automatic context detection and kubeconfig management
  - Performance profiling differences between cloud and homelab
  - Secure access (SSH tunneling, kubeconfig distribution)
- **Cluster Provider Interface**
  - Abstract provider API (start, stop, validate, clean)
  - Plugin system for external repos to implement new providers

## 3. Validation & Scoring
- Accurate command normalization (aliases, resource shortcuts, flags)
- Exit-code based correctness and output diffs
- YAML semantic comparison (using schemas or `kubectl diff` semantics)
- Detailed feedback: diff highlights, line-by-line hints
- Explanation and review-flagging per question

## 4. Metrics & Analytics
- Real-time timing metrics (per-question and total quiz duration)
- Historical tracking of performance (correct % over time)
- Per-category and per-difficulty aggregation
- Exportable reports (JSON, CSV)
- Optional central server or dashboard integration (Grafana, Prometheus)

## 5. Customization & Difficulty Levels
- Adjustable difficulty (Easy, Medium, Hard) based on:
  - Command complexity (simple `get` vs `kubectl patch --type=json`)
  - YAML exercise depth (simple edit vs multi-resource manifests)
  - Time limits per question
- User profiles & preferences (favorite categories, skip lists)
- Custom quiz definitions and imports (local JSON files)
- Weighted randomization and adaptive question selection

## 6. UX & CLI Enhancements
- Interactive menus and filters (questionary, arrow keys)
- Enhanced ASCII art / branding / color themes
- Toggleable color output and accessibility modes
- Tab-completion and fuzzy search (fzf, readline)
- Localization / i18n support
- Progress bars and spinners for long operations

## 7. Testing & Continuous Integration
- Unit tests for core modules (question loading, scoring logic)
- Integration tests against kind or mock clusters
- E2E tests: full quiz flows, sandbox provisioning
- Pre-commit hooks: linting, formatting (black, flake8)
- CI pipeline for packaging, publishing, and coverage

## 8. Documentation & Community
- Comprehensive user guide and examples
- Quickstart tutorial for new users
- API reference for plugin authors
- Contribution guidelines, code of conduct, issue templates
- GitHub Projects/Boards to track roadmap items in issues

## 9. Future Vision & Extensions
- Web UI or TUI for richer interactive experience
- Real-time collaborative quizzes (pair mode)
- Integrations with GitHub Actions and CI pipelines
- Mobile or VSCode extension for on-the-go practice
- AI-powered question generation and hints
- Support for other CNCF projects (Helm, Prometheus, Istio)

> _This roadmap is a living document. Feel free to propose additions or reprioritize items via issues or pull requests._# KubeLingo Project Roadmap

This document outlines the planned features and improvements for KubeLingo. The roadmap is divided into several key areas, reflecting our vision for making this the best tool for learning and practicing Kubernetes skills.

## Phase 1: Core Enhancements

Focus on solidifying the core quiz experience and adding high-value features.

- **[ ] Difficulty Levels:**
    - [ ] Implement a mechanism to tag questions with difficulty levels (Beginner, Intermediate, Advanced).
    - [ ] Add a command-line flag (`--difficulty`) to let users filter questions.
    - [ ] Adjust scoring or hints based on the selected difficulty.

- **[ ] Performance Tracking & History:**
    - [ ] Enhance history tracking to include time taken per question and streaks.
    - [ ] Implement a `kubelingo history` command to show detailed performance analytics.
    - [ ] Visualize progress over time (e.g., ASCII charts in the terminal).

- **[ ] Spaced Repetition System (SRS):**
    - [ ] Integrate an SRS algorithm to prioritize questions the user has previously answered incorrectly.
    - [ ] Automatically schedule questions for review based on performance.

## Phase 2: Interactive Environments

Bridge the gap between theory and practice by integrating with live Kubernetes clusters.

- **[ ] Sandbox Integration:**
    - [ ] Finalize integration with a sandbox provider (e.g., a custom Go-based sandbox environment).
    - [ ] Develop a session manager to request, configure, and tear down ephemeral Kubernetes environments for quiz sessions.
    - [ ] Ensure `kubectl` commands are correctly routed to the sandbox cluster.

- **[ ] Homelab Integration:**
    - [ ] Add functionality to allow users to use their own homelab cluster.
    - [ ] Implement a configuration flow (`kubelingo config --use-context <my-homelab-context>`) to point KubeLingo to a user-provided kubeconfig context.
    - [ ] Add safety checks and warnings when operating on a non-ephemeral cluster.

- **[ ] Command Validation in Live Environments:**
    - [ ] Develop a robust system to capture commands run by the user within the live environment.
    - [ ] Validate the *state* of the cluster after a user's command, rather than just comparing command strings. (e.g., "Was a pod named 'nginx' actually created?").

## Phase 3: Advanced Editing and Content

Improve the YAML editing experience and expand the question library.

- **[ ] Vim Mode for YAML Editing:**
    - [ ] Integrate a terminal-based text editor with Vim keybindings for the YAML editing exercises.
    - [ ] Explore options like `pyvim` or creating a temporary file and launching the user's `$EDITOR`.

- **[ ] Real-time YAML Validation:**
    - [ ] Integrate a YAML linter (e.g., `yamllint`) and the Kubernetes OpenAPI schema.
    - [ ] Provide immediate feedback on syntax errors and invalid Kubernetes resource definitions as the user types.

- **[ ] Expanded Content & New Question Types:**
    - [ ] Add question packs for CKA and CKS certification topics.
    - [ ] Introduce troubleshooting scenarios where the user must diagnose and fix a broken resource in a live environment.
    - [ ] Add questions about Kubernetes security best practices.

## Future Vision & Long-Term Goals

Ideas that are further out on the horizon.

- **[ ] Web UI / TUI:**
    - [ ] Develop a full-featured Text-based User Interface (TUI) using a library like `rich` or `textual`.
    - [ ] Explore creating a companion web application for a more graphical experience.

- **[ ] Custom Question Decks:**
    - [ ] Allow users to write their own questions and answers in a simple format (e.g., JSON or YAML).
    - [ ] Implement functionality to share and download question packs from a central repository or URL.

- **[ ] AI-Powered Features:**
    - [ ] Use an LLM to provide dynamic hints or detailed explanations.
    - [ ] Experiment with AI-generated questions for a virtually unlimited question pool.

- **[ ] Multiplayer Mode:**
    - [ ] A competitive mode where two or more users race to answer questions correctly.
