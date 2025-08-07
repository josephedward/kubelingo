import os
import sys
import yaml
from pathlib import Path
from dataclasses import asdict

# Add project root to path to allow importing kubelingo modules
# Use ROOT from config for a more reliable path
from kubelingo.utils.config import ENABLED_QUIZZES, ROOT as project_root, DATABASE_FILE, BACKUP_DATABASE_FILE
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
    # Backup the database only if new questions have been added since last backup
    try:
        import sqlite3
        # Count total questions in primary database
        conn = sqlite3.connect(DATABASE_FILE)
        total_primary = conn.cursor().execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        conn.close()
        backup_path = Path(BACKUP_DATABASE_FILE)
        perform_backup = False
        if not backup_path.exists():
            perform_backup = True
            print(f"Backup database not found at {BACKUP_DATABASE_FILE}, creating initial backup...")
        else:
            # Count questions in backup database
            conn_bkp = sqlite3.connect(BACKUP_DATABASE_FILE)
            total_backup = conn_bkp.cursor().execute("SELECT COUNT(*) FROM questions").fetchone()[0]
            conn_bkp.close()
            if total_primary > total_backup:
                perform_backup = True
                print(f"New questions detected ({total_primary} > {total_backup}), updating backup database...")
            else:
                print("No new questions; backup database remains unchanged.")
        if perform_backup:
            backup_dir = backup_path.parent
            backup_dir.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(DATABASE_FILE, BACKUP_DATABASE_FILE)
            print(f"Backup database created/updated at {BACKUP_DATABASE_FILE}")
    except Exception as e:
        print(f"Failed to backup database: {e}")


if __name__ == "__main__":
    migrate()
