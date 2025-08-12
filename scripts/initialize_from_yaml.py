import logging
import sqlite3
import sys
import uuid
import yaml
from pathlib import Path

# Add project root to path to allow imports from kubelingo
# This makes the script runnable from anywhere
try:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from kubelingo.database import get_db_connection
    from kubelingo.utils.path_utils import get_project_root
except ImportError:
    # Fallback for when script is run standalone without kubelingo in path
    logging.error("Could not import kubelingo modules. Ensure kubelingo is in PYTHONPATH.")
    def get_project_root():
        return Path.cwd()
    def get_db_connection():
        raise NotImplementedError("kubelingo.database.get_db_connection not available")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Mapping from YAML 'type' to database 'Exercise Category' as per shared_context.md
# and logic in kubelingo/question.py.
TYPE_TO_EXERCISE_CATEGORY = {
    'socratic': 'basic',
    'command': 'command',
    'live_k8s': 'command',
    'manifest': 'manifest',  # category name, could be legacy type
    'yaml_author': 'manifest',
    'yaml_edit': 'manifest',
    'live_k8s_edit': 'manifest'
}

def initialize_from_yaml():
    """
    Initializes the application database from consolidated YAML backups.
    It clears the existing questions and rebuilds them from YAML sources
    based on the schema in shared_context.md.
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
        cursor.execute("DELETE FROM questions")
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

                yaml_type = question_data.get('type')
                
                # Logic from kubelingo/question.py __post_init__
                source_filename = yaml_file.name
                if source_filename in ('general_operations.yaml', 'resource_types_reference.yaml'):
                    exercise_category = 'basic'
                else:
                    exercise_category = TYPE_TO_EXERCISE_CATEGORY.get(yaml_type)
                
                subject_matter = question_data.get('category')

                if not exercise_category:
                    logging.warning(f"Question in {relative_path} has unknown or missing type '{yaml_type}'. Defaulting to 'command'.")
                    exercise_category = 'command'

                q_id = question_data.get('id', str(uuid.uuid4()))
                response = question_data.get('response')
                
                # Per instructions, using schema from shared_context.md.
                # This assumes 'questions' table has 'category_id' and 'subject_id' columns.
                sql = """
                INSERT INTO questions (id, prompt, response, source_file, category_id, subject_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """
                params = (
                    q_id,
                    prompt,
                    response,
                    str(relative_path),
                    exercise_category,
                    subject_matter
                )
                
                cursor.execute(sql, params)
                question_count += 1

        except yaml.YAMLError as e:
            logging.error(f"Error parsing YAML file {relative_path}: {e}")
        except sqlite3.Error as e:
            logging.error(f"Database error while processing a question from {relative_path}: {e}")
            logging.error(f"Problematic question data might be: {question_data}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while processing {relative_path}: {e}")
    
    conn.commit()
    conn.close()
    logging.info(f"Database initialization complete. Loaded {question_count} questions.")

if __name__ == "__main__":
    # This allows running the script directly for testing or manual initialization.
    initialize_from_yaml()
