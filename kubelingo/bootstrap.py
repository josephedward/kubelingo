import logging
import sqlite3
from pathlib import Path

import yaml

from kubelingo.database import add_question, get_db_connection
from kubelingo.modules.ai_categorizer import AICategorizer
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
    
    search_paths = [
        project_root / 'yaml',
        project_root / 'backups' / 'yaml',
    ]
    
    yaml_backups = []
    for backup_dir in search_paths:
        if backup_dir.is_dir():
            logging.info(f"Searching for backups in {backup_dir}...")
            found_files = find_and_sort_files_by_mtime([str(backup_dir)], extensions=['.yaml', '.yml'])
            if found_files:
                yaml_backups = found_files
                break

    if not yaml_backups:
        logging.warning(f"No YAML backups found in any search location. Searched: {[str(d) for d in search_paths]}. Skipping bootstrap.")
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

        logging.info("Initializing AI Categorizer for enrichment.")
        try:
            categorizer = AICategorizer()
        except (ImportError, ValueError) as e:
            logging.error(f"Failed to initialize AI Categorizer: {e}. AI-based categorization will be skipped.")
            categorizer = None

        question_count = 0
        for q in data:
            if not isinstance(q, dict) or 'id' not in q:
                logging.warning(f"Skipping invalid item in YAML: {q}")
                continue

            q_id = q.get('id')
            prompt = q.get('prompt')
            logging.info(f"Processing question with id: {q_id}")

            # Set defaults from YAML, which serve as a fallback.
            subject_id = q.get('category')
            yaml_type = q.get('type')
            TYPE_TO_CATEGORY_ID_FALLBACK = {
                'socratic': 'basic',
                'command': 'command',
                'live_k8s': 'command',
                'manifest': 'manifest',
                'yaml_author': 'manifest',
                'yaml_edit': 'manifest',
                'live_k8s_edit': 'manifest'
            }
            category_id = TYPE_TO_CATEGORY_ID_FALLBACK.get(yaml_type)

            # Use AI to infer categories if available and a prompt exists.
            if categorizer and prompt:
                try:
                    logging.info(f"Using AI to infer exercise category and subject for question {q_id}.")
                    ai_result = categorizer.categorize_question({'prompt': prompt})

                    if ai_result:
                        # Update with AI results, keeping fallback if AI doesn't provide a value.
                        category_id = ai_result.get('exercise_category') or category_id
                        subject_id = ai_result.get('subject_matter') or subject_id
                        logging.info(f"AI inferred category: '{category_id}', subject: '{subject_id}' for question {q_id}.")
                    else:
                        logging.warning(f"AI categorization returned no result for question {q_id}. Using values from YAML.")
                except Exception as e:
                    logging.warning(f"AI inference failed for question {q_id}, using values from YAML. Error: {e}")

            # Add question with Subject Matter (subject_id)
            add_question(
                id=q_id,
                prompt=prompt,
                source_file=str(latest_backup_path),
                response=q.get('answer'),
                category=subject_id,  # This is subject_matter, which maps to subject_id
                source=q.get('source'),
                validation_steps=q.get('validation_steps'),
                validator=q.get('validator'),
                review=q.get('review', False),
                conn=conn
            )

            # Update the Exercise Category (category_id) in a separate step.
            if category_id:
                logging.info(f"Setting exercise category to '{category_id}' for question {q_id}")
                cursor.execute("UPDATE questions SET category_id = ? WHERE id = ?", (category_id, q_id))
            else:
                logging.warning(f"Could not determine exercise category for question {q_id}")

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
