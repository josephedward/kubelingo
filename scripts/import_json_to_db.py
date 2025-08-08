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
    main()#!/usr/bin/env python3

import argparse
import shutil
import sys
from pathlib import Path

# Ensure the project root is in the Python path
try:
    project_root = Path(__file__).resolve().parents[1]
except IndexError:
    project_root = Path.cwd()
sys.path.insert(0, str(project_root))

from kubelingo.database import add_question, get_db_connection
from kubelingo.modules.json_loader import JSONLoader
from kubelingo.question import Question

# As per shared_context.md, the live database is in ~/.kubelingo
DB_DIR = Path.home() / ".kubelingo"
DB_PATH = DB_DIR / "kubelingo.db"
# Backups are stored in a version-controlled directory
BACKUP_DIR = project_root / "question-data-backup"
BACKUP_PATH = BACKUP_DIR / "kubelingo.db.bak"


def clear_json_questions(conn):
    """Deletes all existing questions sourced from JSON files."""
    print("Clearing existing questions sourced from JSON files from the database...")
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM questions WHERE source_file LIKE '%.json'")
        print("JSON-sourced questions cleared successfully.")
    except Exception as e:
        print(f"Error clearing JSON-sourced questions: {e}", file=sys.stderr)
        raise


def import_questions_from_path(source_path: Path, loader: JSONLoader, conn) -> int:
    """Loads all JSON files from a directory or a single file and writes them to the database."""
    print(f"Searching for JSON files in '{source_path}'...")
    if source_path.is_dir():
        json_files = list(source_path.glob("**/*.json"))
    elif source_path.is_file() and source_path.suffix in [".json"]:
        json_files = [source_path]
    else:
        json_files = []

    if not json_files:
        print("No JSON files found.")
        return 0

    print(f"Found {len(json_files)} JSON files. Importing questions...")

    total_imported = 0
    for file_path in json_files:
        try:
            questions: list[Question] = loader.load_file(str(file_path))
            for q in questions:
                # Based on the Question dataclass and database module, we call add_question
                # with all available fields. getattr is used for safety with optional fields.
                # Ensure list/dict fields default to empty containers instead of None to prevent
                # database NULLs that can cause runtime errors.
                validation_steps = getattr(q, "validation_steps", None)
                pre_shell_cmds = getattr(q, "pre_shell_cmds", None)
                initial_files = getattr(q, "initial_files", None)

                add_question(
                    conn,
                    id=q.id,
                    prompt=q.prompt,
                    source_file=file_path.name,
                    response=getattr(q, "response", None),
                    category=getattr(q, "category", None),
                    source=getattr(q, "source", None),
                    validation_steps=validation_steps or [],
                    validator=getattr(q, "validator", None),
                    review=False,  # New questions are not marked for review by default
                    explanation=getattr(q, "explanation", None),
                    difficulty=getattr(q, "difficulty", None),
                    pre_shell_cmds=pre_shell_cmds or [],
                    initial_files=initial_files or {},
                    question_type=getattr(q, "question_type", "command"),
                )
            total_imported += len(questions)
            print(f"  - Imported {len(questions)} questions from '{file_path.name}'.")
        except Exception as e:
            print(
                f"  - ERROR processing file '{file_path.name}': {e}", file=sys.stderr
            )

    return total_imported


def backup_database():
    """Backs up the live database to the version-controlled backup directory."""
    if not DB_PATH.exists():
        print(
            f"Live database not found at '{DB_PATH}'. Nothing to back up.",
            file=sys.stderr,
        )
        return

    print(f"Backing up live database from '{DB_PATH}'...")
    try:
        BACKUP_DIR.mkdir(exist_ok=True)
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print(f"Database successfully backed up to '{BACKUP_PATH}'.")
    except Exception as e:
        print(f"ERROR: Failed to back up database: {e}", file=sys.stderr)


def main():
    """Main function to orchestrate the import and backup process."""
    parser = argparse.ArgumentParser(
        description="Import JSON quiz questions into the SQLite database and create a backup.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="This script is the canonical way to seed the database from JSON source files.\n"
        "It uses the 'database-first' architecture described in shared_context.md.",
    )
    parser.add_argument(
        "--source-dir",
        dest="source_paths",
        action="append",
        type=Path,
        help="A directory or single JSON file to import. Can be specified multiple times. "
        "If not specified, defaults to scanning 'question-data/json'.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing JSON-sourced questions from the database before importing.",
    )
    args = parser.parse_args()

    source_paths = args.source_paths
    if not source_paths:
        source_paths = [
            project_root / "question-data" / "json",
        ]

    loader = JSONLoader()
    conn = get_db_connection()
    total_imported = 0

    try:
        if args.clear:
            clear_json_questions(conn)

        for path in source_paths:
            if not path.exists():
                print(
                    f"Warning: Source path '{path}' does not exist. Skipping.",
                    file=sys.stderr,
                )
                continue
            total_imported += import_questions_from_path(path, loader, conn)

        conn.commit()
        print(f"\nTransaction committed. Imported a total of {total_imported} questions.")
    except Exception as e:
        conn.rollback()
        print(
            f"\nAn error occurred: {e}. Rolling back database changes.", file=sys.stderr
        )
    finally:
        conn.close()

    if total_imported > 0:
        backup_database()
    else:
        print("\nNo questions were imported. Skipping database backup.")


if __name__ == "__main__":
    main()
