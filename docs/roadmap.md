<!-- Kubelingo Roadmap -->
# Kubelingo Project Roadmap

This document outlines the vision, features, and enhancements planned for the Kubelingo CLI quiz tool. It is organized into key focus areas and milestone ideas.

> _This roadmap is a living document. Feel free to propose additions or reprioritize items via issues or pull requests._# KubeLingo Project Roadmap


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
