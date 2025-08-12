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
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def create_quizzes_from_backup():
    """
    Indexes YAML files from a consolidated backup and populates the database.
    """
    gemini_models = [
        "gemini-1.5-pro-latest",
        "gemini-1.5-flash-latest",
        "gemini-2.0-flash",
    ]
    print("\nPlease choose a Gemini model to use for processing questions:")
    for i, model in enumerate(gemini_models, 1):
        print(f"  {i}. {model}")

    choice = 0
    while not 1 <= choice <= len(gemini_models):
        try:
            choice_str = input(f"Enter number (1-{len(gemini_models)}): ")
            choice = int(choice_str)
        except (ValueError, EOFError, KeyboardInterrupt):
            print("\nInvalid input. Aborting.")
            sys.exit(1)

    selected_model = gemini_models[choice - 1]
    logging.info(f"Using Gemini model: {selected_model}")

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
                data = yaml.safe_load(f)
                logging.debug(f"Loaded YAML content from {yaml_file}: {data}")

            if isinstance(data, dict):
                questions_data = data.get('questions')
            else:
                questions_data = data

            if not isinstance(questions_data, list):
                logging.error(
                    f"Skipping file {yaml_file}: Expected a list of questions, but got {type(questions_data)}."
                )
                continue

            for q_data in questions_data:
                metadata = q_data.get('metadata', {})
                
                # Consolidate data from top-level and metadata, with top-level taking precedence.
                consolidated_data = {**metadata, **q_data}

                logging.debug(f"Processing question data: {consolidated_data}")

                q_id = consolidated_data.get('id')
                prompt = consolidated_data.get('prompt')
                q_type = consolidated_data.get('type')
                category = consolidated_data.get('category')
                exercise_category = category or q_type

                if not q_id or not prompt:
                    logging.warning(f"Skipping question due to missing 'id' or 'prompt' in {yaml_file}: {consolidated_data}")
                    continue

                if not exercise_category:
                    logging.warning(f"Skipping question {q_id} in {yaml_file}: missing 'category' or 'type'.")
                    continue
                
                # Use Gemini to process the question prompt
                gemini_response = process_with_gemini(prompt, model=selected_model)
                if not gemini_response:
                    logging.warning(f"Skipping question {q_id}: Gemini processing failed.")
                    continue

                # Add specific validation for 'manifest' type
                if q_type == 'manifest':
                    if 'vim' not in consolidated_data.get('tools', []):
                        logging.warning(f"Skipping manifest question {q_id}: 'vim' tool is required.")
                        continue
                    if 'kubectl apply' not in consolidated_data.get('validation_steps', []):
                        logging.warning(f"Skipping manifest question {q_id}: 'kubectl apply' validation is required.")
                        continue

                add_question(
                    conn=conn,
                    id=q_id,
                    prompt=gemini_response,  # Store the processed prompt
                    source_file=str(yaml_file),
                    response=consolidated_data.get('response'),
                    category=exercise_category,
                    source=consolidated_data.get('source'),
                    validation_steps=consolidated_data.get('validation_steps'),
                    validator=consolidated_data.get('validator'),
                    review=consolidated_data.get('review', False)
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
