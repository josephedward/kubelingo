import os
import sys
import yaml
import shutil
import argparse
from pathlib import Path
from dataclasses import asdict

# Add project root to path to allow importing kubelingo modules
# Use ROOT from config for a more reliable path
from kubelingo.utils.config import ENABLED_QUIZZES, ROOT as project_root, DATABASE_FILE, BACKUP_DATABASE_FILE, DATA_DIR
sys.path.insert(0, str(project_root))
from kubelingo.database import init_db, add_question
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.question import Question


def migrate():
    """Migrates questions from YAML files to the SQLite database."""
    parser = argparse.ArgumentParser(description="Migrates questions from YAML files to the SQLite database.")
    parser.add_argument(
        "--file",
        help="Path to a specific YAML file to migrate. If not provided, migrates all files from ENABLED_QUIZZES."
    )
    args = parser.parse_args()

    print("Initializing database...")
    init_db()
    print("Database initialized.")

    yaml_loader = YAMLLoader()
    total_questions = 0

    yaml_files = []
    if args.file:
        if Path(args.file).exists():
            yaml_files.append(args.file)
        else:
            print(f"Error: File not found at '{args.file}'")
            return
    else:
        # Discover all YAML files from ENABLED_QUIZZES in config
        print("Discovering quiz files from ENABLED_QUIZZES config...")
        for path in ENABLED_QUIZZES.values():
            full_path = project_root / path
            if full_path.exists() and full_path.suffix in ('.yaml', '.yml'):
                yaml_files.append(str(full_path))

    yaml_files = sorted(list(set(yaml_files)))  # de-duplicate and sort

    print(f"Found {len(yaml_files)} unique YAML quiz files to migrate.")

    for file_path in yaml_files:
        print(f"Processing {file_path}...")
        try:
            # Load questions as objects for structured data
            questions_obj: list[Question] = yaml_loader.load_file(file_path)
            
            # Load raw data to get attributes not on the Question dataclass, like 'review'
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_questions_data = yaml.safe_load(f)
            raw_q_map = {
                item.get('id'): item for item in raw_questions_data if isinstance(item, dict)
            }

            for q in questions_obj:
                raw_q_data = raw_q_map.get(q.id, {})
                q_data = {
                    'id': q.id,
                    'prompt': q.prompt,
                    'response': q.response,
                    'category': q.category,
                    'source': getattr(q, 'source', None),
                    'validation_steps': [asdict(step) for step in q.validation_steps],
                    'validator': q.validator,
                    'source_file': os.path.basename(file_path),
                    'review': raw_q_data.get('review', False),
                    'explanation': getattr(q, 'explanation', None)
                }
                add_question(**q_data)
            total_questions += len(questions_obj)
            print(f"  Migrated {len(questions_obj)} questions.")
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")

    print(f"\nMigration complete. Total questions migrated: {total_questions}")

    # Create a backup of the newly migrated database.
    try:
        db_path = os.path.join(DATA_DIR, 'kubelingo.db')
        backup_path = os.path.join(DATA_DIR, 'kubelingo.db.bak')
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)
            print(f"Created a backup of the database at: {backup_path}")
    except Exception as e:
        print(f"Could not create database backup: {e}")


if __name__ == "__main__":
    migrate()
