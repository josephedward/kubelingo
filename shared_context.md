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