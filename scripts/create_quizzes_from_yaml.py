#!/usr/bin/env python

import logging
import yaml
from pathlib import Path
import sys
import os
import sqlite3
import llm
from datetime import datetime
import json

# Add project root to path to allow imports of kubelingo
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.database import get_db_connection, init_db
from kubelingo.utils.path_utils import get_project_root, get_live_db_path

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def process_with_gemini(prompt, model="gemini-2.0-flash"):
    """
    Uses the llm-gemini plugin to process a prompt with the specified model.
    """
    try:
        model_instance = llm.get_model(model)
        response = model_instance.prompt(prompt)
        # The response object has a .text() method to get the text of the response
        return response.text().strip()
    except Exception as e:
        logging.error(f"Error processing with Gemini: {e}")
        return None


def add_question(conn, id, prompt, source_file, response, category, source, validation_steps, validator, review):
    """
    Adds a question to the database, handling JSON serialization for complex fields.
    """
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO questions (
                id, prompt, source_file, response, category, source,
                validation_steps, validator, review
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                prompt=excluded.prompt,
                source_file=excluded.source_file,
                response=excluded.response,
                category=excluded.category,
                source=excluded.source,
                validation_steps=excluded.validation_steps,
                validator=excluded.validator,
                review=excluded.review;
        """, (
            id,
            prompt,
            str(source_file),
            response,
            category,
            source,
            json.dumps(validation_steps) if validation_steps is not None else None,
            json.dumps(validator) if validator is not None else None,
            review
        ))
    except sqlite3.Error as e:
        logging.error(f"Failed to add question {id}: {e}")


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
    
    db_path = ":memory:"
    conn = get_db_connection(db_path)
    init_db(db_path=db_path, clear=True)
    logging.info("In-memory database initialized and schema created.")

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
                logging.debug(f"Processing question data: {q_data}")
                q_id = q_data.get('id')
                q_type = q_data.get('type')
                
                exercise_category = q_type
                if not exercise_category:
                    logging.warning(f"Skipping question {q_id} in {yaml_file}: missing type.")
                    continue
                
                # Use Gemini to process the question prompt
                prompt = q_data.get('prompt')
                if not prompt:
                    logging.warning(f"Skipping question {q_id}: Missing 'prompt'.")
                    continue

                # Add specific validation for 'manifest' type
                if q_type == 'manifest':
                    if 'vim' not in q_data.get('tools', []):
                        logging.warning(f"Skipping manifest question {q_id}: 'vim' tool is required.")
                        continue
                    if 'kubectl apply' not in q_data.get('validation', []):
                        logging.warning(f"Skipping manifest question {q_id}: 'kubectl apply' validation is required.")
                        continue

                add_question(
                    conn=conn,
                    id=q_id,
                    prompt=prompt,  # Store the processed prompt
                    source_file=str(yaml_file),
                    response=q_data.get('response'),
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
        logging.info(f"Successfully added {question_count} questions to the in-memory database.")

        live_db_path = Path(get_live_db_path())
        dump_filename = f"quiz_dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        dump_path = live_db_path.parent / dump_filename
        
        with open(dump_path, 'w') as f:
            for line in conn.iterdump():
                f.write(f'{line}\n')
        
        logging.info(f"Database dump created at: {dump_path}")
        logging.info(f"To load this dump into your main database, run:")
        logging.info(f"sqlite3 '{live_db_path}' < '{dump_path}'")
    else:
        logging.info("No new questions were added to the database.")
        
    conn.close()
    logging.info("Quiz creation process finished.")

if __name__ == "__main__":
    create_quizzes_from_backup()
