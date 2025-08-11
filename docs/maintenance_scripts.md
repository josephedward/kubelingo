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
- Integrate AI client in shared module to standardize prompts and logging.