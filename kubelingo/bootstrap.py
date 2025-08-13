import getpass
import logging
import sqlite3
from pathlib import Path

import questionary
import yaml

from kubelingo.database import add_question, get_db_connection
from kubelingo.integrations.llm import GeminiClient, OpenAIClient
from kubelingo.modules.ai_categorizer import AICategorizer
from kubelingo.utils.config import (
    get_api_key,
    save_ai_provider,
    save_api_key,
)
from kubelingo.utils.path_utils import find_and_sort_files_by_mtime, get_project_root
from kubelingo.utils.ui import Fore, Style

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def _check_api_keys():
    """Checks for API keys and prompts if none are configured."""
    # Check if at least one key is already set
    if get_api_key('gemini') or get_api_key('openai'):
        return

    print(f"\n{Fore.YELLOW}--- Welcome to Kubelingo ---{Style.RESET_ALL}")
    print("AI-powered features like Socratic study mode require an API key.")
    print("You can get a key from Google AI Studio (for Gemini) or OpenAI.")
    print("")

    if questionary.confirm("Would you like to set up an API key now?", default=True).ask():
        # Prompt for Gemini
        gemini_key = getpass.getpass("Enter your Gemini API key (or press Enter to skip): ").strip()
        if gemini_key:
            if GeminiClient.test_key(gemini_key):
                save_api_key('gemini', gemini_key)
                print(f"{Fore.GREEN}✓ Gemini API key is valid and has been saved.{Style.RESET_ALL}")
                save_ai_provider('gemini')  # Set as default provider
                return  # Exit after successful configuration
            else:
                print(f"{Fore.RED}✗ The Gemini API key provided is not valid.{Style.RESET_ALL}")

        # Prompt for OpenAI if Gemini was skipped or failed
        openai_key = getpass.getpass("Enter your OpenAI API key (or press Enter to skip): ").strip()
        if openai_key:
            if OpenAIClient.test_key(openai_key):
                save_api_key('openai', openai_key)
                print(f"{Fore.GREEN}✓ OpenAI API key is valid and has been saved.{Style.RESET_ALL}")
                save_ai_provider('openai')  # Set as default provider
            else:
                print(f"{Fore.RED}✗ The OpenAI API key provided is not valid.{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.YELLOW}No API key was configured. Some AI features may be disabled.{Style.RESET_ALL}")
            print(f"You can set one up later in the {Fore.CYAN}Settings -> API Keys{Style.RESET_ALL} menu.")
    else:
        print(f"\n{Fore.YELLOW}No API key was configured. Some AI features may be disabled.{Style.RESET_ALL}")
        print(f"You can set one up later in the {Fore.CYAN}Settings -> API Keys{Style.RESET_ALL} menu.")

    print("-" * 30 + "\n")


def initialize_app():
    """
    Performs all necessary startup tasks for the application, including
    API key checks and database bootstrapping.
    """
    _check_api_keys()
    bootstrap_on_startup()


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

        # If the YAML is a dictionary, try to find the list of questions within it.
        if isinstance(data, dict):
            questions_list = next((v for v in data.values() if isinstance(v, list)), None)
            if questions_list is not None:
                logging.info("Found a list of questions inside the YAML dictionary.")
                data = questions_list
            else:
                logging.error(f"YAML file {latest_backup_path} is a dictionary but contains no list of questions. Aborting.")
                conn.close()
                return

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
                subject_id=subject_id,  # This is subject_matter, which maps to subject_id
                source=q.get('source'),
                validation_steps=q.get('validation_steps'),
                validator=q.get('validator'),
                review=q.get('review', False),
                conn=conn
            )

            # Update the Exercise Category (schema_category) in a separate step.
            if category_id:
                logging.info(f"Setting exercise category to '{category_id}' for question {q_id}")
                cursor.execute("UPDATE questions SET schema_category = ? WHERE id = ?", (category_id, q_id))
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
