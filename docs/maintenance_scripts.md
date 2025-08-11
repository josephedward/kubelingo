<!-- Maintenance and Troubleshooting Scripts Overview -->
# Maintenance and Troubleshooting Scripts

This document outlines the purpose and intended functionality of various maintenance and troubleshooting scripts in the `scripts/` directory. These scripts help manage question data stored in YAML backups and the central SQLite database.

Scripts are grouped into four categories:
1. System
2. YAML
3. SQLite
4. Questions

For each task, the documentation includes:
- **Purpose**: What the script achieves.
- **Script**: Suggested script filename.
- **Behavior**: High-level description of operations.
- **Existing Scripts**: Reference to legacy or current scripts to adapt.
- **AI Prompts**: Example prompts when AI interaction is required.

---
## 1. System

### Bug Ticket
- **Purpose**: Collect and manage outstanding issues or bug reports.
- **Script**: `scripts/bug_ticket.py` (to be created)
- **Behavior**: Maintains a Markdown or JSON file listing bug tickets, supports adding new entries with descriptions, tags, and status updates.
- **Existing Scripts**: None specifically; could adapt issue management code from project templates.
- **AI Prompts**: "Please describe the bug, including steps to reproduce and any error messages."

---
## 2. YAML Backup Management

### Index All YAML Files
- **Purpose**: Scans all configured question and backup directories to find YAML files and creates a central index file (`backups/index.yaml`) with their metadata.
- **Script**: `scripts/index_yaml_files.py`
- **Behavior**: Uses `get_all_yaml_files()` and `get_all_yaml_backups()` to discover files. For each file, it records the path, size, and last modified time. The index helps other scripts and tools quickly locate relevant files without re-scanning the filesystem.
- **Existing Scripts**: `scripts/index_yaml_files.py`.
- **AI Prompts**: None.

### Locate Previous YAML Backup
- **Purpose**: Find and list YAML backup files containing question data.
- **Script**: `scripts/locate_yaml_backups.py`
- **Behavior**: Scans one or more directories for `*.yaml`/`*.yml` files, supports regex filtering and JSON output.
- **Existing Scripts**: `scripts/locate_yaml_backups.py` (verify and enhance filtering, AI summary options).
- **AI Prompts**: None.

### View YAML Backup Statistics
- **Purpose**: Analyze a YAML backup file and report metrics (total questions, per-category counts, file size, modification time).
- **Script**: `scripts/yaml_backup_stats.py`
- **Behavior**: Loads YAML using `kubelingo.modules.yaml_loader.YAMLLoader`, computes statistics, outputs human-readable or JSON, optionally generates an AI summary.
- **Existing Scripts**: `scripts/yaml_backup_stats.py` (ensure all imports, including `Counter`, are correct).
- **AI Prompts**: "Would you like a natural-language summary of these statistics?"

### Write DB to YAML Backup Version
- **Purpose**: Export current SQLite database questions into a versioned YAML backup.
- **Script**: `scripts/export_db_to_yaml.py`
- **Behavior**: Initializes or connects to DB via `init_db()`, fetches questions with `get_all_questions()`, writes YAML to `question-data-backup/<timestamp>.yaml` or specified path.
- **Existing Scripts**: `scripts/export_db_to_yaml.py` (remove duplicate code blocks, use `yaml.safe_dump`, handle output paths correctly).
- **AI Prompts**: "Provide an optional description or label for this backup:"

### Restore DB from YAML Backup Version
- **Purpose**: Import or merge questions from a YAML backup into the active database.
- **Script**: `scripts/restore_yaml_to_db.py`
- **Behavior**: Parses YAML with `yaml.safe_load`, maps `'type'` to `question_type`, optionally clears DB (`--clear`), calls `add_question()` for each entry, reports summary.
- **Existing Scripts**: `scripts/restore_yaml_to_db.py` (add key renaming, filter unexpected kwargs).
- **AI Prompts**:
  - "Clear existing database before restoring? (yes/no)"
  - "How should duplicate question IDs be handled? [merge|overwrite|skip]"

---
## 3. SQLite Database Management

### Index All SQLite Files
- **Purpose**: Scans the entire project repository to find all SQLite database files (`*.db`).
- **Script**: `scripts/index_sqlite_files.py`
- **Behavior**: Uses `get_all_sqlite_files_in_repo()` to find all database files. It prints a list of the located files. Unlike the YAML indexer, it does not currently write to an index file but provides a quick way to list all discoverable databases.
- **Existing Scripts**: `scripts/index_sqlite_files.py`.
- **AI Prompts**: None.

### View Database Schema
- **Purpose**: Display the schema of the SQLite database (tables, columns, indexes).
- **Script**: `scripts/view_sqlite_schema.py`
- **Behavior**: Connects to configured DB file, runs `PRAGMA table_info()` or dumps `.schema`, outputs to console or file.
- **Existing Scripts**: None; implement as small helper using `kubelingo.database.get_db_connection()`.
- **AI Prompts**: None.

### Locate Previous SQLite Backup
- **Purpose**: List available SQLite backup files by timestamp or version.
- **Script**: `scripts/locate_sqlite_backups.py`
- **Behavior**: Scans `question-data-backup/` for `.db` files, outputs metadata in table or JSON.
- **Existing Scripts**: None; could reuse logic from `locate_yaml_backups.py`.
- **AI Prompts**: None.

### Diff with Backup SQLite DB
- **Purpose**: Compare the active database against a backup to identify schema or data changes.
- **Script**: `scripts/diff_sqlite_backup.py`
- **Behavior**: Uses `sqldiff` or dumps both DBs to SQL, runs a unified diff, summarizes differences.
- **Existing Scripts**: None; consider invoking external `sqldiff` tool or Python difflib.
- **AI Prompts**: "Show schema changes, data changes, or both?"

### Create SQLite Backup Version
- **Purpose**: Create a timestamped copy of the current SQLite database file.
- **Script**: `scripts/create_sqlite_backup.py`
- **Behavior**: Copies `kubelingo.db` from app directory to `question-data-backup/` with a timestamped filename, supports `--label`.
- **Existing Scripts**: None.
- **AI Prompts**: "Enter a label or description for this backup (optional):"

### Restore from SQLite Backup Version
- **Purpose**: Restore or merge from a selected SQLite backup into the active database.
- **Script**: `scripts/restore_sqlite_backup.py`
- **Behavior**: Offers options to overwrite the entire DB or merge specific tables, prompts user before destructive operations.
- **Existing Scripts**: None; can reuse file-copy logic and possibly integrate `add_question()` for table-level merging.
- **AI Prompts**: "Overwrite entire database or merge table-by-table?"

---
## 4. Question Data Maintenance

### Deduplicate Questions
- **Purpose**: Identify and resolve duplicate questions in the database or YAML backups.
- **Script**: `scripts/deduplicate_questions.py`
- **Behavior**: Computes hashes or uses AI similarity to group duplicates, prompts user to choose or merge.
- **Existing Scripts**: `scripts/legacy/find_duplicate_questions.py`.
- **AI Prompts**: "These questions look similar; select canonical version or merge fields:"

### Fix Question Categorization
- **Purpose**: Ensure all questions in the database have a consistent `schema_category` based on their type and content.
- **Script**: `scripts/reorganize_question_categories.py`
- **Behavior**: Iterates through all questions in the database, determines the correct schema category based on the logic in the `Question` dataclass, and updates the database. It reports on any quiz files that contain questions with mixed categories.
- **Existing Scripts**: `scripts/reorganize_question_categories.py`.
- **AI Prompts**: None.

### Fix Documentation Links
- **Purpose**: Validate and repair broken documentation URLs in question metadata.
- **Script**: `scripts/validate_doc_links.py`
- **Behavior**: Performs HTTP HEAD requests for each URL, flags broken links, suggests replacements via AI or known patterns.
- **Existing Scripts**: None; may adapt link-checking logic from web frameworks.
- **AI Prompts**: "Link {url} returned {status}; provide an updated URL or mark as deprecated:"

### Fix Question Formatting
- **Purpose**: Lint and correct formatting issues in question definitions (YAML or DB).
- **Script**: `scripts/lint_fix_question_format.py`
- **Behavior**: Enforces required fields, normalizes YAML indentation, escapes characters, updates entries in place.
- **Existing Scripts**: None; can leverage `kubelingo.modules.yaml_loader` validation logic.
- **AI Prompts**: "Field '{field}' is missing for question '{id}'; please provide a value:"

---
## Additional Recommendations
- Consolidate common backup logic into a single `scripts/backup_manager.py` with subcommands for `yaml` and `sqlite`.
- Consider a unified CLI entrypoint (e.g., `kubelingo maintenance <task>`) rather than individual scripts.
- Centralize AI integration in a shared module for consistent prompts, logging, and error handling.
