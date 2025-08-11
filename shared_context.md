## Resilient Path Discovery

To improve stability and resilience against file reorganizations, Kubelingo now uses a centralized path discovery mechanism. All scripts and application code should use these helpers instead of hard-coded paths to locate data files.

- **Configuration in `kubelingo/utils/config.py`**: This file contains the source of truth for directory locations.
  - `QUESTION_DIRS`: A list of directories to search for question YAML files.
  - `YAML_BACKUP_DIRS`: A list of directories for YAML backups.
  - `SQLITE_BACKUP_DIR`: The directory for SQLite database backups.

- **Discovery in `kubelingo/utils/path_utils.py`**: This module provides functions to find data files.
  - `get_all_question_dirs() -> List[str]`: Returns all configured directories for question YAMLs.
  - `get_all_yaml_files(dirs: Optional[List[str]] = None) -> List[Path]`: Scans directories (defaults to `QUESTION_DIRS`) and returns all found `.yaml` and `.yml` files.
  - `get_all_yaml_backups() -> List[Path]`: Returns all `.yaml` and `.yml` files from `YAML_BACKUP_DIRS`.
  - `get_all_sqlite_backups() -> List[Path]`: Returns all `.db` files from `SQLITE_BACKUP_DIR`.
  - `get_live_db_path() -> str`: Returns the canonical path to the user's live database.

**Developer Guidance**: Always use helpers from `kubelingo.utils.path_utils` to locate data sources. For example, to import all questions, call `get_all_yaml_files()` and iterate over the returned list of `Path` objects. This ensures that your code will continue to work even if data files are moved to a different configured location.

## Question Categories

We classify quiz questions into three main categories, each driving a distinct user workflow and validation approach:

1. Open-Ended Questions
   - Type: `socratic`
   - Description: Conceptual or resource-based quizzes (Socratic tutor, operations, resource reference).
   - Answers are free-form explanations or single operations/resources (outside of an interactive shell).
   - CLI Flag: `--socratic`

2. Command-Based Questions
   - Type: `kubectl` or `command`
   - Description: Single-line imperative commands (e.g., `kubectl`, `helm`, or other shell commands).
   - Evaluated for conceptual correctness and syntax (e.g., via `kubectl --dry-run=client -o yaml`).
   - CLI Flag: `--kubectl`

3. Manifest-Based Questions
   - Type: `yaml_edit` or `yaml_author`
   - Description: Editing or authoring Kubernetes resource manifests using Vim.
   - Workflow: Launches Vim editing mode, parses the edited YAML, and validates structure/content against the expected manifest.
   - CLI Flags: `--manifests` (alias `--yaml`)

Questions are stored in the database with a `question_type` column reflecting one of the above values. The unified session flow in the application dispatches to the appropriate handler based on this type.

## New `kubectl` Quizzes

Added eight new quiz modules based on the Kubernetes documentation, covering a wide range of `kubectl` commands. These quizzes are designed as command-based knowledge checks and follow the standardized YAML format.

The new quizzes are:
- **Kubectl Shell Setup**: Focuses on `kubectl` aliases and shell autocompletion.
- **Kubectl Pod Management**: Covers creating, inspecting, and managing Pods.
- **Kubectl Deployment Management**: Deals with Deployments, rollouts, and scaling.
- **Kubectl Namespace Operations**: Questions on creating and managing namespaces.
- **Kubectl ConfigMap Operations**: Focuses on creating and using ConfigMaps.
- **Kubectl Secret Management**: Covers creating and using Secrets.
- **Kubectl Service Account Operations**: Questions about ServiceAccounts.
- **Kubectl Additional Commands**: A general collection of other useful `kubectl` commands.

These quizzes are integrated into the main application menu and can be invoked using the `--quiz` argument.

## Data Discovery and Path Management

To make the application resilient against path changes and to centralize data management, Kubelingo uses a discovery layer for locating data files. This ensures that scripts and the application can find questions and backups even if directories are moved or reorganized.

**Core Principles**:
- **Centralized Configuration**: All primary data directories are defined as constants in `kubelingo/utils/config.py`. This includes paths for question sources (`QUESTION_DIRS`), YAML backups (`YAML_BACKUP_DIRS`), and SQLite backups (`SQLITE_BACKUP_DIRS`).
- **Dynamic Discovery**: A dedicated module, `kubelingo/utils/path_utils.py`, provides helper functions to find files. Scripts should use these helpers (e.g., `find_yaml_files()`) instead of hard-coding paths.
- **Resilient Scripts**: Maintenance scripts are being updated to use these discovery utilities, accept path overrides via CLI flags, and provide graceful fallbacks if data sources are not found.

**Best Practices for Developers & Agents**:
- **Always use the discovery layer**: When you need to read question files, call helpers from `kubelingo.utils.path_utils`. Do not hard-code paths like `question-data/questions`.
- **Example**: To get all question YAML files, use `find_yaml_files(get_all_question_dirs())`.

This approach ensures that questions are never "lost" and that the system can adapt to changes in the file structure.

## Database is the Source of Truth

**IMPORTANT**: At runtime, Kubelingo loads all quiz questions exclusively from a single SQLite database. It **does not** read individual JSON, YAML, or Markdown files from the `question-data/` directory. Those files should be considered legacy artifacts used only for seeding the database for the first time.

### Migrating Legacy Quiz Files into the Database

If you have legacy quiz definitions in YAML format under `question-data/yaml` or its backup directory `question-data/yaml-bak`, you can import them into the database by running:

```bash
python scripts/migrate_to_db.py
```

You can also use the built-in CLI command:
```bash
kubelingo migrate-yaml
```

This will:
- Discover all `.yaml` and `.yml` files in both `question-data/yaml` and `question-data/yaml-bak`.
- Insert or update each question into the live database (`~/.kubelingo/kubelingo.db`).
- Create a new backup of your migrated database at `question-data-backup/kubelingo.db`.

Once migration is complete, the CLI will rely solely on the database for all quizzes, and you can archive or remove the original YAML files if desired.

### Database Files Explained

- **Live Database (`~/.kubelingo/kubelingo.db`)**: This is your active, personal database. It lives in your home directory and stores your progress, review flags, and any AI-generated questions.
- **Original Questions Backup (`question-data-backup/kubelingo_original.db`)**: A version-controlled, read-only snapshot of the original question bank. The live database is no longer automatically seeded from this file. You must use the data management scripts (e.g., `scripts/import_yaml_to_db.py`, `scripts/import_json_to_db.py`) to populate your database. To prevent accidental data loss, automatic seeding on startup has been removed.

- **User Data Backup (`question-data-backup/kubelingo.db.bak`)**: To protect your data, scripts that perform migrations will create a backup of your *live* database with a `.bak` extension. This backup is typically stored at `question-data-backup/kubelingo.db.bak`.

To restore your database, use the `scripts/restore_db_from_backup.py` script. It lets you choose whether to restore from your user data backup or start fresh from the original backup.

### Imported Questions Live Only in the Database

Questions brought into the system by the JSON or PDF import scripts are stored *exclusively* in the live database (`~/.kubelingo/kubelingo.db`).  They do *not* appear under the legacy file-based menu entries (e.g., "YAML Editing", "Helm Basics").

To see which quiz modules exist in the database (including those imported from JSON or PDF), run:
```bash
python3 scripts/list_db_modules.py
```
This will list each module by name along with the number of questions it contains, for example:
```
Available DB quiz modules (module_name: question count):
 - kubectl_pod_management_quiz: 8
 - kubectl_operations_quiz: 44
 - kubectl_additional_commands_quiz: 42
 ...
```

Once you have the module name (e.g. `master_quiz`), launch it directly with:
```bash
kubelingo --exercise-module master_quiz
```
This will load that module’s questions from the DB and run the unified quiz interface.


### YAML Backup Utilities

- **locate_yaml_backups.py**: Locates YAML backup files, providing detailed information like file size and modification date. It can scan multiple directories and filter results.
  Usage:
  ```bash
  # Scan default backup directory
  python3 scripts/locate_yaml_backups.py
  # Scan a custom directory
  python3 scripts/locate_yaml_backups.py /path/to/your/backups
  ```

- **yaml_backup_stats.py**: Show detailed statistics for YAML files in a directory or for a single file. Requires PyYAML.
  Usage:
  ```bash
  # Scan default backup directory
  python3 scripts/yaml_backup_stats.py
  # Scan a specific file or directory
  python3 scripts/yaml_backup_stats.py <path-to-yaml-file-or-dir>
  ```

### Seeding the Database Manually

The live database at `~/.kubelingo/kubelingo.db` is **not** seeded automatically. You must manually populate it using the provided data management scripts. This ensures that the contents of your database are always under your direct control and prevents accidental data loss from automatic restores.

To populate your database, use scripts like:
- `scripts/import_yaml_to_db.py` to load questions from YAML files.
- `scripts/import_json_to_db.py` to load questions from JSON files.

These scripts will safely add or update questions in your live database.

### `scripts/import_json_to_db.py`

This script provides a way to populate the Kubelingo database from `question-data/json`. It complements the YAML import script and is essential for loading all question modules.

**Functionality**:
- **JSON Ingestion**: Recursively finds and parses all `.json` files in the `question-data/json` directory.
    - **Append-Only**: This script never deletes questions. It uses `INSERT OR REPLACE` so existing entries (by ID) are updated in-place and new ones are added. No clearing of existing data occurs.
- **Database Population**: Loads all questions from the JSON files and inserts them into the live SQLite database (`~/.kubelingo/kubelingo.db`).
- **Automatic Backup**: After a successful import, it creates a backup of the newly populated database.

**Usage**:

- To import or update all JSON-based quizzes (append-only):
  ```bash
  python3 scripts/import_json_to_db.py
  ```

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
4.  **Stateful Navigation**: The interactive quiz menu supports `Work on Answer (in Shell)`, `Check Answer`, `Show Expected Answer(s)`, `Show Model Answer` (when available), `Flag for Review`/`Unflag`, `Next Question`, `Previous Question`, and `Exit Quiz`, tracking per-question status and transcripts.
5.  **Persistent Transcripts**: Session transcripts are saved to `logs/transcripts/...` and can be evaluated on-demand via the `Check Answer` feature, enabling replayable proof-of-execution.

### How YAML Quizzes Pick Up Your Edits

The quiz engine handles file management for you—there’s no need to name or manage temp files manually. It works in two modes:

• **Live K8s Edits** (`live_k8s_edit` questions in YAML quizzes):
  – Each question defines an `initial_files` map, e.g. `pod.yaml` → stub contents.
  – Selecting “Work on Answer (in Shell)” seeds your sandbox’s working directory with those files.
  – Edit or rename them as you like, then run `kubectl apply -f <your-file>.yaml`.
  – On exit, the quiz runs `validation_steps` (e.g. `kubectl get pod resource-checker …`) against the cluster state; it does not re-read your local files.

• **Pure YAML Comparisons** (`yaml_edit` questions):
  – The CLI spins up a temporary YAML file, injects the prompt as comments, and opens it in Vim for you.
  – Exiting Vim returns you to the CLI, which slurps the temp file into memory, runs `yaml.safe_load`, and compares the resulting object to the question’s `correct_yaml`.
  – You never need to refer to the temp file yourself; matching happens in-memory.

In both cases, the question’s metadata (`initial_files`, `pre_shell_cmds`, `validation_steps`, or `correct_yaml`) drives what gets seeded, what gets checked, and where your edits are evaluated.

### Roadmap Progress

**Phase 1: Unified Shell Experience** is largely complete. The core architecture for delivering all question types through a consistent shell-driven workflow is in place. Here's where we stand on the immediate next steps:

-   **[Completed] Customizable quiz length**: Users can now specify the number of questions with `-n/--num`. If fewer are requested, a random subset is chosen. If more are requested, the system can generate additional questions via AI.
-   **[In Progress] Expand matcher support**: `exit_code`, `contains`, and `regex` matchers are implemented. JSONPath, YAML structure, and direct cluster state checks are still pending.
-   **[Not Started] Add unit/integration tests**: No formal tests exist yet for `answer_checker` or the new UI flows. This is the highest priority next step to prevent regressions.
-   **[Not Started] Flesh out AI-based evaluation**: The foundation for transcript-based evaluation is present, but the `llm` integration for a "second opinion" has not been started.
-   **[Not Started] Improve API key handling**: An interactive prompt for the `OPENAI_API_KEY` has not been implemented.
-   **[Completed] Persist AI-generated questions**: AI-generated questions are now automatically saved to a local SQLite database (`kubelingo.db`). This enables reuse and offline review. The implementation includes a `kubelingo/database.py` module for all database interactions and is rigorously tested in `tests/test_database.py` and `tests/modules/test_question_generator.py`.
  
## Recent Enhancements

- [Added] **Kubectl Syntax Validation**: Introduced `validate_kubectl_syntax()` in `kubelingo/utils/validation.py`, which runs `kubectl <cmd> --help` client-side to catch unknown commands or flags and surfaces errors or warnings before executing or recording user input.
- [Added] **YAML Manifest Structure Validation**: In the Vim-based YAML editor (`kubelingo/modules/kubernetes/vim_yaml_editor.py`), Kubelingo now applies `validate_yaml_structure()` on the edited manifest, printing any syntax or structure errors and warnings immediately after editing and before answer evaluation.
-- [Improved] **Kubectl Syntax Skipping**: If the `kubectl` binary is not found on the PATH, `validate_kubectl_syntax()` now treats commands as valid (skipping the `--help` check) instead of rejecting them outright.
-- [Improved] **Dry-Run Validation Fallback**: During AI-driven question generation, the `--dry-run=client` validation now catches `FileNotFoundError` and skips the validation step, preventing infinite retry loops when `kubectl` is missing.
-- [Improved] **AI Question Key Flexibility**: `AIQuestionGenerator.generate_questions()` now accepts alternative JSON keys—`question`/`answer` and `q`/`a`—in addition to `prompt`/`response` to accommodate varied AI output shapes.
- [Added] **Persistence for AI-Generated Questions**: Valid questions generated by the AI are now automatically saved to a local SQLite database (`kubelingo.db`). This prevents data loss and allows for reuse in future sessions. The feature is supported by a new `kubelingo/database.py` module and is fully tested.
- [Fixed] **Quiz Startup Crash**: Resolved a `TypeError` that occurred when starting quizzes (like the Vim quiz) with questions that do not have pre-shell commands. The session initialization logic now correctly handles cases where `pre_shell_cmds` is missing or null, preventing the application from crashing.

## Troubleshooting: Missing Quiz Questions After Adding New YAML Modules

If you add a new quiz YAML file under `question-data/yaml` (for example, `kubectl_additional_commands_quiz.yaml`) but `kubelingo --quiz <name>` shows `Questions: 0`, here's why and how to fix it:

- Kubelingo loads quizzes **only** from the local SQLite database at runtime; it does not re-scan `question-data/` directories on each run.
- On first run—or when the live DB is empty—Kubelingo **copies** the **original** backup database (`question-data-backup/kubelingo_original.db`) into your live DB (`~/.kubelingo/kubelingo.db`).
- If your new YAML file was committed **after** `kubelingo_original.db` was last updated, that backup (and any live DB seeded from it) will not include your new questions.
- To import **all** YAML quiz files (including newly added ones) into your live database, run:
  ```bash
  kubelingo migrate-yaml
  ```
  or:
  ```bash
  python scripts/import_yaml_to_db.py
  ```
- After importing, you can (re)create the project-level original backup so new users/installations will seed from the updated set:
  ```bash
  python scripts/import_and_backup.py
  ```
- To see when the original backup was last committed vs. when your YAML file was added:
  ```bash
  git log --pretty=oneline question-data-backup/kubelingo_original.db
  git log --pretty=oneline question-data/yaml/kubectl_additional_commands_quiz.yaml
  ```
- Once migrated, running:
  ```bash
  kubelingo --quiz kubectl_additional_commands_quiz.yaml
  ```
  should list the expected number of questions.

### Error when importing: `add_question() got an unexpected keyword argument '...'`

If you encounter an error like `TypeError: add_question() got an unexpected keyword argument 'solution_file'` when running a database import script, it often means you are using an older, deprecated script (such as `create_sqlite_db_from_yaml.py`).

The project has standardized on `scripts/import_yaml_to_db.py` for this task, as it is kept up-to-date with the database schema.

**Solution**: Use the correct script to import YAML questions:

```bash
python scripts/import_yaml_to_db.py
```

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
   - Options are now: Work on Answer (in Shell), Check Answer, Show Expected Answer(s), Show Model Answer, Flag for Review, Next Question, Previous Question, Exit Quiz.
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

### How YAML Quiz File Handling Works

You don’t have to “tell” the quiz which filename you used — all wiring happens behind the scenes in the question definition:

• **Live K8s Edits** (`type: live_k8s_edit` in `yaml_quiz.yaml`):
  – Each question’s metadata includes an `initial_files` map (e.g. `pod.yaml` → a stub with TODOs).
  – When you select “Work on Answer (in Shell)”, you enter a sandbox whose working directory already contains that exact file (`pod.yaml`).
  – You edit that file (or rename and apply it with your own `-f`, if you prefer), then run `kubectl apply -f …`.
  – On exit, Kubelingo runs the `validation_steps` (for example, `kubectl get pod resource-checker …`) against the live cluster state — it never needs to re‐read your local file.

• **Pure YAML Comparisons** (`type: yaml_edit`):
  – The CLI creates a tiny temp file under the covers and opens it in Vim for you to edit.
  – When you exit Vim, it slurps the temp file’s contents into memory and `safe_load`s it via PyYAML to a Python object.
  – That object is directly compared against the question’s `correct_yaml` field — again, you never name the file yourself.

In both modes, the question’s metadata (`initial_files` + `pre_shell_cmds` + `validation_steps`) drives seeding, checking, and grading. You simply edit & apply as instructed; the quiz picks up your work through its validation commands or by comparing the in-memory YAML object.

### Session Transcript Logging & AI-Based Evaluation
To support full-session auditing and optional AI judgment, we can record everything the user does in the sandbox:
1. **Robust PTY shell launch with `script`**:
   - When a transcript file is requested (`KUBELINGO_TRANSCRIPT_FILE` env var), the shell launch behavior depends on the platform:
     - On Linux, if the `script` utility exists, the shell is launched under:
       ```bash
       script -q -c "bash --login --init-file <init-script>" "$KUBELINGO_TRANSCRIPT_FILE"
       ```
       This ensures full-session recording (including `vim` edits) and properly restores terminal modes on exit.
     - On macOS (Darwin) or if `script` is unavailable, it falls back to Python’s `pty.spawn(...)` to prevent compatibility issues with BSD `script`.
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
  - **Fixed**: Added a `kubectl cluster-info` pre-flight check before starting any Kubernetes quiz. This check verifies that `kubectl` can communicate with a cluster, preventing exercises from failing on setup commands due to a misconfigured environment. If the check fails, it prints a helpful error message and exits gracefully.
  - **Fixed**: Questions without validation steps are no longer erroneously marked as correct. The answer-checking logic now requires at least one validation step to have been executed and passed; otherwise, the answer is considered incorrect, preventing false positives for malformed questions.
  - **Fixed**: Decoupled "Work on Answer" from "Check Answer" in the quiz loop. Previously, the answer was checked immediately after exiting the shell, which could cause premature 'Incorrect' messages and prevent the user from working on questions. Now, the user must explicitly select "Check Answer" to trigger evaluation.
  - **Fixed**: Restored the interactive `questionary`-based menus for bare `kubelingo` invocations. A UI regression had replaced them with a plain text-based menu. The fix re-implements the rich menu with `use_indicator=True` and dict-based choices, while retaining the text menu as a fallback for non-TTY environments. This resolves the `F821 undefined name 'questionary'` errors.
  - **Fixed**: Removed deprecated live exercise logic to prevent hangs when working on an answer.
  - **Fixed**: Errors during `pre_shell_cmds` are now handled gracefully, preventing quiz crashes.
  - **Fixed**: The `TypeError` on `Question.__init__` was resolved by removing an invalid `type` argument.
  - **Feature**: Questions are now de-duplicated by prompt text after loading to ensure a clean study session.
  - **Feature**: Added a "Show Model Answer" option to the in-quiz menu for questions that have a model response defined.
  - **Feature**: The Vim/YAML editor now displays the exercise prompt before opening the editor and uses a temporary `.vimrc` file to ensure consistent 2-space tabbing.
  - **Feature**: Added `kubectl_common_operations.yaml`, a new quiz based on the official Kubernetes documentation examples. The questions cover common `kubectl` commands and are intended for AI-based evaluation, allowing for flexibility with aliases and command variations.
  - **Feature**: Reorganized `kubectl` quizzes into three distinct topics: Syntax, Operations, and Resource Types. Created new quiz files for each and updated the main menu to reflect the new structure, removing "trick questions" about non-existent resource short names.
  - **Fixed**: Resolved an `ImportError` for a missing configuration variable that occurred after reorganizing the `kubectl` quiz files.
  - **Fixed**: Resolved a bug preventing text-based answers (like for Vim or Kubectl command quizzes) from being evaluated. The quiz flow now consistently requires the user to explicitly select "Check Answer" to trigger evaluation for all question types, ensuring reliability.
  - **Fixed**: Corrected the quiz flow for text-based questions (Vim, commands) to auto-evaluate the answer upon submission, as intended. This also ensures that the expected answer and source citation are displayed immediately, even for correct answers.
  - **Fixed**: Removed faulty pre-processing of Vim commands before AI evaluation. The AI now receives the raw command, allowing it to correctly handle normal-mode commands with mistaken colons (e.g., `:dd`) and properly evaluate command-line mode commands (e.g., `:q!`). This change restores the auto-evaluation workflow and ensures Vim questions display their source citations correctly.
  - **Fixed**: The AI evaluator was incorrectly marking the valid Vim command `:x` as incorrect when the expected answer was `:wq`. The system prompt for Vim quizzes has been updated with a stronger example (`:x` and `:wq` are equivalent) to ensure it correctly identifies command aliases.
  - **Fixed**: Improved AI evaluation for Vim quizzes to be more precise about Vim's modes. The AI will now correctly distinguish between Normal mode (e.g., `dd`) and Command-line mode (e.g., `:w`). It will still accept Normal mode commands mistakenly prefixed with a colon but will provide a gentle correction, enhancing the learning experience.
  - **Fixed**: Standardized the source URL for all Vim quiz questions to point to the official documentation at `https://vimdoc.sourceforge.net/`, removing inconsistent references. This ensures that both AI evaluation and the "Visit Source" action provide a consistent, authoritative reference.
  - **Fixed**: Removed a redundant question from the Vim quiz ("Go to an arbitrary line N") to avoid confusion and improve quiz quality.
  - **Fixed**: Resolved a `TypeError` that could occur when starting a quiz. The issue was caused by `null` values for list-based fields (like `pre_shell_cmds`) in the database. The import script now ensures these fields are always stored as empty lists instead of null, preventing the error. Re-seeding the database with `scripts/import_yaml_to_db.py` will apply the fix.
  - **Fixed**: For Kubernetes questions, the AI evaluator now programmatically prepends `kubectl` to answers that start with a valid subcommand (e.g., `get`, `annotate`) but omit the `kubectl` or `k` prefix. This prevents answers from being marked incorrect for a missing prefix, improving the learning experience.
  - **Fixed**: Clarified several questions in the Helm quiz that were ambiguous or lacked necessary information in the prompt (e.g., a release name or chart name). This ensures that questions can be answered correctly based on the provided text, improving the user experience and fairness of the AI evaluation.
  - **Cleanup**: Standardized the use of backticks for names and commands in Helm quiz prompts and removed a redundant link to improve consistency.
  - **Fixed**: Further clarified Helm quiz questions that rely on a repository (`bitnami`) by explicitly stating in the prompt to assume the repository has already been added. This removes ambiguity and ensures questions provide all necessary context.
  - **Fixed**: Corrected several `kubectl` quizzes (e.g., Service Account Operations) that were incorrectly configured as shell-based exercises. By removing legacy `validation` blocks, these quizzes now correctly use the command-based evaluation flow, prompting users for a single command and using AI for validation, which resolves UI inconsistencies and aligns them with their intended design.
  - **Feature**: Added a new "YAML Editing" quiz with 8 exercises. Kubelingo supports two modes for YAML questions:
    - **Live Kubernetes Edits (`type: live_k8s_edit`)**: These questions use the unified shell experience, providing starter YAML templates in an `initial_files` directory for users to edit and `apply`. Validation is performed by running `kubectl` commands against the live cluster state.
    - **Pure YAML Comparison (`type: yaml_edit`)**: For these questions, the quiz opens a temporary file in `vim` with a starting template. After editing, the final YAML is compared directly against the question's `correct_yaml` definition. This flow does not require a live cluster.
- Next steps: write unit/integration tests for matcher logic and the `answer_checker` module.

## Core Quiz Architecture: Three Question Modalities

To provide a clear and robust learning path, Kubelingo's architecture is centered around three distinct question modalities. This structure ensures that the application can support a wide range of exercises, from conceptual knowledge checks to hands-on, manifest-based challenges. The database schema and application logic must align with these three categories.

### 1. Conceptual Questions

This modality focuses on open-ended, knowledge-based questions designed to foster a deep understanding of Kubernetes concepts, operations, and resources. It serves as the foundation for a "Socratic" tutoring experience.

- **Purpose**: Test theoretical knowledge and reasoning.
- **Examples**: "Explain the role of an init container," "What is the difference between a Service and an Ingress?"
- **User Interaction**: The user provides a text-based explanation.
- **Evaluation**: The answer is evaluated by an AI model for conceptual accuracy and completeness. There is no syntactic validation.
- **Schema Fields**: `id`, `question`, `source`, `explanation` (model answer).

### 2. Command-Based Questions

This modality tests the user's ability to formulate and execute single-line commands for tools like `kubectl`, `helm`, and `vim`.

- **Purpose**: Test practical, imperative command-line skills.
- **Examples**: "Delete a pod named 'my-pod' forcefully," "How do you undo the last change in Vim?"
- **User Interaction**: The user submits a single command.
- **Evaluation**: Answers are evaluated for both conceptual correctness and syntactical validity.
  - **Conceptual**: An AI evaluator checks if the command achieves the desired outcome, understanding aliases and alternative flags (e.g., `kubectl get po` vs. `kubectl get pods`).
  - **Syntactic**: A pre-flight check (e.g., `kubectl --dry-run=client`, or a linter) validates the command's syntax before execution or final evaluation.
- **Schema Fields**: `id`, `question`, `answers` (list of valid commands), `source`, `explanation`.

### 3. Manifest-Based Exercises (Vim-centric)

**This modality is the centerpiece of the Kubelingo learning experience.** It focuses on the declarative, real-world task of authoring and editing Kubernetes YAML manifests. The Vim editor is central to this workflow.

- **Purpose**: Develop proficiency in creating and modifying Kubernetes objects declaratively.
- **User Interaction**: The user is placed directly into a Vim session to work on a YAML file.
- **Sub-types**:
  - **Creation from Scratch**: The user is given a prompt and an empty file (e.g., `pod.yaml`) and must write the complete manifest.
  - **Editing from a Template**: The user is provided with a starter manifest containing errors or missing fields that must be corrected or completed.
- **Evaluation**:
  - For pure YAML editing (`yaml_edit` type), the resulting file content is compared against a correct YAML structure.
  - For live cluster exercises (`live_k8s_edit` type), the user applies the manifest, and validation steps are run against the cluster to check the outcome (e.g., `kubectl get pod my-pod -o jsonpath='{.spec.replicas}'`).
- **Schema Fields**: `id`, `question`, `initial_files` (for templates), `correct_yaml` (for comparison), `validation_steps` (for cluster checks), `source`, `explanation`.

This clear categorization guides all future development, ensuring that the architecture remains focused on delivering a high-quality, multifaceted learning experience with a strong emphasis on practical, manifest-driven skills.

## Data Management Scripts

### `scripts/import_yaml_to_db.py`

This script provides a streamlined way to populate or reset the Kubelingo question database from a directory of YAML source files. It is the designated tool for seeding the database, aligning with the "database-first" architecture.

**Functionality**:
    - **Append-Only**: This script does not delete any existing questions. It uses `INSERT OR REPLACE` to update entries by `id` and append new questions. There is no clear-or-append toggle.
    - **Comprehensive YAML Ingestion**: Recursively finds and parses all `.yaml` and `.yml` files. It can scan multiple source directories in a single run.
    - **Database Population**: Inserts or updates all discovered questions into the live database (`~/.kubelingo/kubelingo.db`).
    - **Automatic Backup**: After each run, it creates or updates the backup at `question-data-backup/kubelingo.db.bak`.

**Usage**:
The script is run from the command line. It can accept multiple source directories.

- To add or update questions from all standard YAML source directories (`question-data/yaml`, `question-data/yaml-bak`, and `question-data/manifests`):
  ```bash
  python3 scripts/import_yaml_to_db.py
  ```
- To import from one or more specific directories:
  ```bash
  python3 scripts/import_yaml_to_db.py --source-dir /path/to/your/yaml/files --source-dir /another/path
  ```
Note: This script always appends or updates questions. To run against defaults or specific paths:
```bash
# import/update all standard YAML sources:
python3 scripts/import_yaml_to_db.py
# import/update specific directories:
python3 scripts/import_yaml_to_db.py --source-dir /path/to/yaml --source-dir /another/path
```

### `scripts/enrich_unseen_questions.py`

This script is designed to expand the question database by leveraging a source file of potential questions. It identifies questions that are not yet in the database and uses AI to generate fully-formed quiz items from them.

**Functionality**:
- **Database Check**: Connects to the live database (`~/.kubelingo/kubelingo.db`) and fetches all existing question prompts.
- **Source Analysis**: Reads a source JSON file (e.g., `question-data/unified.json`) containing a list of questions.
- **Identifies New Content**: Compares prompts from the source file against the database and identifies questions that are "unseen".
- **AI-Powered Generation**: For each unseen question, it uses `AIQuestionGenerator` to create a complete, well-structured question object.
- **YAML Output**: Saves the newly generated questions to a YAML file, ready for review and subsequent import into the database.

**Usage**:
The script is intended to be run from the command line.

- To generate 5 new questions from the default source file and save them:
  ```bash
  python3 scripts/enrich_unseen_questions.py --num-questions 5
  ```
- To perform a dry run that lists unseen questions without calling the AI:
  ```bash
  python3 scripts/enrich_unseen_questions.py --dry-run
  ```
- To specify a different source or output file:
  ```bash
  python3 scripts/enrich_unseen_questions.py \
    --source-file /path/to/source.json \
    --output-file /path/to/output.yaml
  ```
  - By default, when no `--output-file` is provided, the generated questions are saved to `question-data/yaml/ai_generated_new_questions.yaml`.

### `scripts/deduplicate_questions.py`

This script identifies duplicate quiz questions in the live database based on identical prompts. It lists all duplicate entries and, with the `--delete` flag, can remove duplicates while preserving the first occurrence.

**Functionality**:
- Connects to the live database (default `~/.kubelingo/kubelingo.db`).
- Finds prompts appearing more than once.
- Displays `rowid`, `id`, and `source_file` for each duplicate entry.
- With `--delete`, deletes duplicate rows, keeping the earliest entry for each prompt.

**Usage**:

- To list duplicate questions without deleting:
  ```bash
  python3 scripts/deduplicate_questions.py
  ```

- To remove duplicates while keeping the first entry of each prompt:
  ```bash
  python3 scripts/deduplicate_questions.py --delete
  ```

### `scripts/organize_question_data.py`

This script is a powerful, multi-purpose tool for maintaining the question database. It can organize files, de-duplicate questions, and use AI to generate missing explanations and validation steps.

**Functionality**:
- **File Organization**: Cleans up the `question-data` directory by archiving legacy files, renaming core quiz files to a consistent standard, and removing empty directories.
- **AI-Powered Enrichment**: For any question missing an `explanation` or `validation_steps`, it uses the OpenAI API (`gpt-3.5-turbo` for explanations, `gpt-4-turbo` for validation steps) to generate them. This is key to ensuring all questions are self-grading.
- **De-duplication**: Before enrichment, it can check against a reference file (e.g., a master list of questions with explanations) and remove any duplicates from the target file.
- **Flexible & General-Purpose**: The script can operate on different file structures (flat lists or nested categories) and can be targeted at specific files.

**Usage**:
The script is highly configurable via command-line flags.

- To preview all changes without modifying files:
  ```bash
  python3 scripts/organize_question_data.py --dry-run
  ```
- To run only the file organization tasks:
  ```bash
  python3 scripts/organize_question_data.py --organize-only
  ```
- To enrich a specific file (e.g., a new question set) and de-duplicate it against a master file:
  ```bash
  python3 scripts/organize_question_data.py --enrich-only \
    --enrich-file question-data/json/new_questions.json \
    --dedupe-ref-file question-data/json/kubernetes_with_explanations.json
  ```
- To generate AI-scaffolded `validation_steps` for questions missing them (use `--dry-run` to preview):
  ```bash
  python3 scripts/organize_question_data.py --generate-validations --dry-run
  ```
- To target a specific file for validation generation (if not using the default `kubernetes.json`):
  ```bash
  python3 scripts/organize_question_data.py --generate-validations \
    --enrich-file question-data/json/ckad_quiz_data.json
  ```
- Improved error handling for OpenAI API connection issues has been added to provide clearer feedback on network problems.
- The script's import logic is now robust, allowing it to be run as a standalone file. It unconditionally defines `project_root` at the top and inserts it into `sys.path`, fixing previous import errors.

### `scripts/generate_ai_questions.py`

This script provides a way to generate new quiz questions using AI and save them to a YAML file. It is useful for expanding quiz modules with new content that follows a consistent format.

**Functionality**:
- **AI-Powered Generation**: Uses `AIQuestionGenerator` to create new questions on a specified subject.
- **Example-Based Formatting**: Can take an existing quiz from the database as a set of few-shot examples to ensure the generated questions match the desired style, tone, and structure.
- **YAML Output**: Saves the generated questions to a specified YAML file. These questions can then be reviewed and added to the database using other migration scripts.

**Usage**:
- To generate 3 new questions about Service Accounts, using an existing quiz from the database for context, and save them to a new file:
  ```bash
  python scripts/generate_ai_questions.py \
    --subject "Kubernetes Service Accounts" \
    --num-questions 3 \
    --example-source-file kubectl_service_account_operations.yaml \
    --output-file question-data/yaml/ai_generated_sa_questions.yaml
  ```

### `scripts/generate_from_pdf.py`

This script provides a way to generate new quiz questions from a PDF document using AI. It is designed to expand the question bank by processing external materials like study guides while avoiding duplication with existing questions.

**Functionality**:
- **PDF Parsing**: Extracts text content from a given PDF file using the `PyMuPDF` library.
- **Deduplication Context**: Fetches all existing question prompts from the live database to guide the AI in generating unique content.
- **AI Generation**: Sends the extracted text in chunks to an AI model, instructing it to create new questions that are not present in the existing set.
- **YAML Output**: Saves the generated questions to a YAML file for review. It does not modify the database directly.

**Usage**:
First, install the required dependencies:
```bash
pip install pymupdf openai
```
You must also have your `OPENAI_API_KEY` environment variable set.

To run the script:
```bash
python3 scripts/generate_from_pdf.py \
    --pdf-path /path/to/document.pdf \
    --output-file question-data/yaml/generated_questions.yaml
```
After running, review the output YAML file, then use `scripts/import_yaml_to_db.py` to add the new questions to the database.

### `scripts/import_and_backup.py`

This script provides a way to populate the Kubelingo database from a directory of YAML quiz files and then create a backup of the populated database. This is particularly useful for developers who are creating or updating quiz content in YAML format and need to load it into the application's database.

**Functionality**:
- **Import from YAML**: The script scans a specified directory for YAML files (`.yaml` or `.yml`), parses them using `YAMLLoader`, and inserts each question into the live SQLite database (`~/.kubelingo/kubelingo.db`). It uses `INSERT OR REPLACE` logic, so running it multiple times with the same questions will update them in place.
- **Database Backup**: After importing all questions, the script creates a backup of the live database. It copies `~/.kubelingo/kubelingo.db` to `question-data-backup/kubelingo_original.db`. This file serves as the canonical, version-controlled question bank. The main application uses this file to seed a user's local database on first run.

**Usage**:
The script is run from the command line. It takes a `--source-dir` argument pointing to the directory with YAML files, which defaults to `/Users/user/Documents/GitHub/kubelingo/question-data/yaml-bak`.

- To run with the default source directory:
  ```bash
  python3 scripts/import_and_backup.py
  ```
- To specify a different directory:
  ```bash
  python3 scripts/import_and_backup.py --source-dir /path/to/other/yaml/files
  ```

### `scripts/locate_yaml_backups.py`

This utility script locates YAML backup files and can provide detailed information, JSON output, or an AI-generated summary.

**Functionality**:
- **Scanning**: Scans one or more directories. A primary directory can be provided as an argument (defaults to `question-data-backup/`), and additional directories can be specified with `-d` or `--dir`.
- **Filtering**: Can filter files using a regex pattern.
- **Output Formats**: Displays results as formatted text or structured JSON.
- **AI Summary**: Can use an AI model to generate a summary of the located backups.

**Usage**:
To scan the default directory:
```bash
python3 scripts/locate_yaml_backups.py
```
To scan a custom directory and filter by a pattern:
```bash
python3 scripts/locate_yaml_backups.py /path/to/your/backups --pattern ".*_quiz.yaml"
```
To scan multiple directories:
```bash
python3 scripts/locate_yaml_backups.py primary-backups/ --dir secondary-backups/ --dir archives/
```
To get output in JSON format:
```bash
python3 scripts/locate_yaml_backups.py --json
```
To get an AI-generated summary (requires `OPENAI_API_KEY`):
```bash
python3 scripts/locate_yaml_backups.py --ai
```

**Note**: If this script finds no backups when run without arguments, it's likely because the default search path (`question-data-backup/`) is empty or incorrect on your system. You can specify the path to your backup directories directly as an argument to scan the correct location.

### `scripts/yaml_backup_stats.py`

This script provides detailed statistics for YAML backup files, including question counts, category breakdowns, and file metadata. It can operate on a single file or an entire directory.

**Functionality**:
- **Flexible Scanning**: Can analyze a single YAML file or scan a directory for backups. When no path is specified, it uses `backups/index.yaml` to quickly find files in the default backup directories, falling back to a full scan if the index is missing.
- **Filtering**: Supports filtering files by a regex pattern when scanning a directory.
- **Detailed Stats**: Reports total questions, per-category counts, file size, and modification time.
- **Output Formats**: Can display stats in a human-readable format or as structured JSON.
- **AI Summary**: Includes an optional AI-powered feature to summarize the statistics.

**Usage**:
First, ensure dependencies are installed:
```bash
pip install PyYAML openai
```
To analyze a single file:
```bash
python3 scripts/yaml_backup_stats.py /path/to/backup.yaml
```
To scan the default backup directories (uses index for performance):
```bash
python3 scripts/yaml_backup_stats.py
```
To scan a directory and get JSON output:
```bash
python3 scripts/yaml_backup_stats.py /path/to/backups --json
```
To get an AI summary of the stats (requires `OPENAI_API_KEY`):
```bash
python3 scripts/yaml_backup_stats.py /path/to/backups --ai
```
  
### Testing & Observations
- **Core Functionality**: The main quiz loop is stable. The PTY shell now correctly handles terminal input (including `vim` on macOS), resolving the garbled character issue.
- **Quiz Loading**: YAML quiz files are now correctly parsed, and all questions from the "Interactive YAML Exercises" module are loaded as expected.
- **Answer Validation**:
    - `live_k8s_edit` questions are correctly validated against the live cluster state using their `validation_steps`.
    - `yaml_edit` questions are correctly compared against their `correct_yaml` definitions.
- **Gaps**: There are no formal unit or integration tests for the answer-checking logic (`answer_checker`) or the YAML loading/parsing pipeline. All testing so far has been manual via smoke tests.

- **YAML Backup Script Tests**:
    - `locate_yaml_backups.py`: exit code 0, printed "No YAML backup files found in question-data-backup/.".
    - `yaml_backup_stats.py`: without PyYAML installed, printed error "Error: PyYAML is not installed. Please install it" and exited with code 1. After installing PyYAML, exit code 0 and printed "No YAML backup files found in question-data-backup/.".

### CLI Readability & Regression Tests
To guard against mangled output and UI regressions, we recommend:
Options are now: Work on Answer (in Shell), Check Answer, Show Expected Answer(s), Show Model Answer, Flag for Review, Next Question, Previous Question, Exit Quiz
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

## Interactive CLI Flow

> For now, skip the very first screen - we are only evaluating single commands so the distinction between pty and docker does not matter. Disable the 'kustom' option too. Leave it grayed out and unselectable to indicate it will be build later on. What we really want, is a screen that comes up listing quiz modules ('vim' is the only one we have implemented correctly, the rest should be greyed out and disabled, but visible) and it should look like: 1. Vim Quiz 2. Review Flagged 3. Help (just shows all the parser args and menu options etc) 4. Exit App 5. Session Type (visible but disabled) 6. Custom Quiz (visible but disabled) ...(then you can list all other disabled quiz options that were there previously, killercoda, core_concepts, CRDs, pods etc - make sure they are visible but greyed out and disabled)

When `kubelingo` is run without any arguments, it enters a simplified interactive mode. The initial session type selection (PTY/Docker) is skipped, and the user is taken directly to the main quiz selection menu.

This menu displays:
1.  **Vim Quiz**: The primary, active quiz module.
2.  **Review Flagged Questions**: A session with all questions the user has marked for review.
3.  **Help**: Displays help information about command-line arguments and options.
4.  **Exit App**: Quits the application.

Other options like `Session Type`, `Custom Quiz`, and other quiz modules (`killercoda`, `core_concepts`, etc.) are displayed but are disabled and unselectable, indicating they are planned for future implementation.

## AI System Prompts

To ensure consistent and accurate evaluations, Kubelingo uses carefully crafted system prompts to instruct the AI model.

#### For Full-Transcript Evaluation

This prompt is used by the `AIEvaluator.evaluate` method, which assesses a user's entire sandbox session. It provides a holistic view of the user's problem-solving approach.

```
You are an expert Kubernetes administrator and trainer. Your task is to evaluate a user's attempt to solve a problem in a sandboxed terminal environment.
Based on the provided question, the expected validation steps, the terminal transcript, and any associated logs (like vim commands), determine if the user successfully completed the task.
Your response MUST be a JSON object with two keys:
1. "correct": a boolean value (true if the user's solution is correct, false otherwise).
2. "reasoning": a string providing a concise explanation for your decision. This will be shown to the user.
```

#### For Single-Command Evaluation

This prompt is used by the `AIEvaluator.evaluate_command` method, which provides quick, semantic validation for single-line command questions. It is designed to be lightweight and suitable for knowledge checks.

```
You are an expert instructor preparing a student for the Certified Kubernetes Application Developer (CKAD) exam.
Your task is to evaluate a user's attempt to answer a question by providing a single command.
You will be given the question, the user's submitted command, a list of expected correct commands, and sometimes a source URL for documentation.
Your response MUST be a JSON object with two keys:
1. "correct": a boolean value (true if the user's command is a valid and correct way to solve the problem, false otherwise).
2. "reasoning": a string providing a concise explanation for your decision. This will be shown to the user.
- For K8s questions:
  * Any command without `kubectl` or `k` (e.g., `annotate`) is treated as if `kubectl` was prepended (`kubectl annotate`).
  * Commands starting with `k ` (e.g., `k drain`) are normalized to `kubectl drain`.
- Short resource names in kubectl are equivalent (e.g., `po` for `pods`).
- For Vim, allow colon-prefix variations (e.g., `dd` and `:dd`).
If a source URL is provided, please cite it in your reasoning.
```


## Recent Interactive Quiz UI Updates

1. **Answer Question** replaces "Work on Answer" for text-based questions (commands, Vim exercises, non-live k8s).
   - After typing an answer and pressing Enter, the quiz auto-evaluates:
     * Runs the AI or deterministic checker immediately.
     * Displays the AI reasoning in cyan, the canonical expected answer, and the citation URL (including for Vim commands, if a citation is present).
     * Returns to the action menu so the user can `Next Question`, `Visit Source`, or `Flag for Review`.
   - The explicit "Check Answer" menu entry is removed for these question types.

2. **Shell-mode questions** (`live_k8s`, `live_k8s_edit`) use "Work on Answer (in Shell)" followed by a manual "Check Answer" step. The `yaml_edit` question type is similar in that it requires a manual "Check Answer", but it uses the "Answer Question" action to open `vim` directly without an interactive shell.

3. **Navigation** remains manual for all questions:
   - `Next Question` and `Previous Question` are placed above the `Flag for Review` option.
   - No auto-advance on correct—users can review reasoning and citations first.

4. **Quiz Completion** in interactive mode:
   - After summarizing results and cleaning up swap files, the session returns to the main quiz selection menu.
   - In non-interactive (scripted) mode, the quiz loop exits as before.

> **IMPORTANT**: Do not revert these flows or menu orderings. They ensure a consistent, transparent quiz experience and prevent accidental breakage of the unified UI.

## Vim Quiz Mode Clarification
Vim quizzes assume knowledge of Vim's two primary modes:
1. **Normal Mode** (default upon opening Vim):
   - Used for navigation and editing commands such as:
     * `dd` (delete line)
     * `yy` (yank line)
     * `p` (paste)
     * `u` (undo)
     * `n` (next search match)
     * `gg` (go to top), `G` (go to end)
   - These commands do **not** require a leading colon and can be executed directly (after exiting Insert Mode with `Esc`).
2. **Ex (Command-Line) Mode** (entered by typing `:` in Normal Mode):
   - Used for file operations and line-based commands such as:
     * `:w` to save without exiting
     * `:wq`, `:x`, or `ZZ` to save and quit
     * `:q!` to quit without saving
     * `/:pattern` to search forward
     * `:10` to go to line 10
   - In our evaluator, answers may be submitted with or without the leading `:` (e.g., `w` and `:w` both accepted), but represent Ex commands that run after `:`.

 Make sure all Vim quiz questions and expected answers align with these modes:
 - Normal-mode commands should list the key sequence (e.g., `dd`, `yy`).
 - Ex-mode commands should include the command name, and colon-variants are automatically normalized (leading `:` is optional in answer input).

## Standard YAML Quiz Format

To ensure consistent experience across all YAML-based quizzes, each YAML file should adhere to the following schema:

- Top-level: a YAML sequence (`- ...`) of question objects.
- Each question object must include:
  - `id` (string): unique identifier for the question, e.g., `resource::shortname`.
  - `prompt` (string): the question text to present (legacy `question:` keys are supported but deprecated).
  - `type` (string): the question type, e.g., `command`, `live_k8s`, etc.
  - `response` (string): the expected answer or command.
  - `category` (string): category label, e.g., `Kubectl Common Operations`.
  - `citation` (string, optional): URL for reference documentation.
  - `validator` (object, optional): for AI-based validation, with:
    - `type` (string): e.g., `ai`.
    - `expected` (string): expected canonical command or answer.
- Optional fields:
  - `pre_shell_cmds`: list of setup commands to run before the quiz shell.
  - `initial_files`: mapping of filenames to initial file contents.
  - `validation_steps`: list of validation step objects for deterministic checks.
  - `explanation`: explanatory text to display on correct answers.
  - `difficulty`: question difficulty level.

Nested `metadata:` blocks in YAML files are automatically flattened at runtime by the `YAMLLoader`, and legacy `question:` keys are normalized to `prompt:`. New quizzes should use the flat schema shown above to avoid relying on runtime transformations.

## Database-First Architecture

To improve stability and simplify the architecture, Kubelingo now exclusively uses its SQLite database as the source of truth for all quizzes at runtime.

- **No More Direct File Loading**: The application no longer reads questions directly from YAML, JSON, or Markdown files during a quiz session. All quiz content is fetched from the database.
- **YAML as the Source Format**: The YAML files in `question-data/` remain the canonical, version-controlled source for all quiz content.
- **Migration is Required**: Any changes or additions to the YAML quiz files must be imported into the database using a migration script to become available in the application.

This change eliminates a class of bugs related to file parsing and ensures a consistent, reliable data source for all parts of the application.

## How YAML Exercises Are Evaluated

You don’t have to “tell” the quiz which filename you used—all of the wiring happens behind the scenes in the question’s definition. Here’s how it works:

-   **For live k8s edits (`type: live_k8s_edit`)**:
    -   Each question comes pre-loaded with an `initial_files` map (e.g., `pod.yaml` → stub with TODOs).
    -   When you choose “Work on Answer (in Shell),” it drops you into a sandbox whose `cwd` already contains that exact file (`pod.yaml`).
    -   You edit that file, then `kubectl apply -f …`.
    -   On exit, it runs the `validation_steps` (e.g., `kubectl get pod resource-checker …`) against the live cluster state—it never tries to read your local file at that point.

-   **For pure YAML-comparisons (`type: yaml_edit`)**:
    -   The CLI spins up a temporary file and opens it in `vim`.
    -   When you exit `vim`, it reads the temp file’s contents into memory and does a `PyYAML safe_load` vs. the question’s `correct_yaml` field.
    -   You never have to name the file; it’s all handled in the temporary workspace.

In either case, the question’s metadata (`initial_files`, `pre_shell_cmds`, and `validation_steps`) tells the sandbox what to seed and what to check. You just edit & apply as instructed; the quiz will pick up your work via those validation commands or by comparing the in-memory temp file.


## Custom Quiz Length & AI Generation

Kubelingo now supports customizing the number of questions via the `-n/--num` flag:

- If the requested number (`-n N`) is less than or equal to the total available questions, Kubelingo picks a random subset of size N.
- If N exceeds the total available questions, Kubelingo will attempt to generate the remaining questions using an AI model, provided an `OPENAI_API_KEY` is set. This allows for dynamically extending quizzes.
- If AI generation is unavailable or fails, the quiz will proceed with the available static questions.

## Study Mode: AI-Guided Tutoring

You can extend Kubelingo with a “Study Mode” that transforms it into a Socratic, AI-driven tutor for Kubernetes topics:

- Add the `openai` package to your optional dependencies (`pyproject.toml` under `[project.optional-dependencies]`) and install it.
- Create a new module `kubelingo/modules/study_mode.py` containing:
  - A comprehensive multi-line system prompt enforcing a Socratic, step-by-step teaching style tailored to Kubernetes.
  - A `KubernetesStudySession` class that:
    - Initializes an OpenAI client using `OPENAI_API_KEY`.
    - Implements `start_study_session(topic: str, level: str)` to send the system prompt and first user message.
    - Implements `continue_conversation(user_input: str)` to append to conversation history and fetch AI responses.
    - Optionally, a helper `generate_practice_question(topic: str, difficulty: str)` for scenario-based troubleshooting questions.
- Wire it into the CLI (`kubelingo/cli.py`):
  - Add a new `study` subcommand or a `--study` flag.
  - When invoked, prompt the user for the Kubernetes `topic` and their `level`, then call `start_study_session` and enter a loop reading user input and calling `continue_conversation` until the user exits.
- Best practices:
  - Cache only the last ~6 messages in memory to reduce token usage.
  - Use `gpt-3.5-turbo` for cost-effective interactions and reserve `gpt-4` for complex reasoning tasks.
  - Ensure the tutor always ends responses with a guiding question, never full solutions.
  - Persist study session transcripts under `logs/study_sessions/` for later review.

## Importing Questions from Killer Shell Exam Simulators PDF

To extend the quiz with questions derived from the PDF `Killer Shell - Exam Simulators.pdf`:

- A new script `scripts/extract_pdf_questions.py` has been added. It:
  - Uses `pdftotext` to extract text content from the specified PDF.
  - Invokes the AI question generator to produce a user-defined number of candidate questions.
  - Verifies each generated prompt against the existing SQLite database (`~/.kubelingo/kubelingo.db`) to avoid duplicates.
  - Inserts only new, unique questions into the live database under the `killershell` category and marks their `source_file` as the PDF name.
  - Does not move or delete any existing database files or YAML backups.

Usage:
```bash
python scripts/extract_pdf_questions.py "Killer Shell - Exam Simulators.pdf" -n 5
```

After running, you can list or play the new questions by invoking:
```bash
kubelingo --quiz killershell
```

## Importing JSON-Based Questions

To load questions defined in JSON under `question-data/json` into the live database:

- A new script `scripts/import_json_to_db.py` is available. It:
  - Discovers all `*.json` files under `question-data/json`.
  - Uses `JSONLoader` to parse each file into `Question` objects.
  - Inserts or replaces each question into your live SQLite DB (`~/.kubelingo/kubelingo.db`).
  - Optionally clears existing questions with the `--clear` flag before import.

Usage example:
```bash
# Import only JSON questions (appends to existing DB)
python scripts/import_json_to_db.py

# Clear all questions and re-import JSON sources
python scripts/import_json_to_db.py --clear
```

### Viewing and Running JSON-Based Quizzes

Imported JSON quiz files do not show up in the `--quiz` menu (which is reserved for the enabled YAML quizzes). Instead:

- To list all loaded quiz modules (including JSON, YAML, and MD sources):
  ```bash
  kubelingo --list-modules
  # or equivalently
  python scripts/list_db_modules.py
  ```
- To run a specific module directly, use the `--exercise-module` flag with the module name (the JSON filename without extension):
  ```bash
  # For JSON module 'ckad_quiz_data.json', run:
  kubelingo --exercise-module ckad_quiz_data
  ```
- Alternatively, in Kubernetes shortcut mode (`--k8s`), you can select any DB module interactively:
  ```bash
  kubelingo --k8s
  ```
  Then pick from the full list of DB-backed quizzes.

## Enriching Unseen Questions from unified.json

To verify which questions from `question-data/unified.json` are already present in the database and identify any _unseen_ prompts, use the `scripts/enrich_unseen_questions.py` utility. This script:
  - Loads all prompts from `question-data/unified.json`.
  - Queries the live SQLite database (`~/.kubelingo/kubelingo.db`) for existing questions.
  - Reports unseen prompts and, if requested, can invoke the AI question generator to create new questions based on those prompts.

Dry-run mode (no changes, list unseen prompts):
```bash
python3 scripts/enrich_unseen_questions.py --dry-run
```

To generate up to N new AI-based questions for unseen prompts (requires OpenAI API key and PyYAML):
```bash
export OPENAI_API_KEY=your_key_here
pip install pyyaml
python3 scripts/enrich_unseen_questions.py --num-questions N
```
Generated questions are saved to `question-data/yaml/ai_generated_new_questions.yaml` in YAML format.

**Important**:
  - Do not delete or move any database files under `~/.kubelingo/` or backup files in `question-data-backup/`. These are required for seeding, state tracking, and prompt comparison.
  - The script handles missing PyYAML only for dry-run mode; installing PyYAML is necessary for writing the output YAML file.

## Maintenance & Triage Meta-Scripts

We are building a suite of **maintenance and triage meta-scripts** to simplify tracking, exporting, importing, backing up, and cleaning up our question database. These scripts cover:

- **Bug Tracking**: Collect and manage outstanding issues via `scripts/bug_ticket.py` and `docs/bug_tickets.yaml`.
- **YAML Backup Utilities**: Exporting and restoring the database to/from YAML (`scripts/export_db_to_yaml.py`, `scripts/restore_yaml_to_db.py`), locating backups (`scripts/locate_yaml_backups.py`), and viewing stats (`scripts/yaml_backup_stats.py`).
- **SQLite Backup Utilities**: Viewing schema (`scripts/view_sqlite_schema.py`), listing backups (`scripts/locate_sqlite_backups.py`), creating backups (`scripts/create_sqlite_backup.py`), restoring (`scripts/restore_sqlite.py`), and diffing DBs (`scripts/diff_sqlite.py`).
- **Question Data Hygiene**: Deduplicating (`scripts/deduplicate_questions.py`), categorizing (`scripts/categorize_questions.py`), fixing links (`scripts/fix_links.py`), and formatting questions (`scripts/format_questions.py`).

For full details and usage examples, see `docs/maintenance_scripts.md`.
 
### Maintenance & Triage Meta-Scripts

We are building a suite of scripts for tracking and triaging our work, including:
- Bug ticket management
- YAML backup and restore utilities
- SQLite database backup, restore, and diff tools
- Question data hygiene and maintenance (deduplication, categorization, formatting)

For full details and the development plan, see `docs/maintenance_scripts.md`.
  
## Self-Healing & Discovery Roadmap

> Here’s a roadmap for taking our self-healing/discovery story even further—so that no matter how folders move, files vanish or get renamed, the system still “just works.”

1.  **Centralize & Parameterize All Paths**  
    -   In `kubelingo/utils/config.py` expose _only_ helper getters (e.g. `get_all_question_dirs()`, `get_live_db_path()`, `get_yaml_backup_dirs()`, `get_sqlite_backup_dirs()`) and deprecate any literal paths.
    -   Allow overrides via environment variables or CLI flags (e.g. `KUBELINGO_QUESTION_DIRS=/foo:/bar`).
2.  **Refactor Every Script to Use Discovery Helpers**  
    -   Go through all the importers, exporters, backup-listers and switch them to call `discover_*()` from `path_utils` instead of hard-coded dirs.
    -   If no candidates are found, the script should:
        -   print a clear “No files under any of: […]” message
        -   list out what _was_ found (even if zero)
        -   prompt the user to supply a directory or abort.
3.  **Build a Unified “Locate” Command in the CLI**  
    -   Add a `kubelingo locate` subcommand (or `kubelingo doctor`) that exercises all discovery paths and reports:
        -   question dirs & file counts
        -   YAML backups & timestamps
        -   SQLite backups & timestamps
        -   current live DB path & schema version
    -   Agents can call `kubelingo locate questions` to bootstrap everything.
4.  **Maintain an Index of Backups**  
    -   Every time we snapshot a `.db` or dump to YAML, append a record to a simple `backups/index.yaml` (or JSON).
    -   Scripts can read that index to offer interactive selection (“choose one of these 12 backups”).
5.  **Add Automated Smoke Tests & CI Checks**  
    -   Under `tests/`, write a few pytest or shell-based smoke tests that assert:
        -   `discover_question_files()` yields at least one YAML
        -   `discover_yaml_backups()` yields at least one file
        -   `get_live_db_path()` exists and `show_sqlite_schema.py` returns exit code 0
    -   Hook these into CI so any path breakage is caught immediately.
6.  **Graceful Fallbacks & Prompts**  
    -   If a script sees multiple candidate dirs (e.g. two different archives), prompt once: “I found these two question folders—please pick one to import from.”
    -   Cache that choice in a user-config file so you don’t keep being asked.
7.  **Version & Rotate Backups**  
    -   Add a “prune” script (`scripts/prune_backups.py`) to keep only the N most recent backups, so that index files don’t grow indefinitely.
8.  **Surface Discovery in shared_context.md**  
    -   Update the shared context so every new AI agent knows: “Never hard-code; always call `kubelingo.utils.path_utils` functions for question/Data/DB paths.”
9.  **Consolidation & Archive Helpers**  
    -   A script to automatically move any stray YAML under `question-data` into the canonical `questions/` folder (so that new files are always discoverable).
10. **Monitoring & Telemetry**  
    -   Instrument each discovery routine to log “which path won” and “how many files discovered.”
    -   Over time we can spot when users stop storing files in the primary dir and update docs accordingly.

—By layering in discovery helpers, interactive fallbacks, an index of backups, and CI-driven smoke tests, the system becomes truly self-healing. Rapid AI-driven refactors or folder reorganizations simply flow through the same discovery layer, and nothing ever “disappears.” Let me know which of these you’d like to tackle next—I can jump in and start implementing the CLI “locate” command or the backup-index machinery right away.


## Maintenance Toolbox UI

A centralized maintenance script is being developed to provide a unified interface for common data management tasks. The script will present an interactive menu to guide the user.

```
? Select a maintenance task: (Use arrow keys)

   === YAML ===
   ○ Index all Yaml Files in Dir
   ○ Consolidate Unique Yaml Questions
   ○ Locate Previous YAML backup
   ○ Diff YAML Backups
   ○ YAML Statistics
   === Sqlite ===
   ○ Write DB to YAML Backup Version
   ○ Restore DB from YAML Backup Version
   ○ Index all Sqlite files in Dir
   ○ View Database Schema
   ○ Locate Previous Sqlite Backup
   ○ Diff with Backup Sqlite Db
   ○ Create Sqlite Backup Version
   ○ Restore from Sqlite Backup Version
   === Questions ===
   ○ Deduplicate Questions
   ○ Fix Question Categorization
   ○ Fix Documentation Links
   ○ Fix Question Formatting
   === System ===
 » ○ Bug Ticket
   ○ Cancel
```

The `Cancel` option exits the maintenance menu without taking any action, returning to the previous menu or command prompt.

The maintenance toolbox includes the following key YAML utilities:
- **Locate Previous YAML backup**: Finds the most recent YAML backup file based on its timestamp.
- **Diff YAML Backups**: Compares different YAML backup versions to show what has changed. It can compare a range of versions or all of them.
- **YAML Statistics**: Provides a count of questions broken down by exercise type and subject matter type.

#### Sqlite Utilities
- **Write DB to YAML Backup Version**: Exports the live SQLite database to a YAML backup file.
- **Restore DB from YAML Backup Version**: Restores the live database from a specified YAML backup.
- **Index all Sqlite files in Dir**: Scans directories to locate and index all SQLite database files.
- **View Database Schema**: Displays the table structure of the live SQLite database.
- **Locate Previous Sqlite Backup**: Finds the most recent SQLite backup file based on its timestamp.
- **Diff with Backup Sqlite Db**: Compares the live database with a backup version to show differences.
- **Create Sqlite Backup Version**: Creates a timestamped backup of the live SQLite database.
- **Restore from Sqlite Backup Version**: Restores the database from a selected SQLite backup file.

#### Question Utilities
- **Deduplicate Questions**: Identifies and optionally removes duplicate questions from the database.
- **Fix Question Categorization**: Helps in organizing questions into standard categories.
- **Fix Documentation Links**: Checks and corrects documentation URLs within questions.
- **Fix Question Formatting**: Standardizes the formatting of question text and metadata.

#### System Utilities
- **Bug Ticket**: Creates a new bug ticket for tracking issues.

## AI-Powered Question Consolidation and Categorization

As part of the maintenance toolbox, the "Consolidate Unique Yaml Questions" feature will leverage AI to process indexed YAML files. It will generate a unique set of questions, categorized according to a standardized schema. This ensures consistency and enriches the question database.

### Question Schema

#### Exercise Type
- **Basic**: Simple single-word answer with AI feedback.
- **Command**: Syntax evaluation for shell commands.
- **Manifest**: Requires using Vim to author or edit a YAML manifest, which is then evaluated.

#### Subject Matter Type
1. Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)
2. Pod design patterns (initContainers, sidecars, lifecycle hooks)
3. Commands, args, and env (ENTRYPOINT/CMD overrides, env/envFrom)
4. App configuration (ConfigMaps, Secrets, projected & downwardAPI volumes)
5. Probes & health (liveness, readiness, startup; graceful shutdown)
6. Resource management (requests/limits, QoS classes, HPA basics)
7. Jobs & CronJobs (completions, parallelism, backoff, schedules)
8. Services (ClusterIP/NodePort/LoadBalancer, selectors, headless)
9. Ingress & HTTP routing (basic rules, paths, service backends)
10. Networking utilities (DNS in-cluster, port-forward, exec, curl)
11. Persistence (PVCs, using existing StorageClasses, common volume types)
12. Observability & troubleshooting (logs, describe/events, kubectl debug/ephemeral containers)
13. Labels, annotations & selectors (label ops, field selectors, jsonpath)
14. Imperative vs declarative (—dry-run, create/apply/edit/replace/patch)
15. Image & registry use (imagePullPolicy, imagePullSecrets, private registries)
16. Security basics (securityContext, runAsUser/fsGroup, capabilities, readOnlyRootFilesystem)
17. ServiceAccounts in apps (mounting SA, minimal RBAC needed for app access)
18. Scheduling hints (nodeSelector, affinity/anti-affinity, tolerations)
19. Namespaces & contexts (scoping resources, default namespace, context switching)
20. API discovery & docs (kubectl explain, api-resources, api-versions)

You are right. Although the script reports success, the questions are not usable in the application. I've found the reason why.

The problem is that create_sqlite_db_from_yaml.py is assigning the wrong source_file to the questions. The application needs the original source file name to display the questions in the correct quiz categories. Since your consolidated YAML file doesn't contain this information, all questions are being assigned the same source file (consolidated_unique_questions_20250811_144940.yaml), which causes the app to show zero questions for every quiz.

To fix this, I can modify the script to determine the correct source_file from the question's category. The mapping between categories and source files is defined within your project.

To implement this, I need to see the quiz definitions. Please add the following file to the chat:

kubelingo/utils/config.py

Once you provide it, I can create the necessary changes to correctly populate the database.

You are right. Although the script reports success, the questions are not usable in the application. I've found the reason why.

The problem is that create_sqlite_db_from_yaml.py is assigning the wrong source_file to the questions. The application needs the original source file name to display the questions in the correct quiz categories. Since your consolidated YAML file
doesn't contain this information, all questions are being assigned the same source file (consolidated_unique_questions_20250811_144940.yaml), which causes the app to show zero questions for every quiz.

To fix this, I can modify the script to determine the correct source_file from the question's category. The mapping between categories and source files is defined within your project.

To implement this, I need to see the quiz definitions. Please add the following file to the chat:

kubelingo/utils/config.py

Once you provide it, I can create the necessary changes to correctly populate the database.
