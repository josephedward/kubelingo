## Current Architecture: The Unified Shell Experience

Kubelingo delivers every quiz question—whether command, manifest/YAML edit, or Vim exercise—via one consistent shell-driven workflow. This was achieved through a major refactor that unified the user experience.

The core components of this architecture are:
1.  **Extended `Question` Schema**: The `Question` model now includes:
    - `pre_shell_cmds: List[str]` for setup commands (e.g. `kubectl apply -f …`).
    - `initial_files: Dict[str, str]` to seed YAML or other starter files.
    - `validation_steps: List[ValidationStep]` of post-shell commands with matchers.
2.  **Sandbox Helper**: The `run_shell_with_setup(...)` function:
    - Provisions an isolated workspace, writes `initial_files`, and runs `pre_shell_cmds`.
    - Spawns an interactive PTY shell (or Docker container) that records a full session transcript (including Vim edits).
    - After the shell exits, it executes each `ValidationStep.cmd`, applies matchers (e.g., exit code, regex), and aggregates results.
    - Returns structured `ShellResult` data and cleans up the workspace.
3.  **Unified Session Flow**: The main Kubernetes session now uses the sandbox helper for all question types, removing legacy branching for different quiz formats.
4.  **Stateful Navigation**: The interactive quiz menu supports `Next`, `Previous`, `Open Shell`, and `Check Answer`, tracking per-question status and transcripts.
5.  **Persistent Transcripts**: Session transcripts are saved to `logs/transcripts/...` and can be evaluated on-demand via the `Check Answer` feature, enabling replayable proof-of-execution.

With this foundation, the next steps are to:
1.  Expand matcher support (JSONPath, YAML structure, cluster state checks).
2.  Add unit/integration tests for `answer_checker` and the new UI flows.
3.  Flesh out AI-based “second opinion” evaluation (using Simon Willison’s [`llm`](https://github.com/simonw/llm) package to reduce transcripts to a deterministic yes/no verdict).
4.  Implement an interactive prompt for the `OPENAI_API_KEY` if it is not found, to improve usability.

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
   - Options are now: Work on Answer (in Shell), Check Answer, Flag for Review, Next Question, Previous Question, Exit Quiz.
3. Outcome-Based Validation
   - Success is determined by inspecting cluster or file state after user actions, not command text matching.
   - Manifest-based questions use `kubectl get` checks; Vim-based questions may validate file contents or applied results.

### PTY Shell vs Docker Container
- PTY Shell
  - Pros: Fast start, uses host environment, minimal overhead.
  - Cons: No sandboxing—commands run on host. This means tools like `kubectl` must be installed and configured on your local machine.
  - **Note**: The PTY shell is configured to provide a consistent experience. It sets a `(kubelingo-sandbox)$` prompt, silences macOS `bash` deprecation warnings, and provides a `k=kubectl` alias. It also attempts to source your existing `~/.bash_profile` to preserve your environment.
- Docker Container
  - Pros: Full isolation, consistent environment, safe for destructive commands.
  - Cons: Slower startup, requires Docker.

Use PTY for quick local quizzes, Docker for safe, reproducible environments.

### Session Transcript Logging & AI-Based Evaluation
To support full-session auditing and optional AI judgment, we can record everything the user does in the sandbox:
1. **Robust PTY shell launch with `script`**:
   - When a transcript file is requested (`KUBELINGO_TRANSCRIPT_FILE` env var) and the `script` utility exists, the shell is launched under:
     ```bash
     script -q -c "bash --login --init-file <init-script>" "$KUBELINGO_TRANSCRIPT_FILE"
     ```
     This ensures full-session recording (including `vim` edits) and properly restores terminal modes on exit, avoiding nested prompt failures.
   - Otherwise, falls back to Python’s `pty.spawn(['bash','--login', '--init-file', <init-script>])`, maintaining the custom sandbox prompt and environment.
2. **Parse and sanitize the transcript**:
   - Strip ANSI escape codes.
   - Extract user keystrokes and commands.
3. **Post-Shell Evaluation**:
   - **Deterministic Checks**: Upon shell exit, each `ValidationStep` is executed and matched against the recorded transcript (exit code, substring contains, regex, JSONPath, etc.).
   - **AI Second Opinion**: If an `OPENAI_API_KEY` is present and the transcript was saved, the AI evaluator is dynamically imported at runtime (no heavy `llm` imports at load time). It invokes `evaluate(question, transcript)` to get a JSON response with `correct` (bool) and `reasoning` (str), printed in cyan below the deterministic feedback. If the AI verdict disagrees with the deterministic result, AI overrides it. All import or invocation errors are caught so that AI evaluation failures do not crash the quiz.

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
- Refactored session menu to dynamically build navigation actions (Work on Answer, Check Answer, Flag/Unflag; Next/Previous only when valid; Exit).
- Removed all manual numeric prefixes from CLI and session menu labels; questionary’s auto-numbering now provides consistent labeling.
- Implemented per-question `transcripts_by_index` mapping and “Check Answer” action in `kubelingo/modules/kubernetes/session.py` to evaluate stored transcripts without relaunch.
- Extended matcher support in `answer_checker.evaluate_transcript` and the sandbox helper to cover `exit_code`, `contains`, and `regex` matchers.
- Implemented "second opinion" AI evaluation: if deterministic checks fail and `--ai-eval` is enabled, the transcript is sent to an LLM to potentially override the result.
 - **Fixed**: Cleared the terminal at the start of each question to separate contexts and prevent UI overlap.
 - **Fixed**: Removed manual numeric prefixes from all menus; questionary auto-numbering now renders cleanly.
 - **Fixed**: Inserted blank lines before rendering menus to ensure clear visual separation from prior content.
 - **Fixed**: Removed the top-level `import llm` (and heavy pandas/numpy/sqlite_utils deps) from `ai_evaluator.py`, deferring the `llm` import to runtime inside `_check_and_process_answer`. This prevents startup segmentation faults and restores the full ASCII-art banner and interactive menus.
 - **Fixed**: Consolidated all question flows through the unified `spawn_pty_shell` runner so that, upon shell exit, control returns cleanly to the main quiz loop. This avoids nested Questionary prompts inside the sandbox and eliminates unintended cancellations.
  - **Fixed**: A UI bug causing nested prompts was resolved by ensuring all questions use the unified PTY shell. Placeholder `validation_steps` were added to markdown-based questions that lacked them, forcing consistent processing through the modern, robust answer interface. This also enables transcript-based AI evaluation for all exercises.
  - **Fixed (attempted)**: The interactive CLI menu for bare `kubelingo` had been disabled by a mis-indentation/guard. Although the guard was removed, the block remains incorrectly nested under the `--k8s` shortcut, so it still does not fire on an empty invocation. A full refactor is needed to move the menu logic before any module dispatch.
  - **Fixed**: Corrected a critical syntax/indentation error in `kubelingo/cli.py` by removing a malformed, duplicated interactive block and restoring a minimal bare-`kubelingo` fallback menu (PTY Shell, Docker Container, Enter OpenAI API Key, Exit).
  - **Fixed**: Addressed a UI regression in `kubelingo/modules/kubernetes/session.py` by standardizing menu choice definitions as simple `{"name": ..., "value": ...}` dict literals (instead of mixed `questionary.Choice`), restoring clean layout and correct numbering.
  - **Fixed**: Corrected the `default` argument for the per-question action menu in `kubelingo/modules/kubernetes/session.py`. It now correctly uses the choice `value` ('answer') instead of its `name`, restoring the default selection indicator (`»`) and fixing the UI regression.
  - **Fixed**: Wrapped the PTY shell under `script` when recording transcripts, fixing terminal state corruption and preventing nested Questionary prompts from auto-cancelling after exit.
  - **Fixed**: Repaired a critical dispatch logic error in `kubelingo/cli.py` that caused invocations with flags (e.g., `--k8s`) to exit prematurely. A large block of code containing the module execution logic was incorrectly indented within a conditional, preventing it from running. The fix involved removing duplicated code and correcting indentation, restoring quiz functionality for all non-interactive invocations.
  - **Fixed**: Restored the interactive `questionary`-based menus for bare `kubelingo` invocations. A UI regression had replaced them with a plain text-based menu. The fix re-implements the rich menu with `use_indicator=True` and dict-based choices, while retaining the text menu as a fallback for non-TTY environments. This resolves the `F821 undefined name 'questionary'` errors.
- Next steps: write unit/integration tests for matcher logic and the `answer_checker` module.
  
### Testing & Observations
- Smoke-tested `run_shell_with_setup` with a dummy question (echo/contains): passes validation, shell spawn aborted appropriately in headless mode.
- Transcript persistence via `save_transcript` works: logs saved under `logs/transcripts/...`.
- CLI menu navigation now inserts a blank line before rendering the next menu, preventing prompt text from merging with question output.
- `evaluate_transcript` correctly evaluates exit_code, contains, and regex matchers; JSONPath and cluster-state matchers pending.
- Loaders still populate only legacy `initial_yaml` and `validations`; new `initial_files`/`validation_steps` fields unpopulated.

### CLI Readability & Regression Tests
To guard against mangled output and UI regressions, we recommend:
Options are now: Work on Answer (in Shell), Check Answer, Flag for Review, Next Question, Previous Question, Exit Quiz
1.  Smoke-test static CLI outputs:
    -  Use pytest’s `capsys` or a subprocess to run `kubelingo --help`, `--history`, `--list-modules`, etc.
    -  Assert exit code 0, presence of key banner lines and option names (e.g. `Select a session type:`), and absence of control chars (`\x00`).
    -  Strip ANSI codes (`re.sub(r'\x1b\[[0-9;]*m', '', line)`) and ensure no overlong lines (>80 chars).
2.  Snapshot tests for visual regression:
    -  Capture the desired `--help` (or menu) output and store in `tests/expected/help.txt`.
    -  In pytest, compare current output to the snapshot. Any unintended changes will fail CI until explicitly updated.
3.  Doc-driven menu consistency:
    -  Extract bullet points from `shared_context.md` (e.g. `• Open Shell`, `• Check Answer`, `• Next Question`, `• Previous Question`).
    -  Assert those exact strings appear in code (`kubelingo/cli.py` or `modules/kubernetes/session.py`), ensuring docs and code stay in sync.
4.  Minimal example test (in `tests/test_cli_readability.py`):
    ```python
    import sys, re, subprocess, pytest
    ANSI = re.compile(r'\x1b\[[0-9;]*m')
    BIN = [sys.executable, '-m', 'kubelingo']

    def run_cli(args):
        return subprocess.run(BIN + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_help_readable():
        r = run_cli(['--help'])
        assert r.returncode == 0
        out = r.stdout
        assert 'Kubelingo:' in out
        for line in out.splitlines():
            clean = ANSI.sub('', line)
            assert len(clean) <= 80
            assert '\x00' not in clean

    def test_menu_readable(monkeypatch, capsys):
        import builtins
        monkeypatch.setattr(sys, 'argv', ['kubelingo'])
        monkeypatch.setattr(builtins, 'input', lambda _: '4')  # select Exit
        monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
        monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
        from kubelingo.cli import main
        main()
        out = capsys.readouterr().out
        assert 'Select a session type:' in out
        assert '1) PTY Shell' in out and '4) Exit' in out

These tests will flag any stray ANSI codes, missing menu items, or misaligned text, keeping the CLI consistently legible and aligned with the documentation.
# Kubelingo Development Context

## AI-Powered Exercise Evaluation

### Overview

This document outlines the implementation of an AI-powered evaluation system for sandbox exercises in Kubelingo. This feature enhances the learning experience by providing intelligent feedback on a user's performance beyond simple command matching or script-based validation.

### Feature Description

- **AI-by-default Sandbox Evaluation**: For any sandbox exercise, AI evaluation is the default. Kubelingo records the user's entire terminal session. If an `OPENAI_API_KEY` is present, it uses an LLM to evaluate the transcript. The `--ai-eval` flag is deprecated but retained for backward compatibility.
- **Full-Session Transcripting**: The system captures all user input and shell output, creating a comprehensive transcript of the exercise attempt. This includes `kubectl`, `helm`, and other shell commands.
- **Vim Command Logging**: To provide insight into file editing tasks, commands executed within `vim` are also logged to a separate file. This is achieved by aliasing `vim` to `vim -W <logfile>`.
- **AI Analysis**: After the user exits the sandbox, the transcript and Vim log are sent to an OpenAI model (e.g., GPT-4). The AI is prompted to act as a Kubernetes expert and evaluate whether the user's actions successfully fulfilled the requirements of the question.
- **Feedback**: The AI's JSON-formatted response, containing a boolean `correct` status and a `reasoning` string, is presented to the user.

#### Evaluation Strategy

Kubelingo uses the following evaluation approach:

1.  **Transcript-Based Evaluation (for Sandbox Exercises)**:
    -   **Trigger**: Enabled by default for all sandbox-based question types whenever an `OPENAI_API_KEY` is available.
    -   **Mechanism**: Captures the entire user session in the sandbox (via Rust PTY integration) into a transcript. This transcript is sent to the AI for a holistic review of the user's actions. If AI evaluation is not available, the system falls back to deterministic validation against `validation_steps`.
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

3.  **AI Evaluator (using `llm` package)**:
    - To rapidly prototype and simplify AI integration, we will use Simon Willison's `llm` package.
    - This tool provides a convenient command-line and Python interface for interacting with various LLMs.
    - The evaluation process involves sending the full context (question, validation steps, and transcript) to the LLM. The prompt is engineered to return a deterministic `yes/no` judgment and a brief explanation. By including the question's `validation_steps`, the AI gets explicit success criteria, improving the accuracy of its verdict.
    - This approach avoids direct integration with the `openai` package for now, allowing for a more flexible and straightforward implementation of the AI-based evaluation feature. It still requires an API key for the chosen model (e.g., `OPENAI_API_KEY`).

### Usage

To use this feature, run Kubelingo with the `--ai-eval` flag:
```bash
kubelingo --k8s --ai-eval
```
Ensure that `OPENAI_API_KEY` is set in your environment.

### UI Regression Analysis

The interactive command-line interface has experienced a significant regression, causing a return to a less polished user experience. Previously, menus were clean, using indicators (`»`) for selection. Now, they have reverted to using numeric prefixes (e.g., `1. PTY Shell`), and exhibit alignment issues, as seen in the recent output logs.

**Root Cause**: The regression was likely introduced during recent feature updates. It appears that earlier commits, which had refactored the `questionary` library calls to use a dictionary-based format for choices and enabled the `use_indicator=True` option, were inadvertently overwritten. This change was crucial for achieving the clean, numberless menu style.

**Affected Areas**: The regression impacts all interactive menus, including:
- The main session selection (`kubelingo/cli.py`).
- The per-question action menu (`kubelingo/modules/kubernetes/session.py`).

**Path to Resolution**: To fix this, the application's interactive prompts must be systematically updated to once again use the dictionary-based choice format and `use_indicator=True` flag. This will restore the consistent, user-friendly interface that was previously achieved.
