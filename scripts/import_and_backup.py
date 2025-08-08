#!/usr/bin/env python3

import argparse
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.database import add_question, get_db_connection
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.question import Question


def import_questions_from_yaml(source_dir: Path):
    """
    Scans a directory for YAML files, loads questions, and adds them to the database.
    """
    print(f"Scanning for YAML files in '{source_dir}'...")
    loader = YAMLLoader()
    yaml_files = list(source_dir.glob("*.yaml")) + list(source_dir.glob("*.yml"))

    if not yaml_files:
        print("No YAML files found in the specified directory.")
        return 0

    conn = get_db_connection()
    question_count = 0
    total_files = len(yaml_files)

    for i, yaml_file in enumerate(yaml_files):
        print(f"  - Processing file {i+1}/{total_files}: '{yaml_file.name}'...")
        try:
            questions: list[Question] = loader.load_file(str(yaml_file))
            for q in questions:
                # Prepare fields for add_question, using getattr for safety to prevent errors.
                validation_steps = [asdict(s) for s in q.validation_steps] if getattr(q, 'validation_steps', None) else []

                add_question(
                    conn,
                    id=q.id,
                    prompt=getattr(q, "prompt", ""),
                    source_file=yaml_file.name,
                    response=getattr(q, "response", None),
                    category=getattr(q, "category", None),
                    source=getattr(q, 'source', getattr(q, 'citation', None)),
                    validation_steps=validation_steps,
                    validator=getattr(q, "validator", None),
                    review=False,
                    explanation=getattr(q, "explanation", None),
                    difficulty=getattr(q, "difficulty", None),
                    pre_shell_cmds=getattr(q, "pre_shell_cmds", []),
                    initial_files=getattr(q, "initial_files", {}),
                    question_type=getattr(q, "type", "command")
                )
                question_count += 1
        except Exception as e:
            print(f"    Error processing file {yaml_file.name}: {e}")

    conn.commit()
    conn.close()
    print(f"\nImport complete. Added/updated {question_count} questions from {total_files} files.")
    return question_count


def backup_database():
    """
    Backs up the live database to be the version-controlled 'source of truth'.
    """
    live_db_path = Path.home() / ".kubelingo" / "kubelingo.db"
    backup_dir = project_root / "question-data-backup"
    # This file is the canonical backup the app checks for to prevent re-seeding.
    backup_path = backup_dir / "kubelingo_original.db"

    if not live_db_path.exists():
        print(f"Error: Live database not found at '{live_db_path}'. Cannot create backup.")
        return

    print(f"\nBacking up live database from '{live_db_path}' to '{backup_path}'...")
    backup_dir.mkdir(exist_ok=True)
    shutil.copy(live_db_path, backup_path)
    print(f"Backup complete. '{backup_path.name}' is now the source for seeding the database on first run.")


def main():
    """
    Main function to run the import and backup process.
    """
    parser = argparse.ArgumentParser(
        description="Import questions from YAML files into the database and create a backup."
    )
    parser.add_argument(
        "--source-dir",
        type=str,
        default="/Users/user/Documents/GitHub/kubelingo/question-data/yaml-bak",
        help="The directory containing YAML quiz files to import.",
    )
    args = parser.parse_args()

    source_path = Path(args.source_dir)
    if not source_path.is_dir():
        print(
            f"Warning: Source directory '{source_path}' does not exist or is not a directory.",
            file=sys.stderr,
        )
        sys.exit(0)

    questions_imported = import_questions_from_yaml(source_path)
    if questions_imported > 0:
        backup_database()
    else:
        print("\nNo questions were imported. Skipping database backup.")


if __name__ == "__main__":
    main()
