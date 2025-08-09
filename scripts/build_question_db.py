#!/usr/bin/env python3
"""
Builds the Kubelingo master question database from the consolidated YAML files
in the 'question-data/questions' directory.
"""
import os
import shutil
import sys
import yaml
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.database import add_question, get_db_connection, init_db
from kubelingo.utils.config import (
    DATABASE_FILE,
    QUESTIONS_DIR,
    MASTER_DATABASE_FILE,
    SECONDARY_MASTER_DATABASE_FILE,
)

def import_questions(conn, source_dir: Path):
    """Loads all questions from YAML files in the source directory and adds them to the database."""
    print(f"Scanning for YAML files in '{source_dir}'...")
    files = list(source_dir.glob("**/*.yaml")) + list(source_dir.glob("**/*.yml"))

    if not files:
        print(f"Error: No YAML files found in '{source_dir}'.")
        print("Please run 'python3 scripts/consolidate_questions.py' first.")
        return 0

    question_count = 0
    for file_path in files:
        print(f"  - Processing '{file_path.name}'...")
        with open(file_path, 'r', encoding='utf-8') as f:
            questions_data = yaml.safe_load(f)
            if not questions_data:
                continue
            for q_dict in questions_data:
                # The 'type' field in YAML maps directly to the 'type' column in the DB.
                add_question(conn, **q_dict)
                question_count += 1
    
    conn.commit()
    print(f"\nImport complete. Added/updated {question_count} questions.")
    return question_count

def backup_database():
    """Backs up the live database to create the master copies."""
    live_db_path = Path(DATABASE_FILE)
    backup_master_path = Path(MASTER_DATABASE_FILE)
    backup_secondary_path = Path(SECONDARY_MASTER_DATABASE_FILE)

    if not live_db_path.exists():
        print(f"Error: Live database not found at '{live_db_path}'. Cannot create backup.")
        return

    print(f"\nBacking up live database from '{live_db_path}'...")
    backup_master_path.parent.mkdir(exist_ok=True)
    shutil.copy(live_db_path, backup_master_path)
    print(f"  - Created primary master backup: '{backup_master_path}'")
    shutil.copy(live_db_path, backup_secondary_path)
    print(f"  - Created secondary master backup: '{backup_secondary_path}'")
    print("\nBackup complete.")

def main():
    """Main function to run the build and backup process."""
    print("--- Building Kubelingo Master Question Database ---")

    source_path = Path(QUESTIONS_DIR)
    if not source_path.is_dir() or not any(source_path.iterdir()):
        print(f"\nError: Consolidated questions directory not found or is empty.")
        print(f"Path: '{source_path}'")
        print("Please run the consolidation script first:")
        print("  python3 scripts/consolidate_questions.py")
        sys.exit(1)

    print(f"\nStep 1: Preparing live database at '{DATABASE_FILE}'...")
    if os.path.exists(DATABASE_FILE):
        os.remove(DATABASE_FILE)
        print("  - Removed existing live database for a clean build.")
    init_db()
    print("  - Initialized new empty database.")

    print(f"\nStep 2: Importing questions from '{source_path}'...")
    conn = get_db_connection()
    questions_imported = 0
    try:
        questions_imported = import_questions(conn, source_path)
    finally:
        conn.close()

    if questions_imported > 0:
        print(f"\nStep 3: Creating master database backups...")
        backup_database()
    else:
        print("\nNo questions were imported. Skipping database backup.")

    print("\n--- Build process finished. ---")

if __name__ == "__main__":
    main()
