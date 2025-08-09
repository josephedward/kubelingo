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
from kubelingo.modules.json_loader import JSONLoader
from kubelingo.modules.md_loader import MDLoader
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.question import Question
from kubelingo.utils.config import (
    DATABASE_FILE,
    JSON_QUIZ_DIR,
    MD_QUIZ_DIR,
    YAML_QUIZ_DIR,
    MANIFESTS_DIR,
    MASTER_DATABASE_FILE,
    SECONDARY_MASTER_DATABASE_FILE,
)


def import_all_questions(conn):
    """
    Scans all source directories (JSON, MD, YAML) for questions and adds them to the database.
    """
    loaders = {
        "JSON": (JSONLoader(), Path(JSON_QUIZ_DIR)),
        "Markdown": (MDLoader(), Path(MD_QUIZ_DIR)),
        "YAML": (YAMLLoader(), Path(YAML_QUIZ_DIR)),
        "Manifests (YAML)": (YAMLLoader(), Path(MANIFESTS_DIR)),
    }

    total_questions_imported = 0
    all_source_dirs_exist = True

    for name, (loader, source_dir) in loaders.items():
        if not source_dir.is_dir():
            print(f"Warning: Source directory for {name} not found, skipping: {source_dir}")
            all_source_dirs_exist = False
            continue

        print(f"\nProcessing {name} questions from '{source_dir}'...")
        if name == "JSON":
            files = list(source_dir.glob("**/*.json"))
        elif name == "Markdown":
            files = list(source_dir.glob("**/*.md"))
        else:
            files = list(source_dir.glob("**/*.yaml")) + list(source_dir.glob("**/*.yml"))
        
        if not files:
            print(f"  No files found in '{source_dir}'.")
            continue

        for file_path in files:
            print(f"  - Loading file: {file_path.name}")
            try:
                questions: list[Question] = loader.load_file(str(file_path))
                for q in questions:
                    add_question(conn, **asdict(q))
                    total_questions_imported += 1
            except Exception as e:
                print(f"    Error processing file {file_path.name}: {e}")

    if not all_source_dirs_exist:
        print("\nWarning: One or more source directories were not found. The database may be incomplete.")
    
    conn.commit()
    print(f"\nImport complete. Added/updated {total_questions_imported} questions.")
    return total_questions_imported


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

    # Step 1: Clear the existing live database for a clean build.
    print(f"\nStep 1: Preparing live database at '{DATABASE_FILE}'...")
    if os.path.exists(DATABASE_FILE):
        os.remove(DATABASE_FILE)
        print("  - Removed existing live database for a clean build.")
    init_db()
    print("  - Initialized new empty database.")

    # Step 2: Import all questions from all scattered source directories.
    print(f"\nStep 2: Importing all questions from source directories...")
    conn = get_db_connection()
    questions_imported = 0
    try:
        questions_imported = import_all_questions(conn)
    finally:
        conn.close()

    # Step 3: Create backups if import was successful.
    if questions_imported > 0:
        print(f"\nStep 3: Creating master database backups...")
        backup_database()
    else:
        print("\nNo questions were imported. Skipping database backup.")

    print("\n--- Build process finished. ---")


if __name__ == "__main__":
    main()
