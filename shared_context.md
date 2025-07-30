## Current Architecture: The Unified Shell Experience

Kubelingo delivers every quiz question—whether command, manifest/YAML edit, or Vim exercise—via one consistent shell-driven workflow. This was achieved through a major refactor that unified the user experience.

The core components of this architecture are:
1.  **Extended `Question` Schema**: The `Question` model currently includes:
   - `pre_shell_cmds` (via the legacy `initial_cmds` field) for setup commands (e.g. `kubectl apply -f …`).
   - `initial_yaml` for simple YAML-based exercises.
   - `validations` for single-step command checks.
   Next, we will add:
   - `initial_files: Dict[str, str]` to seed multiple starter files.
   - `validation_steps: List[ValidationStep]` of post-shell commands with matchers for the full unified schema.
2.  **Sandbox Helper**: The `run_shell_with_setup(...)` function:
    - Provisions an isolated workspace, writes `initial_files`, and runs `pre_shell_cmds`.
    - Spawns an interactive PTY shell (or Docker container) that records a full session transcript (including Vim edits).
    - After the shell exits, it executes each `ValidationStep.cmd`, applies matchers (e.g., exit code, regex), and aggregates results.
    - Returns structured `ShellResult` data and cleans up the workspace.
3.  **Unified Session Flow**: The main Kubernetes session now uses the sandbox helper for all question types, removing legacy branching for different quiz formats.
4.  **Stateful Navigation**: The interactive quiz menu supports `Next`, `Previous`, `Open Shell`, and `Check Answer`, tracking per-question status and transcripts.
5.  **Persistent Transcripts**: Session transcripts are saved to `logs/transcripts/...` and can be evaluated on-demand via the `Check Answer` feature, enabling replayable proof-of-execution.

With this foundation, the next steps are to:
With this foundation, the next steps are to:
1.  Expand matcher support (JSONPath, YAML structure, cluster state checks).
2.  Add unit/integration tests for `answer_checker` and the new UI flows.
3.  Flesh out AI-based “second opinion” evaluation (using Simon Willison’s [`llm`](https://github.com/simonw/llm) package to reduce transcripts to a deterministic yes/no verdict).

## Unified Terminal Quiz Refactor

### Motivation
- Users currently face three distinct modes (shell commands, YAML editing, Vim), creating an inconsistent experience and extra cognitive load.
- A single terminal interface reduces context switching and unifies all question types behind one workflow.

### Design Overview
1. **Single Shell Runner (`run_shell_with_setup` in `kubelingo/sandbox.py`)** - Implemented
   - Step 1: Execute `pre_shell_cmds` and provision `initial_files` to set up prerequisites in a temporary workspace.
   - Step 2: Launch a shell for the user.
     * The Rust bridge now uses the `script` utility for robust transcripting when `--ai-eval` is enabled.
   - Step 3: Upon shell exit, run `validation_steps` to verify results.
     * Deterministic validation checks the exit code of validation commands.
     * This new runner is now integrated into the main quiz loop.
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

### Implementation Progress
- Added `pre_shell_cmds`, `initial_files`, and `validation_steps` fields to `Question` model in `kubelingo/question.py`.
- Fully implemented `run_shell_with_setup` in `kubelingo/sandbox.py` to:
  * Provision an isolated workspace and write `initial_files` (including legacy `initial_yaml`).
  * Execute `pre_shell_cmds` (legacy `initial_cmds`) in the workspace.
  * Spawn a PTY or Docker sandbox shell, always capturing a full terminal transcript and Vim log.
  * Persist transcripts to `logs/transcripts/<session_id>/<question_id>.log` via a new `answer_checker` module (using `KUBELINGO_SESSION_ID`).
  * Added `evaluate_transcript(transcript_path, validation_steps)` in `answer_checker` for reusable transcript-based validation.
  * Run each `ValidationStep` post-shell, aggregating `StepResult` entries for deterministic checks.
  * Return a `ShellResult(success, step_results, transcript_path)` for downstream UI checks.
- Migrated all questions in `ckad_quiz_data.json` to the new unified schema (`validation_steps`, `pre_shell_cmds`, `initial_files`).
- Refactored session runner and sandbox helper to remove legacy compatibility code and use the new schema exclusively.

Added new `answer_checker` module to:
  * Save and load per-question transcripts.
  * Provide `check_answer(q)` function to inspect saved transcripts against validation matchers.

Updated interactive CLI quiz session to:
  * Include “Open Shell”, “Check Answer”, “Next Question”, “Previous Question”, and “Exit Quiz” options.
  * Maintain `transcripts_by_index`, `attempted_indices`, and `correct_indices` to track user progress.
- Refactored session menu to add navigation actions: Open Shell, Check Answer, Next, Previous, Flag/Unflag, Exit.
- Implemented per-question `transcripts_by_index` mapping and “Check Answer” action in `kubelingo/modules/kubernetes/session.py` to evaluate stored transcripts without relaunch.
- Extended matcher support in `answer_checker.evaluate_transcript` and the sandbox helper to cover `exit_code`, `contains`, and `regex` matchers.
- Next steps: write unit/integration tests for matcher logic and the `answer_checker` module; flesh out AI-based evaluation integration.
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

#### Interactive API Key Prompt
- To improve usability, Kubelingo now interactively prompts for an `OPENAI_API_KEY` at startup if one is not found in the environment.
- This feature requires the `questionary` library.
- If the user provides a key, it is set as an environment variable for the duration of the session, enabling AI-powered explanations and evaluations.
- If the user declines or aborts, AI features remain disabled.
- This removes the hard requirement of pre-configuring the environment, allowing for more flexible use of AI assistance.

### Usage

To use this feature, run Kubelingo with the `--ai-eval` flag:
```bash
kubelingo --k8s --ai-eval
```
Ensure that `OPENAI_API_KEY` is set in your environment.
