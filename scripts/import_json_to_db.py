#!/usr/bin/env python3
"""
Import quiz questions from question-data/json into the Kubelingo database.

Scans all JSON files under question-data/json, parses them via JSONLoader,
and inserts/replaces each question into the live database (~/.kubelingo/kubelingo.db).
Supports a --clear flag to delete existing JSON-sourced questions before import.
After import, backs up the updated database to question-data-backup/kubelingo_original.db.
"""
import os
import sys
import argparse
import shutil

# Add project root to PYTHONPATH
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
sys.path.insert(0, PROJECT_ROOT)

from kubelingo.database import init_db, add_question, get_db_connection
from kubelingo.modules.json_loader import JSONLoader
from kubelingo.utils.config import DATA_DIR, BACKUP_DATABASE_FILE, DATABASE_FILE

def clear_json_questions(conn):
    """Delete all questions whose source_file ends with .json"""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM questions WHERE source_file LIKE '%%.json'")
    deleted = cursor.rowcount
    conn.commit()
    return deleted

def main():
    parser = argparse.ArgumentParser(
        description='Import JSON quizzes into the Kubelingo DB'
    )
    parser.add_argument(
        '--clear', action='store_true', help='Remove existing JSON quizzes before import'
    )
    args = parser.parse_args()

    # Initialize live DB
    init_db()
    # Connect to DB
    conn = get_db_connection()
    total_processed = 0
    # Optionally clear JSON questions
    if args.clear:
        deleted = clear_json_questions(conn)
        print(f"Cleared {deleted} existing JSON-based questions.")

    # Discover JSON files
    json_dir = os.path.join(DATA_DIR, 'json')
    if not os.path.isdir(json_dir):
        print(f"JSON directory not found: {json_dir}")
        return
    loader = JSONLoader()
    files = loader.discover()
    for path in sorted(files):
        name = os.path.basename(path)
        print(f"Importing from {name}...")
        try:
            questions = loader.load_file(path)
        except Exception as e:
            print(f"  Failed to parse {name}: {e}")
            continue
        for q in questions:
            # Serialize validation steps
            vs = [ {'cmd': v.cmd, 'matcher': v.matcher} for v in q.validation_steps ]
            validator = q.validator
            try:
                add_question(
                    id=q.id,
                    prompt=q.prompt,
                    source_file=name,
                    response=q.response,
                    category=(q.categories[0] if q.categories else q.category),
                    source='json',
                    validation_steps=vs,
                    validator=validator,
                )
                total_processed += 1
            except Exception as e:
                print(f"  Could not add {q.id}: {e}")
    conn.close()
    print(f"Imported {total_processed} questions from JSON files.")

    # Backup updated DB
    try:
        shutil.copy2(DATABASE_FILE, BACKUP_DATABASE_FILE)
        print(f"Backed up database to {BACKUP_DATABASE_FILE}")
    except Exception as e:
        print(f"Failed to backup database: {e}")

if __name__ == '__main__':
    main()