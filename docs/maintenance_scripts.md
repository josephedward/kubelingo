<!-- Documentation: Outline of maintenance and troubleshooting scripts -->
# Maintenance Scripts Overview

This document outlines recommended maintenance and troubleshooting scripts for working with YAML backups, SQLite backups, and question data. For each task, we provide:
- Purpose and description
- Suggested script name and location
- Existing legacy scripts to adapt (if any)
- High-level implementation notes
- Suggested AI interaction prompts (where applicable)

## 1. YAML Backups

- **locate_previous_yaml_backup**
  - Purpose: List available YAML backup files, sorted by timestamp or version.
  - Suggested script: `scripts/locate_yaml_backups.py`
  - Adapt from: `scripts/legacy/group_backup_yaml_questions.py`, `scripts/legacy/import_yaml_bak_questions.py`
  - Notes: Scan `question-data-backup/` (or configured directory) for `*.yaml` files, parse dates, output a table.

- **view_yaml_backup_statistics**
  - Purpose: Compute statistics for a selected YAML backup (e.g., question count, categories, file size).
  - Suggested script: `scripts/yaml_backup_stats.py`
  - Adapt from: parts of `scripts/legacy/migrate_all_yaml_questions.py`
  - Notes: Load backup file, summarize counts by tag/category, display summary table.
  - AI prompts: "Which breakdown would you like? (e.g., by category, by difficulty, by tag)"

- **write_db_to_yaml_backup_version**
  - Purpose: Export current database state as a new YAML backup with versioning metadata.
  - Suggested script: `scripts/export_db_to_yaml.py`
  - Adapt from: `scripts/legacy/migrate_to_db.py`, `scripts/legacy/build_question_db.py`
  - Notes: Dump DB rows into `question-data-backup/YYYYMMDD_HHMMSS.yaml`, include header with version and description.
  - AI prompts: "Please provide a brief description for this backup version:"

- **restore_db_from_yaml_backup_version**
  - Purpose: Restore or merge a specific YAML backup into the active database.
  - Suggested script: `scripts/restore_yaml_to_db.py`
  - Adapt from: `scripts/legacy/restore_all.py`, `scripts/legacy/migrate_from_yaml_bak.py`
  - Notes: Offer merge vs. overwrite mode, validate schema compatibility before applying.
  - AI prompts: 
    - "Would you like to merge backup into existing data or replace it entirely?"
    - "Proceed with potential data overwrite?"

## 2. SQLite Backups

- **view_database_schema**
  - Purpose: Display the current SQLite database schema (tables, columns, indexes).
  - Suggested script: `scripts/view_sqlite_schema.py`
  - Adapt from: none (leverages `sqlite3 .schema`)
  - Notes: Connect to configured DB path, dump schema to console or file.

- **locate_previous_sqlite_backup**
  - Purpose: List existing SQLite backup files by date/version.
  - Suggested script: `scripts/locate_sqlite_backups.py`
  - Adapt from: analogous YAML script, reuse backup directory logic.

- **diff_with_backup_sqlite_db**
  - Purpose: Compare current DB against a backup, highlighting schema and data differences.
  - Suggested script: `scripts/diff_sqlite_backup.py`
  - Adapt from: use `sqldiff` or dump both DBs and diff via unified diff.
  - AI prompts: "Show only schema changes, data changes, or both?"

- **create_sqlite_backup_version**
  - Purpose: Copy current SQLite DB file to backup directory with timestamp/version.
  - Suggested script: `scripts/create_sqlite_backup.py`
  - Adapt from: `scripts/legacy/restore_db_from_backup.py` (reverse logic)
  - Notes: Verify write permissions, confirm destination.
  - AI prompts: "Enter a description or label for this backup:"

- **restore_sqlite_from_backup_version**
  - Purpose: Restore or merge a selected SQLite backup into the current DB.
  - Suggested script: `scripts/restore_sqlite_backup.py`
  - Adapt from: `scripts/legacy/restore_db_from_backup.py`
  - Notes: Warn before destructive overwrite, support optional table-level merge.
  - AI prompts: "Overwrite entire database or merge specific tables?"

## 3. Question Data Maintenance

- **deduplicate_questions**
  - Purpose: Identify and remove or merge duplicate questions in the database.
  - Suggested script: `scripts/deduplicate_questions.py`
  - Adapt from: `scripts/legacy/find_duplicate_questions.py`, `scripts/legacy/consolidate_questions.py`
  - Notes: Use hash or AI similarity to find duplicates, prompt user for resolution.
  - AI prompts:
    - "These questions appear duplicates; select the canonical version or merge fields:"

- **fix_question_categorization**
  - Purpose: Detect miscategorized questions and suggest correct categories.
  - Suggested script: `scripts/fix_question_categories.py`
  - Adapt from: `scripts/reorganize_question_categories.py`, `scripts/legacy/update_schema_category.py`
  - Notes: Use AI to propose new categories based on content, allow user override.
  - AI prompts:
    - "Suggested new category for question '<excerpt>': <category>. Approve or edit?"

- **fix_documentation_links**
  - Purpose: Validate and correct documentation URLs in questions.
  - Suggested script: `scripts/validate_doc_links.py`
  - Adapt from: `scripts/legacy/check_docs_links.py`
  - Notes: Check HTTP status codes, detect broken links, update to canonical URLs.
  - AI prompts:
    - "Link broken at <URL>. Provide replacement or mark as obsolete:"

- **fix_question_formatting**
  - Purpose: Lint and correct formatting issues in question YAML or DB entries.
  - Suggested script: `scripts/lint_fix_question_format.py`
  - Adapt from: `scripts/legacy/check_quiz_formatting.py`
  - Notes: Enforce schema (fields present), normalize indentation, escape sequences.
  - AI prompts:
    - "Field 'difficulty' missing for question '<title>'. Please specify:"

---
### Additional Recommendations
- Consolidate backup logic into a generic `scripts/backup_manager.py` with subcommands for `yaml` and `sqlite`.
- Provide a unified CLI (e.g., `kubelingo maintenance <task>`) to dispatch these scripts.
- Integrate AI client in shared module to standardize prompts and logging.# Maintenance Scripts Documentation

This document outlines the functionality of various maintenance scripts for `kubelingo`. These scripts help manage question data stored in YAML backups and the central SQLite database.

## YAML Backup Management

Scripts for managing YAML-based backups of the question database.

### Locate Previous YAML backup
*   **Purpose**: Find and list available YAML backup files or directories.
*   **Implementation**: This script should search predefined backup locations for YAML files that contain question data.
*   **Existing Scripts**: `scripts/legacy/group_backup_yaml_questions.py` might contain logic for finding YAML files, which can be adapted. The script should look in directories like `question-data-backup/yaml`.

### View YAML Backup Statistics
*   **Purpose**: Analyze a YAML backup and display statistics, such as the number of questions, categories, and types.
*   **Implementation**: The script would parse a specified YAML backup file, count questions, and group them by various fields (`category`, `type`).
*   **Existing Scripts**: No direct script exists, but `kubelingo/modules/yaml_loader.py` contains parsing logic that can be reused.

### Write DB to YAML Backup Version
*   **Purpose**: Export all questions from the SQLite database to a new versioned YAML backup file.
*   **Implementation**:
    1.  Connect to the SQLite database and fetch all questions using `kubelingo.database.get_all_questions()`.
    2.  Group questions by their original `source_file`.
    3.  Write each group of questions into a corresponding YAML file in a new versioned backup directory (e.g., `question-data-backup/yaml/backup-YYYY-MM-DD`).
*   **Existing Scripts**: `scripts/legacy/consolidate_manifests.py` or `scripts/generate_manifests.py` have logic for writing YAML files which could be a starting point.

### Restore DB from YAML Backup Version
*   **Purpose**: Import questions from a YAML backup into the SQLite database. This should be an additive process (merging) by default.
*   **Implementation**:
    1.  User selects a YAML backup version.
    2.  The script uses `kubelingo.modules.yaml_loader.YAMLLoader` to discover and load questions from the backup files.
    3.  For each question, it checks if a question with the same ID already exists in the database.
    4.  It can prompt the user on how to handle duplicates (skip, overwrite, etc.).
    5.  It uses `kubelingo.database.add_question` to insert new questions.
*   **Existing Scripts**: `scripts/legacy/import_yaml_bak_questions.py`, `scripts/legacy/migrate_all_yaml_questions.py`, and `scripts/migrate_yaml_questions.py` are highly relevant and should be consolidated into a single, robust script.

## SQLite Database Management

Scripts for direct maintenance of the `kubelingo.db` SQLite database.

### View Database Schema
*   **Purpose**: Display the schema of the tables in the SQLite database.
*   **Implementation**: The script would connect to the database and print the `CREATE TABLE` statements for all tables.
*   **Existing Scripts**: This is a simple SQL query. No specific script exists, but it can be easily created using `kubelingo.database.get_db_connection()`.

### Locate Previous Sqlite Backup
*   **Purpose**: Find and list available SQLite database backup files.
*   **Implementation**: Search for `.db` files in predefined backup locations (e.g., `question-data-backup/`).
*   **Existing Scripts**: Can be a new simple script. `kubelingo/utils/config.py` defines `MASTER_DATABASE_FILE` and `SECONDARY_MASTER_DATABASE_FILE`, which are backup locations.

### Diff with Backup Sqlite Db
*   **Purpose**: Compare the current active database with a selected backup version and show the differences (new, modified, or deleted questions).
*   **Implementation**:
    1.  Connect to both the active DB and the backup DB.
    2.  Fetch all questions from both.
    3.  Compare the question sets based on ID and content hash (if available) to find differences.
    4.  Present a summary of changes.
*   **Existing Scripts**: No direct script exists. This would need to be written from scratch.

### Create Sqlite Backup Version
*   **Purpose**: Create a timestamped copy of the current SQLite database.
*   **Implementation**: Simply copy the `kubelingo.db` file to a backup directory with a name like `kubelingo-YYYY-MM-DD.db`.
*   **Existing Scripts**: `scripts/legacy/build_question_db.py` contains a `backup_database` function that can be extracted and used.

### Restore from Sqlite Backup Version
*   **Purpose**: Replace the current database with a selected backup file.
*   **Implementation**:
    1.  The user selects a backup file.
    2.  The script replaces the active `kubelingo.db` with the selected backup. It should create a backup of the current DB before overwriting it.
*   **Existing Scripts**: `scripts/legacy/restore_db_from_backup.py` does exactly this.

## Question Data Quality

Scripts for improving the quality and consistency of question data.

### Deduplicate Questions
*   **Purpose**: Find and optionally remove duplicate questions from the database.
*   **Implementation**:
    1.  Find potential duplicates based on fuzzy matching of the `prompt` field.
    2.  Present pairs of potential duplicates to the user for confirmation.
    3.  Optionally delete one of the duplicates.
*   **Existing Scripts**: `scripts/legacy/find_duplicate_questions.py` provides a good starting point. It can be enhanced with AI-based semantic duplicate detection.
*   **AI Prompt**:
    > "Are the following two questions semantically duplicates, meaning they test the same core knowledge? Respond with only 'Yes' or 'No', followed by a brief one-sentence explanation.
    >
    > Question 1: `[PROMPT_1]`
    > Question 2: `[PROMPT_2]`"

### Fix Question Categorization
*   **Purpose**: Ensure all questions have the correct `category` and `subject` based on their content.
*   **Implementation**:
    1.  Iterate through questions with missing or potentially incorrect categories.
    2.  Use an AI model to classify the question based on its prompt and other metadata.
    3.  Update the category in the database.
*   **Existing Scripts**: `scripts/reorganize_schema_by_ai.py` and `scripts/reorganize_question_categories.py` contain the core logic for this. They should be unified into a single tool.
*   **AI Prompt**: The `get_system_prompt` method in `scripts/reorganize_schema_by_ai.py` provides an excellent template. It should describe the available categories (`socratic`, `command`, `yaml_author`, etc.) and ask the AI to choose the most fitting one for a given question prompt.

### Fix Documentation Links
*   **Purpose**: Check for broken documentation links in questions and help fix them.
*   **Implementation**:
    1.  Extract all URLs from the `source` or `prompt` fields of all questions.
    2.  Check each URL for a `200 OK` status code.
    3.  For broken links (e.g., 404), use an AI to suggest a new, valid link based on the question's content.
    4.  Prompt the user to confirm the replacement before updating the database.
*   **Existing Scripts**: `scripts/legacy/check_docs_links.py` (and the test `tests/test_doc_links.py`) contains logic for extracting and checking links. `scripts/legacy/suggest_citations.py` could provide ideas for suggesting new links.
*   **AI Prompt**:
    > "The following documentation link is broken: `[BROKEN_URL]`.
    >
    > Based on the content of the quiz question below, please find the most relevant and up-to-date replacement URL from the official Kubernetes documentation (kubernetes.io).
    >
    > Question Prompt: `[QUESTION_PROMPT]`
    > Answer/Context: `[QUESTION_ANSWER_OR_CONTEXT]`
    >
    > Please provide only the new URL."

### Fix Question Formatting
*   **Purpose**: Validate and fix formatting issues in questions, such as invalid IDs or malformed YAML content.
*   **Implementation**:
    1.  Iterate through all questions.
    2.  For each question, validate the ID format (e.g., kebab-case).
    3.  Validate any YAML content in `template` or `solution` fields.
    4.  If an issue is found, attempt to auto-correct it or flag it for manual review. AI can be used to suggest fixes for complex issues.
*   **Existing Scripts**: `scripts/legacy/check_quiz_formatting.py` and the test `tests/test_quiz_formatting.py` provide validation logic.
*   **AI Prompt** (for YAML correction):
    > "The following YAML content from a quiz question is invalid. Please correct the syntax and structure while preserving the original intent. Provide only the corrected YAML block.
    >
    > Invalid YAML:
    > ```yaml
    > [INVALID_YAML_CONTENT]
    > ```"

## Other Notable Existing Scripts

These are useful scripts from `scripts/legacy` that are not in the new menu but are worth keeping and potentially integrating.

*   `scripts/legacy/update_db_source_paths.py`: This was in the old troubleshooting menu and is important for keeping database `source_file` paths consistent after refactoring or moving question files. It should probably be added to the `Sqlite` or `Questions` menu.
*   `scripts/legacy/enrich_question_sources.py`: Enriches questions with source information. This could be part of a general "Question Enrichment" tool.
