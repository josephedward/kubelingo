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
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.question import Question

# As per shared_context.md, the live database is in ~/.kubelingo
DB_DIR = Path.home() / ".kubelingo"
DB_PATH = DB_DIR / "kubelingo.db"
# Backups are stored in a version-controlled directory
BACKUP_DIR = project_root / "question-data-backup"
BACKUP_PATH = BACKUP_DIR / "kubelingo.db.bak"


def clear_questions_table(conn):
    """Deletes all existing questions from the database to prepare for a fresh import."""
    print("Clearing existing questions from the database...")
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM questions")
        print("Questions table cleared successfully.")
    except Exception as e:
        print(f"Error clearing questions table: {e}", file=sys.stderr)
        raise  # Re-raise to trigger rollback in main


def import_questions_from_path(source_path: Path, loader: YAMLLoader, conn) -> int:
    """Loads all YAML files from a directory or a single file and writes them to the database."""
    print(f"Searching for YAML files in '{source_path}'...")
    if source_path.is_dir():
        yaml_files = list(source_path.glob("**/*.yaml")) + list(
            source_path.glob("**/*.yml")
        )
    elif source_path.is_file() and source_path.suffix in [".yaml", ".yml"]:
        yaml_files = [source_path]
    else:
        yaml_files = []

    if not yaml_files:
        print("No YAML files found.")
        return 0

    print(f"Found {len(yaml_files)} YAML files. Importing questions...")

    total_imported = 0
    for file_path in yaml_files:
        try:
            questions: list[Question] = loader.load_file(str(file_path))
            for q in questions:
                # Based on the Question dataclass and database module, we call add_question
                # with all available fields. getattr is used for safety with optional fields.
                add_question(
                    conn,
                    id=q.id,
                    prompt=q.prompt,
                    source_file=file_path.name,
                    response=getattr(q, "response", None),
                    category=getattr(q, "category", None),
                    source=getattr(q, "source", None),
                    validation_steps=getattr(q, "validation_steps", None) or [],
                    validator=getattr(q, "validator", None),
                    review=False,  # New questions are not marked for review by default
                    explanation=getattr(q, "explanation", None),
                    difficulty=getattr(q, "difficulty", None),
                    pre_shell_cmds=getattr(q, "pre_shell_cmds", None) or [],
                    initial_files=getattr(q, "initial_files", None) or {},
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
        description="Import YAML quiz questions into the SQLite database and create a backup.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="This script clears the existing questions table before importing new ones.\n"
        "It is the canonical way to seed the database from YAML source files.\n"
        "It uses the 'database-first' architecture described in shared_context.md.",
    )
    parser.add_argument(
        "--source-path",
        type=Path,
        default=Path("/Users/user/Documents/GitHub/kubelingo/question-data/yaml-bak"),
        help="The directory or single YAML file to import.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append questions to the database instead of clearing it first.",
    )
    args = parser.parse_args()

    if not args.source_path.exists():
        print(
            f"Warning: Source path '{args.source_path}' does not exist.",
            file=sys.stderr,
        )
        sys.exit(0)

    loader = YAMLLoader()
    conn = get_db_connection()
    total_imported = 0

    try:
        if not args.append:
            clear_questions_table(conn)
        total_imported = import_questions_from_path(args.source_path, loader, conn)
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
