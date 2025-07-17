<!-- Kubelingo Roadmap -->
# Kubelingo Project Roadmap

This document outlines the vision, features, and enhancements planned for the Kubelingo CLI quiz tool. It is organized into key focus areas and milestone ideas.

> _This roadmap is a living document. Feel free to propose additions or reprioritize items via issues or pull requests._

## Phase 0: Current Implementation (Not Previously Documented)

### Existing Features to Maintain
- [x] **LLM Integration**: OpenAI API integration for detailed explanations (`kubelingo/utils/llm_integration.py`)
- [x] **Review/Flagging System**: Mark questions for later review (`mark_question_for_review`, `unmark_question_for_review`)
- [x] **Rust-Python Bridge**: Performance-critical validation functions in Rust (`kubelingo_core` module)
- [x] **Session History**: Basic session logging and history tracking
- [x] **Semantic YAML Validation**: Compare parsed YAML structures, not raw text
- [x] **Category Filtering**: Filter questions by Kubernetes topic areas
- [x] **Randomized Question Order**: Prevent memorization of question sequences
- [x] **Multiple Question Types**: Command-based and YAML editing exercises

### Technical Infrastructure
- [x] **Hybrid Architecture**: Python CLI with Rust performance modules
- [x] **Maturin Build System**: Python package with Rust extensions
- [x] **CI/CD Pipeline**: GitHub Actions with multi-Python version testing
- [x] **Modular Design**: Separate modules for different quiz types

## Phase 1: Core Enhancements

Focus on solidifying the core quiz experience and adding high-value features.

### Difficulty Levels
- [ ] Implement a mechanism to tag questions with difficulty levels (Beginner, Intermediate, Advanced).
- [ ] Add a command-line flag (`--difficulty`) to let users filter questions.
- [ ] Adjust scoring or hints based on the selected difficulty.

### Performance Tracking & History
- [ ] Enhance history tracking to include time taken per question and streaks.
- [ ] Implement a `kubelingo history` command to show detailed performance analytics.
- [ ] Visualize progress over time (e.g., ASCII charts in the terminal).

### Spaced Repetition System (SRS)
- [ ] Integrate an SRS algorithm to prioritize questions the user has previously answered incorrectly.
- [ ] Automatically schedule questions for review based on performance.

## Phase 2: Interactive Environments

Bridge the gap between theory and practice by integrating with live Kubernetes clusters.

### Sandbox Integration
- [ ] Finalize integration with a sandbox provider (e.g., a custom Go-based sandbox environment).
- [ ] Develop a session manager to request, configure, and tear down ephemeral Kubernetes environments for quiz sessions.
- [ ] Ensure `kubectl` commands are correctly routed to the sandbox cluster.

### Homelab Integration
- [ ] Add functionality to allow users to use their own homelab cluster.
- [ ] Implement a configuration flow (`kubelingo config --use-context <my-homelab-context>`) to point KubeLingo to a user-provided kubeconfig context.
- [ ] Add safety checks and warnings when operating on a non-ephemeral cluster.

### Command Validation in Live Environments
- [ ] Develop a robust system to capture commands run by the user within the live environment.
- [ ] Validate the *state* of the cluster after a user's command, rather than just comparing command strings. (e.g., "Was a pod named 'nginx' actually created?").

## Phase 3: Advanced Editing and Content

Improve the YAML editing experience and expand the question library.

### Vim Mode for YAML Editing
- [ ] Integrate a terminal-based text editor with Vim keybindings for the YAML editing exercises.
- [ ] Explore options like `pyvim` or creating a temporary file and launching the user's `$EDITOR`.

### Real-time YAML Validation
- [ ] Integrate a YAML linter (e.g., `yamllint`) and the Kubernetes OpenAPI schema.
- [ ] Provide immediate feedback on syntax errors and invalid Kubernetes resource definitions as the user types.

### Expanded Content & New Question Types
- [ ] Add question packs for CKA and CKS certification topics.
- [ ] Introduce troubleshooting scenarios where the user must diagnose and fix a broken resource in a live environment.
- [ ] Add questions about Kubernetes security best practices.

## Phase 4: Advanced Features (From Development Discussions)

### Enhanced Learning Analytics
- [ ] **Detailed Performance Metrics**: Time per question, accuracy trends, weak topic identification
- [ ] **Learning Curve Analysis**: Track improvement over time with statistical analysis
- [ ] **Adaptive Difficulty**: Automatically adjust question difficulty based on performance
- [ ] **Competency Mapping**: Map performance to specific CKAD exam objectives

### Developer Experience Improvements
- [ ] **Hot Reload**: Automatically reload question data during development
- [ ] **Question Authoring Tools**: CLI tools for creating and validating new questions
- [ ] **Bulk Question Import**: Import questions from various formats (CSV, JSON, YAML)
- [ ] **Question Analytics**: Track which questions are most/least effective

### Integration Enhancements
- [ ] **IDE Plugins**: VSCode/Vim plugins for in-editor practice
- [ ] **Kubernetes Dashboard Integration**: Practice directly in K8s web UI
- [ ] **CI/CD Integration**: Run kubelingo tests in development pipelines
- [ ] **Slack/Discord Bots**: Team-based practice and competitions

### Advanced Validation
- [ ] **Multi-Solution Support**: Accept multiple correct answers for open-ended questions
- [ ] **Partial Credit Scoring**: Grade partially correct YAML with detailed feedback
- [ ] **Context-Aware Validation**: Validate based on cluster state, not just manifest content
- [ ] **Security Scanning**: Integrate with tools like Falco for security best practices

## Phase 5: Ecosystem Integration

### Cloud Provider Specific Features
- [ ] **GCP GKE Integration**: Google Cloud sandbox environments
- [ ] **Azure AKS Integration**: Azure sandbox environments  
- [ ] **Multi-Cloud Scenarios**: Practice migrating workloads between providers
- [ ] **Cloud-Native Tools**: Integration with Helm, Kustomize, ArgoCD

### Enterprise Features
- [ ] **Team Management**: Multi-user environments with progress tracking
- [ ] **Custom Branding**: White-label versions for training organizations
- [ ] **Reporting Dashboard**: Manager/instructor view of team progress
- [ ] **Integration APIs**: Connect with LMS and HR systems

## Future Vision & Long-Term Goals

Ideas that are further out on the horizon.

### Web UI / TUI
- [ ] Develop a full-featured Text-based User Interface (TUI) using a library like `rich` or `textual`.
- [ ] Explore creating a companion web application for a more graphical experience.

### Custom Question Decks
- [ ] Allow users to write their own questions and answers in a simple format (e.g., JSON or YAML).
- [ ] Implement functionality to share and download question packs from a central repository or URL.

### AI-Powered Features
- [ ] Use an LLM to provide dynamic hints or detailed explanations.
- [ ] Experiment with AI-generated questions for a virtually unlimited question pool.

### Multiplayer Mode
- [ ] A competitive mode where two or more users race to answer questions correctly.
