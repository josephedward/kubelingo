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
                validation_steps_dict = [asdict(step) for step in q.validation_steps] if q.validation_steps else None

                # Accommodate questions that may be missing 'source' or use 'citation' instead.
                source_url = getattr(q, 'source', getattr(q, 'citation', None))

                add_question(
                    id=q.id,
                    prompt=q.prompt,
                    source_file=yaml_file.name,
                    response=q.response,
                    category=q.category,
                    source=source_url,
                    validation_steps=validation_steps_dict,
                    validator=q.validator,
                    review=False  # Defaulting review to False
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
    Backs up the live database to the version-controlled backup location.
    """
    live_db_path = Path.home() / ".kubelingo" / "kubelingo.db"
    backup_dir = project_root / "question-data-backup"
    backup_path = backup_dir / "kubelingo.db"

    if not live_db_path.exists():
        print(f"Error: Live database not found at '{live_db_path}'. Cannot create backup.")
        return

    print(f"\nBacking up live database from '{live_db_path}' to '{backup_path}'...")
    backup_dir.mkdir(exist_ok=True)
    shutil.copy(live_db_path, backup_path)
    print("Backup complete.")


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
        print(f"Error: Source directory '{source_path}' does not exist or is not a directory.")
        sys.exit(1)

    questions_imported = import_questions_from_yaml(source_path)
    if questions_imported > 0:
        backup_database()
    else:
        print("\nNo questions were imported. Skipping database backup.")


if __name__ == "__main__":
    main()
