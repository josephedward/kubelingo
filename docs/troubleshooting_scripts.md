# Troubleshooting and Maintenance Scripts

This document outlines the purpose and usage of various maintenance and troubleshooting scripts available in Kubelingo. These scripts are designed to be run from the interactive troubleshooting menu.

## System

### Bug Ticket
- **Purpose**: Log an issue, bug, or suggestion for later review. This provides a simple, internal mechanism to track problems without leaving the application.
- **Functionality**: Prompts the user for a one-line summary of an issue and appends it to a log file (`.kubelingo/bug_log.txt`).
- **Existing Script**: None. A new script `scripts/bug_ticket.py` is needed.
- **User Prompt**: `Please enter a one-line description of the bug or issue:`

## YAML Management

### Locate Previous YAML backup
- **Purpose**: Find all YAML backup files in the configured backup directories.
- **Functionality**: Scans directories listed in `YAML_BACKUP_DIRS` and lists all found `.yaml`/`.yml` files.
- **Existing Script**: `scripts/locate_yaml_backups.py`.

### View YAML Backup Statistics
- **Purpose**: Provide a summary of the located YAML backup files.
- **Functionality**: Shows the number of files, total size, and modification date range. This can be extended to provide detailed JSON output or an AI-generated summary.
- **Existing Script**: This functionality is part of `scripts/locate_yaml_backups.py` (using flags like `--json` or `--ai`). The menu provides a sub-menu to access these options.

### Write DB to YAML Backup Version
- **Purpose**: Create a YAML backup of all questions currently in the SQLite database.
- **Functionality**: Exports questions from the database into a single, timestamped YAML file stored in a backup directory.
- **Existing Script**: `scripts/export_db_to_yaml.py`.

### Restore DB from YAML Backup Version
- **Purpose**: Restore questions from a specific YAML backup file or directory into the database.
- **Functionality**: Allows the user to select a YAML file to restore from. The script parses the file and adds the questions to the database, with an option to clear existing data first.
- **Existing Script**: `scripts/restore_yaml_to_db.py`.

## SQLite Database Management

### View Database Schema
- **Purpose**: Display the schema of the live SQLite database tables.
- **Functionality**: Executes a `.schema` command against the database file and prints the output.
- **Existing Script**: None. A new script `scripts/view_database_schema.py` is needed.

### Locate Previous SQLite Backup
- **Purpose**: Find all SQLite database backup files.
- **Functionality**: Scans directories in `SQLITE_BACKUP_DIRS` for `.db` files.
- **Existing Script**: None. A new script `scripts/locate_sqlite_backups.py` is needed.

### Diff with Backup Sqlite Db
- **Purpose**: Compare the live database with a selected backup.
- **Functionality**: Shows differences in schema and data between the live DB and a user-selected backup DB. This could leverage the `sqldiff` command-line utility.
- **Existing Script**: None. A new script `scripts/diff_sqlite_backup.py` is needed.

### Create Sqlite Backup Version
- **Purpose**: Create a timestamped backup of the current live database.
- **Functionality**: Copies the live `kubelingo.db` file to a backup directory with a timestamp in the filename.
- **Existing Script**: None. A new script `scripts/create_sqlite_backup.py` is needed.

### Restore from Sqlite Backup Version
- **Purpose**: Replace the live database with a backup copy.
- **Functionality**: Overwrites the current `kubelingo.db` with a user-selected backup file.
- **Existing Script**: None. A new script `scripts/restore_sqlite_backup.py` is needed.

## Question Hygiene

### Deduplicate Questions
- **Purpose**: Identify and optionally remove duplicate questions from the database.
- **Functionality**: Scans questions in the database and identifies duplicates based on prompt text. Provides an option for interactive deletion.
- **Existing Script**: `scripts/find_duplicate_questions.py`.

### Fix Question Categorization
- **Purpose**: Use AI to review and correct the `schema_category` and `subject` of questions.
- **Functionality**: Iterates through questions, uses an AI model to classify them based on their prompt, and updates the database.
- **Existing Script**: `scripts/reorganize_questions_by_schema.py`.

### Fix Documentation Links
- **Purpose**: Check for and correct broken documentation links within questions.
- **Functionality**: Extracts all URLs from question data and verifies they return a 200 OK status.
- **Existing Script**: `scripts/legacy/check_docs_links.py` provides a basis for a new script `scripts/fix_documentation_links.py`.

### Fix Question Formatting
- **Purpose**: Validate the structure and formatting of questions in the database against the `Question` dataclass.
- **Functionality**: Iterates through questions and checks for missing required fields or incorrect data types.
- **Existing Script**: `scripts/legacy/check_quiz_formatting.py` (for YAML) can be adapted to work against the database in a new script `scripts/fix_question_formatting.py`.
