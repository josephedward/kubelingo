import os
import sys
import yaml
from pathlib import Path
from dataclasses import asdict

# Add project root to path to allow importing kubelingo modules
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from kubelingo.utils.config import ENABLED_QUIZZES
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

    yaml_files = set(ENABLED_QUIZZES.values())

    print(f"Found {len(yaml_files)} unique YAML quiz files to migrate.")

    for file_path in yaml_files:
        if not os.path.exists(file_path):
            print(f"Warning: File not found, skipping: {file_path}")
            continue

        print(f"Processing {file_path}...")
        try:
            questions: list[Question] = yaml_loader.load_file(file_path)
            for q in questions:
                q_data = {
                    'id': q.id,
                    'prompt': q.prompt,
                    'response': q.response,
                    'category': q.category,
                    'source': q.source,
                    'validation_steps': [asdict(step) for step in q.validation_steps],
                    'validator': q.validator,
                    'source_file': file_path,
                }
                add_question(**q_data)
            total_questions += len(questions)
            print(f"  Migrated {len(questions)} questions.")
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")

    print(f"\nMigration complete. Total questions migrated: {total_questions}")


if __name__ == "__main__":
    migrate()
