import logging
import sqlite3
from pathlib import Path

import yaml

from kubelingo.database import add_question, get_db_connection
from kubelingo.utils.path_utils import find_and_sort_files_by_mtime, get_project_root

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TYPE_TO_CATEGORY_ID = {
    'socratic': 'basic',
    'command': 'command',
    'manifest': 'manifest',
}


def bootstrap_on_startup():
    """
    Main function to run the bootstrap process. It finds the latest YAML backup,
    clears the database, and repopulates it with questions from the YAML file.
    """
    logging.info("Starting bootstrap process from consolidated YAML backup.")

    project_root = get_project_root()
    backup_dir = project_root / 'yaml' / 'consolidated_backup'

    if not backup_dir.is_dir():
        logging.warning(f"Backup directory not found: {backup_dir}. Skipping bootstrap.")
        return

    logging.info(f"Searching for latest backup in {backup_dir}...")
    yaml_backups = find_and_sort_files_by_mtime([str(backup_dir)], extensions=['.yaml', '.yml'])

    if not yaml_backups:
        logging.warning(f"No YAML backups found in {backup_dir}. Skipping bootstrap.")
        return

    latest_backup_path = Path(yaml_backups[0])
    logging.info(f"Found latest backup: {latest_backup_path}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        logging.info("Clearing existing questions from the database.")
        cursor.execute("DELETE FROM questions")
        conn.commit()

        logging.info(f"Loading questions from {latest_backup_path}...")
        with open(latest_backup_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not isinstance(data, list):
            logging.error(f"Expected a list of questions in {latest_backup_path}, but got {type(data)}. Aborting.")
            conn.close()
            return

        question_count = 0
        for q in data:
            if not isinstance(q, dict) or 'id' not in q:
                logging.warning(f"Skipping invalid item in YAML: {q}")
                continue

            q_id = q.get('id')
            logging.info(f"Processing question with id: {q_id}")

            add_question(
                id=q_id,
                prompt=q.get('prompt'),
                source_file=str(latest_backup_path),
                response=q.get('answer'),
                category=q.get('category'),  # This is for subject_id
                source=q.get('source'),
                validation_steps=q.get('validation_steps'),
                validator=q.get('validator'),
                review=q.get('review', False),
                conn=conn
            )

            # Now, update the category_id (Exercise Category)
            yaml_type = q.get('type')
            category_id = TYPE_TO_CATEGORY_ID.get(yaml_type)

            if category_id:
                logging.info(f"Setting exercise category to '{category_id}' for question {q_id}")
                cursor.execute("UPDATE questions SET category_id = ? WHERE id = ?", (category_id, q_id))
            else:
                logging.warning(f"No exercise category mapping found for type '{yaml_type}' in question {q_id}")

            question_count += 1

        conn.commit()
        conn.close()
        logging.info(f"Successfully processed and loaded {question_count} questions.")
        logging.info("Bootstrap process completed successfully.")

    except sqlite3.Error as e:
        logging.error(f"Database error during bootstrap: {e}")
    except FileNotFoundError:
        logging.error(f"Backup file not found: {latest_backup_path}")
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML file {latest_backup_path}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during bootstrap: {e}", exc_info=True)
