#!/usr/bin/env python3
"""
Builds the Kubelingo master question database from the consolidated YAML files
in the 'question-data/questions' directory.
"""
import os
import shutil
import sys
import yaml
import sqlite3
import tempfile
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.database import add_question, get_db_connection, init_db
from kubelingo.question import QuestionCategory
from kubelingo.utils.config import (
    DATABASE_FILE,
    QUESTIONS_DIR,
    MASTER_DATABASE_FILE,
    SECONDARY_MASTER_DATABASE_FILE,
)

def import_questions(source_dir: Path, conn: sqlite3.Connection):
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
                # Flatten metadata, giving preference to top-level keys
                if 'metadata' in q_dict and isinstance(q_dict['metadata'], dict):
                    metadata = q_dict.pop('metadata')
                    # Pop unsupported 'links' key from metadata before merging.
                    metadata.pop('links', None)
                    for k, v in metadata.items():
                        if k not in q_dict:
                            q_dict[k] = v

                # Set schema_category based on the question type
                q_type = q_dict.get('type', 'command')
                if q_type in ('yaml_edit', 'yaml_author', 'live_k8s_edit'):
                    q_dict['schema_category'] = QuestionCategory.MANIFEST.value
                elif q_type == 'socratic':
                    q_dict['schema_category'] = QuestionCategory.OPEN_ENDED.value
                else:  # command, etc.
                    q_dict['schema_category'] = QuestionCategory.COMMAND.value

                # The 'type' field from YAML needs to be mapped to 'question_type' for the DB
                if 'type' in q_dict:
                    q_dict['question_type'] = q_dict.pop('type')
                else:
                    q_dict['question_type'] = q_type

                q_dict['source_file'] = file_path.name
                # Preserve any `links` entries in metadata
                links = q_dict.pop('links', None)
                if links:
                    metadata = q_dict.get('metadata')
                    if not isinstance(metadata, dict):
                        metadata = {}
                    metadata['links'] = links
                    q_dict['metadata'] = metadata
                add_question(conn=conn, **q_dict)
                question_count += 1
    print(f"\nImport complete. Added/updated {question_count} questions.")
    return question_count

def backup_database(source_db_path: str):
    """Backs up the given database to create the master copies."""
    live_db_path = Path(source_db_path)
    backup_master_path = Path(MASTER_DATABASE_FILE)
    backup_secondary_path = Path(SECONDARY_MASTER_DATABASE_FILE)

    if not live_db_path.exists():
        print(f"Error: Database not found at '{live_db_path}'. Cannot create backup.")
        return

    print(f"\nBacking up database from '{live_db_path}'...")
    backup_master_path.parent.mkdir(exist_ok=True)
    shutil.copy(live_db_path, backup_master_path)
    print(f"  - Created primary master backup: '{backup_master_path}'")
    shutil.copy(live_db_path, backup_secondary_path)
    print(f"  - Created secondary master backup: '{backup_secondary_path}'")
    print("\nBackup complete.")

def main():
    """Main function to run the build and backup process."""
    print("--- Building Kubelingo Master Question Database ---")

    # Discover question directories dynamically
    from kubelingo.utils.path_utils import get_all_question_dirs
    candidate_dirs = get_all_question_dirs()
    source_path = None
    for d in candidate_dirs:
        p = Path(d)
        if p.is_dir() and (any(p.glob('**/*.yaml')) or any(p.glob('**/*.yml'))):
            source_path = p
            break
    if source_path is None:
        print("\nError: No question YAML files found in any of the candidate directories:")
        for d in candidate_dirs:
            print(f"  - {d}")
        print("Please ensure your question-data directories are populated.")
        sys.exit(1)
    print(f"\nUsing questions from '{source_path}'...")

    print(f"\nStep 1: Preparing live database at '{DATABASE_FILE}'...")
    init_db()
    print("  - Ensured database is initialized for build.")

    print(f"\nStep 2: Importing questions from '{source_path}'...")
    questions_imported = 0
    conn = get_db_connection()
    try:
        questions_imported = import_questions(source_path, conn)
    finally:
        conn.close()

    if questions_imported > 0:
        print(f"\nStep 3: Creating master database backups...")
        backup_database(DATABASE_FILE)
    else:
        print("\nNo questions were imported. Skipping database backup.")

    print("\n--- Build process finished. ---")

if __name__ == "__main__":
    main()
