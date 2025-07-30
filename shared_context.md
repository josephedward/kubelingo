## Unified Terminal Quiz Refactor

### Motivation
- Users currently face three distinct modes (shell commands, YAML editing, Vim), creating an inconsistent experience and extra cognitive load.
- A single terminal interface reduces context switching and unifies all question types behind one workflow.

### Design Overview
1. Single Shell Runner (`_run_shell_question`)
   - Step 1: Execute `initial_cmds` and provision `initial_files` (e.g. YAML manifests) to set up prerequisites.
   - Step 2: Launch a PTY or Docker container shell for the user to work in.
     * Users run commands directly (e.g. `kubectl get pods`, `kubectl apply -f pod.yaml`, or open Vim).
     * For Vim-based exercises, `vim` is launched inside the shell; upon exit, the edited files are retained for validation.
   - Step 3: Upon shell exit, run validation commands (`ValidationStep.cmd`) to verify results.
     * For manifest-based exercises, run `kubectl get -f <file>.yaml` or `kubectl get <resource>` to ensure resources were created.
2. Simplified Interactive Menu
   - Removed separate “Check Answer” and inline editor paths.
   - Options are now: Open Shell, Flag/Unflag, Skip, Back to Quiz Menu.
3. Outcome-Based Validation
   - Success is determined by inspecting cluster or file state after user actions, not command text matching.
   - Manifest-based questions use `kubectl get` checks; Vim-based questions may validate file contents or applied results.

### PTY Shell vs Docker Container
- PTY Shell
  - Pros: Fast start, uses host environment, minimal overhead.
  - Cons: No sandboxing—commands run on host.
- Docker Container
  - Pros: Full isolation, consistent environment, safe for destructive commands.
  - Cons: Slower startup, requires Docker.

Use PTY for quick local quizzes, Docker for safe, reproducible environments.

### Session Transcript Logging & AI-Based Evaluation
To support full-session auditing and optional AI judgment, we can record everything the user does in the sandbox:
1. **Wrap the shell in the UNIX `script` utility**:
   ```bash
   # Inside spawn_pty_shell or launch_container_sandbox:
   script -q -c "bash --login" "$TRANSCRIPT_PATH"
   ```
   - Records all input/output (including `vim` commands) to `TRANSCRIPT_PATH`.
2. **Parse and sanitize the transcript**:
   - Strip ANSI escape codes.
   - Extract user keystrokes and commands.
3. **Deterministic or AI-based evaluation**:
   - **Deterministic**: scan the transcript for required `kubectl`/`helm` invocations, then validate cluster state via `kubectl get ...` or diff stored manifests.
   - **AI-based**: send the transcript, the question prompt, and expected outcomes (YAML spec or resource assertions) to the LLM, asking it to return a pass/fail judgement.

**Tradeoffs**:
- Deterministic validation is fast, offline, and predictable but rigid (only matches known commands).
- AI-based evaluation can handle creative workflows and freeform `vim` edits, but requires a valid `OPENAI_API_KEY` and produces non-deterministic results.

Leveraging this transcript + AI pipeline allows us to unify all question types (commands, YAML edits, Helm charts) under a single shell-driven flow with transparent grading.
  
### Documentation & Roadmap Updates
- Added a new Phase 1: Unified Shell Experience to `docs/roadmap.md`, covering schema enhancements, sandbox runner, CLI refactor, session transcript recording, evaluation pipelines, and testing/documentation.
- Recorded these changes here to keep shared context in sync.
- Interactive CLI quiz type selection now includes an explicit 'Exit' option to allow quitting without starting a quiz.
# Kubelingo Development Context

## AI-Powered Exercise Evaluation

### Overview

This document outlines the implementation of an AI-powered evaluation system for sandbox exercises in Kubelingo. This feature enhances the learning experience by providing intelligent feedback on a user's performance beyond simple command matching or script-based validation.

### Feature Description

- **`--ai-eval` Flag**: A new command-line flag, `--ai-eval`, enables the AI evaluation mode. When active, Kubelingo records the user's entire terminal session within the sandbox.
- **Full-Session Transcripting**: The system captures all user input and shell output, creating a comprehensive transcript of the exercise attempt. This includes `kubectl`, `helm`, and other shell commands.
- **Vim Command Logging**: To provide insight into file editing tasks, commands executed within `vim` are also logged to a separate file. This is achieved by aliasing `vim` to `vim -W <logfile>`.
- **AI Analysis**: After the user exits the sandbox, the transcript and Vim log are sent to an OpenAI model (e.g., GPT-4). The AI is prompted to act as a Kubernetes expert and evaluate whether the user's actions successfully fulfilled the requirements of the question.
- **Feedback**: The AI's JSON-formatted response, containing a boolean `correct` status and a `reasoning` string, is presented to the user.

#### Hybrid Evaluation Strategy

To provide the best experience for different types of questions, Kubelingo uses a hybrid evaluation approach:

1.  **Transcript-Based Evaluation (for Sandbox Exercises)**:
    -   **Trigger**: Enabled with the `--ai-eval` flag for `live_k8s` and `live_k8s_edit` question types.
    -   **Mechanism**: Captures the entire user session in the sandbox (via Rust PTY integration) into a transcript. This transcript is sent to the AI for a holistic review of the user's actions.
    -   **Use Case**: Ideal for complex, multi-step exercises where the final state of the cluster or files determines success.

2.  **Command-Based Evaluation (for Command Questions)**:
    -   **Trigger**: Enabled by setting the `KUBELINGO_AI_EVALUATOR=1` environment variable for `command` question types.
    -   **Mechanism**: Sends only the user's single-line command answer to the AI for semantic validation. It's a lightweight check that understands aliases, flag order, and functional equivalence.
    -   **Use Case**: Perfect for knowledge-check questions where a quick, intelligent validation of a single command is needed without the overhead of a sandbox.

### Implementation Details

1.  **Rust PTY Shell (`src/cli.rs`)**:
    - The `run_pty_shell` function is enhanced to support transcripting.
    - It checks for two environment variables: `KUBELINGO_TRANSCRIPT_FILE` and `KUBELINGO_VIM_LOG`.
    - If `KUBELINGO_TRANSCRIPT_FILE` is set, it tees all PTY input and output to the specified file.
    - If `KUBELINGO_VIM_LOG` is set, it configures the `bash` shell to alias `vim` to log commands to the specified file.

2.  **Python Session (`kubelingo/modules/kubernetes/session.py`)**:
    - When `--ai-eval` is used, `_run_unified_quiz` creates temporary files for the transcript and Vim log.
    - It sets the corresponding environment variables before launching the sandbox.
    - After the sandbox session, it reads the logs and passes them to the evaluation function.
    - The `_run_one_exercise` method is updated to call the AI evaluator when this mode is active, otherwise falling back to the legacy assertion script validation.

3.  **AI Evaluator (`kubelingo/modules/ai_evaluator.py`)**:
    - A new `AIEvaluator` class encapsulates the logic for interacting with the OpenAI API.
    - It constructs a detailed prompt including the question, transcript, and logs.
    - It requires an `OPENAI_API_KEY` environment variable to be set. The `kubelingo[llm]` package extra should be installed.

### Usage

To use this feature, run Kubelingo with the `--ai-eval` flag:
```bash
kubelingo --k8s --ai-eval
```
Ensure that `OPENAI_API_KEY` is set in your environment.
