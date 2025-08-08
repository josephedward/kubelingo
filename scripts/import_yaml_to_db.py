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
        epilog="By default, this script removes existing questions from the database that originate\n"
        "from the specified source files before re-importing them. Use --append to disable this.\n"
        "It is the canonical way to seed the database from YAML source files.",
    )
    parser.add_argument(
        "--source-dir",
        dest="source_paths",
        action="append",
        type=Path,
        help="A directory or single YAML file to import. Can be specified multiple times. "
        "If not specified, defaults to scanning 'question-data/yaml' and "
        "'question-data/yaml-bak'.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append questions to the database instead of clearing questions from source files first.",
    )
    args = parser.parse_args()

    source_paths = args.source_paths
    if not source_paths:
        source_paths = [
            project_root / "question-data" / "yaml",
            project_root / "question-data" / "yaml-bak",
        ]

    # Discover all YAML files from all source paths first
    all_yaml_files = []
    for path in source_paths:
        if not path.exists():
            print(f"Warning: Source path '{path}' does not exist. Skipping.", file=sys.stderr)
            continue
        if path.is_dir():
            all_yaml_files.extend(list(path.glob("**/*.yaml")))
            all_yaml_files.extend(list(path.glob("**/*.yml")))
        elif path.is_file() and path.suffix in [".yaml", ".yml"]:
            all_yaml_files.append(path)

    if not all_yaml_files:
        print("No YAML files found to import.")
        return

    print(f"Found {len(all_yaml_files)} YAML files to process.")

    loader = YAMLLoader()
    conn = get_db_connection()
    total_imported = 0

    try:
        if not args.append:
            # Delete only questions from the source files we are about to import
            source_file_names = [p.name for p in all_yaml_files]
            if source_file_names:
                placeholders = ','.join('?' for _ in source_file_names)
                sql = f"DELETE FROM questions WHERE source_file IN ({placeholders})"
                
                print(f"Clearing existing questions from {len(source_file_names)} source files...")
                cursor = conn.cursor()
                cursor.execute(sql, source_file_names)
                print(f"Cleared {cursor.rowcount} questions.")

        # Import questions from all discovered files
        for file_path in all_yaml_files:
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
                print(f"  - ERROR processing file '{file_path.name}': {e}", file=sys.stderr)

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
