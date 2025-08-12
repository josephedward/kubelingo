import logging
import sqlite3
from pathlib import Path

import yaml

from kubelingo.database import add_question, get_db_connection
from kubelingo.modules.question_generator import AIQuestionGenerator
from kubelingo.utils.path_utils import find_and_sort_files_by_mtime, get_project_root

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def bootstrap_on_startup():
    """
    Main function to run the bootstrap process. It finds the latest YAML backup,
    clears the database, and repopulates it with questions from the YAML file.
    It uses AI to infer exercise type and subject matter for each question.
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

        logging.info("Initializing AI Question Generator for enrichment.")
        ai_generator = AIQuestionGenerator()
        question_count = 0

        TYPE_TO_CATEGORY_ID = {
            'socratic': 'basic',
            'command': 'command',
            'live_k8s': 'command',
            'manifest': 'manifest',
            'yaml_author': 'manifest',
            'yaml_edit': 'manifest',
            'live_k8s_edit': 'manifest'
        }

        for q in data:
            if not isinstance(q, dict) or 'id' not in q:
                logging.warning(f"Skipping invalid item in YAML: {q}")
                continue

            q_id = q.get('id')
            prompt = q.get('prompt')
            logging.info(f"Processing question with id: {q_id}")

            # AI inference for category and subject
            try:
                if not prompt:
                    raise ValueError("Prompt is missing, cannot use AI inference.")

                logging.info(f"Using AI to infer exercise type and subject for question {q_id}.")
                base_question = {'prompt': prompt}
                enriched_q = ai_generator.generate_question(base_question=base_question)

                yaml_type = enriched_q.get('type')
                subject_id = enriched_q.get('category')
                logging.info(f"AI inferred type: '{yaml_type}', subject: '{subject_id}' for question {q_id}.")

            except Exception as e:
                logging.warning(f"AI inference failed for question {q_id}, falling back to YAML values. Error: {e}")
                yaml_type = q.get('type')
                subject_id = q.get('category')

            category_id = TYPE_TO_CATEGORY_ID.get(yaml_type)

            add_question(
                id=q_id,
                prompt=prompt,
                source_file=str(latest_backup_path),
                response=q.get('answer'),
                category=subject_id,  # This is for subject_id
                source=q.get('source'),
                validation_steps=q.get('validation_steps'),
                validator=q.get('validator'),
                review=q.get('review', False),
                conn=conn
            )

            # Now, update the category_id (Exercise Category)
            if category_id:
                logging.info(f"Setting exercise category to '{category_id}' for question {q_id}")
                cursor.execute("UPDATE questions SET category_id = ? WHERE id = ?", (category_id, q_id))
            else:
                logging.warning(f"Could not determine exercise category for type '{yaml_type}' in question {q_id}")

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
