scripts/initialize_from_yaml.py
import logging
import sqlite3
import sys
import uuid
import yaml
import subprocess
import json
from pathlib import Path
from time import sleep

# Add project root to path to allow imports from kubelingo
try:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from kubelingo.database import get_db_connection
    from kubelingo.utils.path_utils import get_project_root
except ImportError:
    logging.error("Could not import kubelingo modules. Ensure kubelingo is in PYTHONPATH.")
    def get_project_root():
        return Path.cwd()
    def get_db_connection():
        raise NotImplementedError("kubelingo.database.get_db_connection not available")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def categorize_with_gemini(prompt: str) -> dict:
    """Uses llm-gemini to categorize a question."""
    try:
        result = subprocess.run(
            ["llm", "-m", "gemini-2.0-flash", "-o", "json_object", f"Categorize: {prompt}"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return json.loads(result.stdout)
    except Exception as e:
        logging.error(f"Error categorizing with llm-gemini: {e}")
        return {}

def initialize_from_yaml():
    """
    Initializes the application database from consolidated YAML backups.
    """
    logging.info("Starting database initialization from consolidated YAML backups...")

    try:
        root = get_project_root()
        conn = get_db_connection()
    except Exception as e:
        logging.error(f"Error during initial setup (getting project root or DB connection): {e}")
        return

    backup_dir = root / 'yaml' / 'consolidated_backup'

    if not backup_dir.is_dir():
        logging.warning(f"Consolidated backup directory not found: {backup_dir}")
        logging.warning("Skipping initialization. The application might not have questions.")
        return

    yaml_files = sorted(list(backup_dir.glob('**/*.yaml')) + list(backup_dir.glob('**/*.yml')))
    if not yaml_files:
        logging.info(f"No YAML files found in {backup_dir}. No questions will be loaded.")
        return

    logging.info(f"Found {len(yaml_files)} YAML files to process in {backup_dir}.")

    cursor = conn.cursor()

    try:
        logging.info("Clearing existing questions from the database.")
        retry_count = 0
        while retry_count < 5:
            try:
                cursor.execute("DELETE FROM questions")
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    logging.warning("Database is locked. Retrying...")
                    retry_count += 1
                    sleep(1)
                else:
                    raise
        else:
            logging.error("Failed to clear 'questions' table after multiple retries. Aborting initialization.")
            conn.close()
            return
    except sqlite3.Error as e:
        logging.error(f"Failed to clear 'questions' table: {e}. Aborting initialization.")
        conn.close()
        return

    question_count = 0
    for yaml_file in yaml_files:
        relative_path = yaml_file.relative_to(root)
        logging.info(f"Processing file: {relative_path}")
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if not isinstance(data, list):
                logging.warning(f"YAML file {relative_path} does not contain a list of questions. Skipping.")
                continue

            for question_data in data:
                if not isinstance(question_data, dict):
                    logging.warning(f"Skipping non-dictionary item in {relative_path}")
                    continue

                prompt = question_data.get('prompt')
                if not prompt:
                    logging.warning(f"Skipping question with no prompt in {relative_path}")
                    continue

                logging.info(f"Categorizing question with llm-gemini: '{prompt[:70]}...'")
                categories = categorize_with_gemini(prompt)

                exercise_category = categories.get('exercise_category', 'custom')
                subject_matter = categories.get('subject_matter', 'Unknown')

                q_id = question_data.get('id', str(uuid.uuid4()))

                sql = """
                INSERT INTO questions (id, prompt, response, source_file, category_id, subject_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """
                params = (
                    q_id,
                    prompt,
                    question_data.get('response'),
                    str(relative_path),
                    exercise_category,
                    subject_matter,
                )

                retry_count = 0
                while retry_count < 5:
                    try:
                        cursor.execute(sql, params)
                        break
                    except sqlite3.OperationalError as e:
                        if "database is locked" in str(e):
                            logging.warning("Database is locked. Retrying...")
                            retry_count += 1
                            sleep(1)
                        else:
                            raise
                else:
                    logging.error(f"Failed to insert question {q_id} after multiple retries. Skipping.")
                    continue

                question_count += 1

        except yaml.YAMLError as e:
            logging.error(f"Error parsing YAML file {relative_path}: {e}")
        except sqlite3.Error as e:
            logging.error(f"Database error while processing a question from {relative_path}: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while processing {relative_path}: {e}")
    
    conn.commit()
    conn.close()
    logging.info(f"Database initialization complete. Loaded {question_count} questions.")

if __name__ == "__main__":
    initialize_from_yaml()
