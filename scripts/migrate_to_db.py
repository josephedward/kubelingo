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
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the existing database before migrating. Use for a full restore."
    )
    args = parser.parse_args()

    print("Initializing database...")
    init_db(clear=args.clear)
    if args.clear:
        print("Database cleared and re-initialized.")
    else:
        print("Database initialized.")

    yaml_loader = YAMLLoader()
    total_questions = 0

    yaml_files = []
    if args.file:
        p = Path(args.file)
        if p.exists():
            yaml_files.append(str(p))
        else:
            print(f"Error: File not found at '{args.file}'")
            return
    else:
        # Discover all YAML/backup files in the configured data directories (yaml and yaml-bak)
        for subdir in ('yaml', 'yaml-bak'):
            quiz_dir = Path(DATA_DIR) / subdir
            print(f"Scanning quiz directory: {quiz_dir}")
            if not quiz_dir.is_dir():
                continue
            for pattern in ('*.yaml', '*.yml', '*.yaml.bak'):
                for p in quiz_dir.glob(pattern):
                    yaml_files.append(str(p))

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

    # Create a backup of the newly migrated database, clearly named in the repo
    try:
        from kubelingo.utils.config import BACKUP_DATABASE_FILE, DATABASE_FILE as USER_DB_FILE
        backup_dir = os.path.dirname(BACKUP_DATABASE_FILE)
        os.makedirs(backup_dir, exist_ok=True)
        # Copy the active user DB (~/.kubelingo/kubelingo.db) into project backup
        shutil.copy2(USER_DB_FILE, BACKUP_DATABASE_FILE)
        print(f"Created a backup of the questions database at: {BACKUP_DATABASE_FILE}")
    except Exception as e:
        print(f"Could not create database backup: {e}")


if __name__ == "__main__":
    migrate()
