# Kubelingo Maintenance and Management Scripts

This document provides an overview of the command-line tools used for development, maintenance, and data management within the Kubelingo project. These scripts provide a powerful interface for managing YAML and SQLite data sources, generating new content, and ensuring data hygiene.

## The Central Orchestrator: `kubelingo_tools.py`

The primary entry point for most maintenance tasks is `kubelingo_tools.py`. It acts as a unified orchestrator that can be run in two modes:

1.  **Interactive Menu**: Running the script without any arguments launches an interactive menu that guides you through common tasks.
    ```bash
    ./scripts/kubelingo_tools.py
    ```
2.  **Direct Command Execution**: You can call specific subcommands to perform tasks directly. This is useful for scripting and automation.
    ```bash
    # Run the quiz interface
    ./scripts/kubelingo_tools.py quiz

    # Run a generator
    ./scripts/kubelingo_tools.py generate kubectl-operations

    # Dynamically run another script
    ./scripts/kubelingo_tools.py run yaml_manager.py stats
    ```

`kubelingo_tools.py` delegates most of its functionality to the specialized manager scripts detailed below.

---

## Core Management Scripts

The following scripts contain the core logic for managing different aspects of the Kubelingo ecosystem.

### 1. YAML Management (`yaml_manager.py`)

This script is a comprehensive tool for all operations related to YAML question files.

**Usage**: `./scripts/yaml_manager.py [command]`

| Command               | Description                                                                          |
| --------------------- | ------------------------------------------------------------------------------------ |
| `consolidate`         | Finds all YAML files and consolidates unique questions into a single file.           |
| `create-db`           | Populates the SQLite database from specified YAML files.                             |
| `deduplicate`         | Scans a directory for YAML files, finds duplicate questions, and creates a consolidated unique file. |
| `diff`                | Compares two YAML backup files to show changes in questions.                         |
| `export`              | Exports all questions from the SQLite database into a single YAML file.              |
| `import-ai`           | Imports questions from YAML, using an AI model to categorize them.                   |
| `index`               | Creates a central index (`backups/index.yaml`) of all YAML files with metadata.      |
| `init`                | Initializes the database from consolidated YAML backups.                             |
| `restore`             | Restores questions from YAML files into the database, with an option to clear it first. |
| `list-backups`        | Finds and lists all YAML backup files, sorted by modification time.                  |
| `stats`               | Calculates and prints statistics about questions in YAML files (e.g., counts by type and category). |
| `backup-stats`        | Shows detailed statistics for the latest YAML backup file.                           |
| `group-backups`       | Groups legacy backup questions into a 'legacy_yaml' module in the database.          |
| `import-bak`          | Imports questions from the legacy `question-data/yaml-bak` directory into the DB.    |
| `migrate-all`         | Migrates all YAML questions from standard directories to the database.               |
| `migrate-bak`         | Clears the DB and migrates all questions from the `yaml-bak` directory.              |
| `verify`              | Verifies that YAML questions can be imported to a temporary DB and loaded correctly. |
| `organize-generated`  | Consolidates, imports, and cleans up AI-generated YAML questions from a source directory. |

### 2. SQLite Database Management (`sqlite_manager.py`)

This script provides tools for managing the SQLite database (`kubelingo.db`), which serves as the primary data store for questions.

**Usage**: `./scripts/sqlite_manager.py [command]`

| Command                 | Description                                                                              |
| ----------------------- | ---------------------------------------------------------------------------------------- |
| `index`                 | Finds all SQLite files and creates an index file (`backups/sqlite_index.yaml`) with metadata. |
| `schema`                | Displays the full SQL schema of the database.                                            |
| `list`                  | Lists all located SQLite backup files, sorted by modification time.                      |
| `diff`                  | Compares two SQLite databases, showing differences in schema and row counts.             |
| `restore`               | Restores the live database from a selected backup file.                                  |
| `create-from-yaml`      | Populates the database from YAML files (similar to `yaml_manager.py restore`).           |
| `migrate-from-yaml`     | Migrates questions from various YAML source directories into the database.               |
| `build-master`          | Builds the master database from all YAML files in the `questions/` directory.            |
| `normalize-sources`     | Normalizes `source_file` paths in the DB to be just the basename (e.g., `path/to/file.yaml` -> `file.yaml`). |
| `list-modules`          | Lists all distinct `source_file` values in the DB, representing quiz modules.            |
| `prune-empty`           | Scans for and deletes empty (zero-table) SQLite database files.                          |
| `unarchive`             | Moves SQLite files from the `archive/` directory to `.kubelingo/` and prunes old versions. |
| `update-schema-category`| Updates the `schema_category` field in the DB based on the `source_file` name.           |
| `fix-sources`           | Corrects `source_file` paths based on the question's category.                           |

### 3. Question Content Generation (`generator.py`)

This script is used to generate new quiz questions and manifests from various sources.

**Usage**: `./scripts/generator.py [command]`

| Command               | Description                                                                             |
| --------------------- | --------------------------------------------------------------------------------------- |
| `from-pdf`            | Extracts text from a PDF and uses an AI model to generate new quiz questions.             |
| `ai-quiz`             | Generates a small, general-purpose Kubernetes quiz using an AI model.                     |
| `ai-questions`        | Generates questions on a specific subject using an AI model, optionally using existing questions as examples. |
| `resource-reference`  | Generates a static quiz manifest (`resource_reference.yaml`) for Kubernetes resource metadata (API version, shortnames, etc.). |
| `kubectl-operations`  | Generates a static quiz manifest (`kubectl_operations.yaml`) for `kubectl` command names. |
| `service-account`     | Generates a static set of questions related to Kubernetes ServiceAccounts.              |
| `validation-steps`    | Auto-generates `validation_steps` for questions based on their YAML answer.               |
| `manifests`           | Generates YAML quiz manifests and solution files from legacy JSON question data.          |

### 4. Question Data Management (`question_manager.py`)

This script handles high-level maintenance and organization of question data.

**Usage**: `./scripts/question_manager.py [command]`

| Command               | Description                                                              |
| --------------------- | ------------------------------------------------------------------------ |
| `build-index`         | Indexes YAML files and updates the question database. This command ensures the DB is in sync with the latest YAML source files. |

### 5. Data Consolidation (`consolidator.py`)

This script provides tools for archiving data files and an interactive exercise selector.

**Usage**: `./scripts/consolidator.py [command]`

| Command               | Description                                                                              |
| --------------------- | ---------------------------------------------------------------------------------------- |
| `backups`             | Scans the entire project for data files (`.db`, `.sqlite3`, `.yaml`) and moves them into a central `archive/` directory, removing duplicates. |
| `selector`            | Launches an interactive menu to browse and select study topics from the database.        |

### 6. Bug & Issue Tracking (`bug_ticket.py`)

A simple utility for logging issues or ideas without leaving the terminal.

**Usage**: `./scripts/bug_ticket.py`

- Prompts the user for a description, location, and category of an issue.
- Uses the system's `$EDITOR` for detailed, multi-line descriptions.
- Appends the new ticket to `docs/bug_tickets.yaml`.
