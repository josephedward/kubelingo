#!/usr/bin/env python3

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


def import_json_questions_from_files(
    all_json_files: list[Path], loader: JSONLoader, conn
) -> int:
    """Imports questions from a list of JSON files into the database."""
    total_imported = 0
    for file_path in all_json_files:
        try:
            questions: list[Question] = loader.load_file(str(file_path))
            for q in questions:
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
                    review=False,
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
        epilog="This script appends new questions or updates existing ones in the database. `INSERT OR REPLACE` is used,\n"
        "so existing questions with the same ID will be updated in-place. Questions are never deleted.",
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
        help="Clear all questions from the database before importing. Use with caution.",
    )
    args = parser.parse_args()

    source_paths = args.source_paths
    if not source_paths:
        source_paths = [
            project_root / "question-data" / "json",
        ]

    # Discover all JSON files from all source paths first
    all_json_files = []
    for path in source_paths:
        if not path.exists():
            print(f"Warning: Source path '{path}' does not exist. Skipping.", file=sys.stderr)
            continue
        if path.is_dir():
            all_json_files.extend(list(path.glob("**/*.json")))
        elif path.is_file() and path.suffix in [".json"]:
            all_json_files.append(path)

    if not all_json_files:
        print("No JSON files found to import.")
        return

    print(f"Found {len(all_json_files)} JSON files to process.")

    loader = JSONLoader()
    conn = get_db_connection()
    total_imported = 0

    if args.clear:
        print("Clearing all questions from the database...")
        try:
            conn.execute("DELETE FROM questions")
            conn.commit()
            print("Database cleared successfully.")
        except Exception as e:
            conn.rollback()
            print(f"Error clearing database: {e}", file=sys.stderr)
            conn.close()
            return

    try:
        total_imported = import_json_questions_from_files(
            all_json_files, loader, conn
        )
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
