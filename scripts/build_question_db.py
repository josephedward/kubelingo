#!/usr/bin/env python3
"""
Builds the Kubelingo master question database from all source YAML files.

This script provides the canonical workflow for developers to create the distributable
database from the consolidated YAML question sources. It performs these key actions:

1.  Clears the existing live user database (`~/.kubelingo/kubelingo.db`) to ensure a fresh build.
2.  Discovers all YAML files in the unified backup directory (`question-data/yaml-backups`).
3.  Loads all questions from these files and inserts them into the live database.
4.  Creates two immutable, version-controlled backups of the newly populated database:
    - `question-data-backup/kubelingo_master.db` (primary)
    - `question-data-backup/kubelingo_master.db.bak` (secondary)

These backup files are used to seed new installations of the application.
"""
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.database import add_question, get_db_connection, init_db
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.question import Question
from kubelingo.utils.config import (
    DATABASE_FILE,
    YAML_BACKUPS_DIR,
    MASTER_DATABASE_FILE,
    SECONDARY_MASTER_DATABASE_FILE,
)


def import_questions_from_yaml(source_dir: Path):
    """
    Scans a directory for YAML files, loads questions, and adds them to the database.
    """
    print(f"Scanning for YAML files in '{source_dir}'...")
    if not source_dir.is_dir():
        print(f"Error: Source directory '{source_dir}' does not exist.")
        print("Please create it and populate it with your question YAML files.")
        return 0

    loader = YAMLLoader()
    yaml_files = list(source_dir.glob("**/*.yaml")) + list(source_dir.glob("**/*.yml"))

    if not yaml_files:
        print(f"No YAML files found in '{source_dir}'.")
        return 0

    conn = get_db_connection()
    question_count = 0
    total_files = len(yaml_files)

    print(f"Found {total_files} YAML files to process.")
    for i, yaml_file in enumerate(yaml_files):
        print(f"  - Processing file {i+1}/{total_files}: '{yaml_file.name}'...")
        try:
            questions: list[Question] = loader.load_file(str(yaml_file))
            for q in questions:
                # add_question uses INSERT OR REPLACE, which is what we want.
                add_question(conn, **asdict(q))
                question_count += 1
        except Exception as e:
            print(f"    Error processing file {yaml_file.name}: {e}")

    conn.commit()
    conn.close()
    print(f"\nImport complete. Added/updated {question_count} questions from {total_files} files.")
    return question_count


def backup_database():
    """
    Backs up the live database to create the immutable, version-controlled master copies.
    """
    live_db_path = Path(DATABASE_FILE)
    backup_master_path = Path(MASTER_DATABASE_FILE)
    backup_secondary_path = Path(SECONDARY_MASTER_DATABASE_FILE)

    if not live_db_path.exists():
        print(f"Error: Live database not found at '{live_db_path}'. Cannot create backup.")
        return

    print(f"\nBacking up live database from '{live_db_path}'...")
    backup_master_path.parent.mkdir(exist_ok=True)

    # Create primary master backup
    shutil.copy(live_db_path, backup_master_path)
    print(f"  - Created primary master backup: '{backup_master_path}'")

    # Create secondary master backup
    shutil.copy(live_db_path, backup_secondary_path)
    print(f"  - Created secondary master backup: '{backup_secondary_path}'")

    print("\nBackup complete. These files will be used to seed new application installations.")


def main():
    """
    Main function to run the import and backup process.
    """
    print("--- Building Kubelingo Master Question Database ---")

    # Safety Check: Ensure the source YAML directory exists before proceeding.
    source_path = Path(YAML_BACKUPS_DIR)
    if not source_path.is_dir():
        print(f"\n{'-'*60}")
        print(f"Error: Source directory for questions not found.")
        print(f"Path: '{source_path}'")
        print("Please ensure this directory exists and contains your YAML quiz files.")
        print(f"{'-'*60}\n")
        sys.exit(1)

    # Step 1: Clear the existing live database for a clean build.
    print(f"\nStep 1: Preparing live database at '{DATABASE_FILE}'...")
    if os.path.exists(DATABASE_FILE):
        os.remove(DATABASE_FILE)
        print("  - Removed existing live database for a clean build.")
    init_db()
    print("  - Initialized new empty database.")

    # Step 2: Import all questions from the unified YAML backup directory.
    print(f"\nStep 2: Importing questions from '{YAML_BACKUPS_DIR}'...")
    questions_imported = import_questions_from_yaml(source_path)

    # Step 3: Create backups if import was successful.
    if questions_imported > 0:
        print(f"\nStep 3: Creating master database backups...")
        backup_database()
    else:
        print("\nNo questions were imported. Skipping database backup.")

    print("\n--- Build process finished. ---")


if __name__ == "__main__":
    main()
