#!/usr/bin/env python

import logging
import yaml
from pathlib import Path
import sys
import os

# Add project root to path to allow imports of kubelingo
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.database import get_db_connection, add_question
from kubelingo.utils.path_utils import get_project_root

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Mapping from YAML 'type' to database 'category' based on shared_context.md
CATEGORY_MAPPING = {
    'socratic': 'basic',
    'command': 'command',
    'manifest': 'manifest',
}

def create_quizzes_from_backup():
    """
    Indexes YAML files from a consolidated backup and populates the database.
    """
    logging.info("Starting to create quizzes from consolidated YAML backup.")
    
    proj_root = get_project_root()
    yaml_dir = proj_root / 'yaml'

    logging.info(f"Looking for consolidated question files in: {yaml_dir}")

    if not yaml_dir.is_dir():
        logging.error(f"YAML directory not found at: {yaml_dir}")
        logging.error("Cannot search for consolidated question files.")
        return

    logging.info("Scanning for latest consolidated question file...")
    consolidated_files = sorted(yaml_dir.glob('consolidated_unique_questions_*.yaml'), reverse=True)

    if not consolidated_files:
        logging.warning(f"No 'consolidated_unique_questions_*.yaml' files found in '{yaml_dir}'.")
        return
    
    latest_file = consolidated_files[0]
    yaml_files = [latest_file]

    logging.info(f"Found latest consolidated file. Processing: {latest_file}")
    
    conn = get_db_connection()
    question_count = 0
    
    for yaml_file in yaml_files:
        logging.info(f"Processing file: {yaml_file}")
        try:
            with open(yaml_file, 'r') as f:
                questions_data = yaml.safe_load(f)
                if not isinstance(questions_data, list):
                    logging.warning(f"Skipping file {yaml_file}: content is not a list of questions.")
                    continue

            for q_data in questions_data:
                q_id = q_data.get('id')
                q_type = q_data.get('type')
                
                if not q_id or not q_type:
                    logging.warning(f"Skipping question in {yaml_file} due to missing 'id' or 'type'.")
                    continue
                
                exercise_category = CATEGORY_MAPPING.get(q_type)
                if not exercise_category:
                    logging.warning(f"Skipping question {q_id} in {yaml_file}: unknown type '{q_type}'.")
                    continue
                
                add_question(
                    conn=conn,
                    id=q_id,
                    prompt=q_data.get('prompt'),
                    source_file=str(yaml_file),
                    response=q_data.get('answer'),
                    category=exercise_category,
                    source=q_data.get('source'),
                    validation_steps=q_data.get('validation'),
                    validator=q_data.get('validator'),
                    review=q_data.get('review', False)
                )
                question_count += 1
                logging.info(f"Added question ID: {q_id} with category '{exercise_category}'.")

        except yaml.YAMLError as e:
            logging.error(f"Error parsing YAML file {yaml_file}: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while processing {yaml_file}: {e}")
    
    if question_count > 0:
        conn.commit()
        logging.info(f"Successfully added {question_count} questions to the database.")
    else:
        logging.info("No new questions were added to the database.")
        
    conn.close()
    logging.info("Quiz creation process finished.")

if __name__ == "__main__":
    create_quizzes_from_backup()
