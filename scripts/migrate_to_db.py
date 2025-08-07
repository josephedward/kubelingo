import os
import sys
import yaml
from pathlib import Path
from dataclasses import asdict

# Add project root to path to allow importing kubelingo modules
# Use ROOT from config for a more reliable path
from kubelingo.utils.config import ENABLED_QUIZZES, ROOT as project_root
sys.path.insert(0, str(project_root))
from kubelingo.database import init_db, add_question
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.question import Question


def migrate():
    """Migrates questions from YAML files to the SQLite database."""
    print("Initializing database...")
    init_db()
    print("Database initialized.")

    yaml_loader = YAMLLoader()
    total_questions = 0

    # Discover all YAML files from the backup directory.
    yaml_dir = Path(project_root) / 'question-data-backup' / 'yaml'
    
    yaml_files = []
    if yaml_dir.is_dir():
        for root, _, files in os.walk(yaml_dir):
            for filename in files:
                if filename.endswith(('.yaml', '.yml')):
                    yaml_files.append(os.path.join(root, filename))
    
    yaml_files = sorted(list(set(yaml_files))) # de-duplicate and sort

    print(f"Found {len(yaml_files)} unique YAML quiz files to migrate from {yaml_dir}.")

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
                    'review': raw_q_data.get('review', False)
                }
                add_question(**q_data)
            total_questions += len(questions_obj)
            print(f"  Migrated {len(questions_obj)} questions.")
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")

    print(f"\nMigration complete. Total questions migrated: {total_questions}")


if __name__ == "__main__":
    migrate()
