#!/usr/bin/env python3
"""
This script reorganizes all questions in the database by assigning them to a
schema category ('Basic/Open-Ended', 'Command-Based/Syntax', 'Manifests')
using an AI model for classification.
"""
import os
import sys
import argparse
import logging
from tqdm import tqdm

# Ensure the parent directory is on sys.path to allow for package imports
if __name__ == '__main__' and __package__ is None:
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(pkg_dir)
    sys.path.insert(0, project_root)
    # At this point, `import kubelingo` should work
    __package__ = 'scripts'

from kubelingo.database import get_all_questions, add_question, get_db_connection
from kubelingo.question import Question, QuestionCategory
from kubelingo.utils.config import get_api_key

try:
    import openai
except ImportError:
    print("OpenAI library not found. Please run 'pip install openai'")
    sys.exit(1)


class AICategorizer:
    """Uses an AI model to classify questions into schema categories."""

    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        if not api_key:
            raise ValueError("OpenAI API key is required.")
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def get_system_prompt(self) -> str:
        """Returns the system prompt for the classification task."""
        return """You are an expert assistant for categorizing Kubernetes quiz questions. Your task is to classify a given question into one of three specific categories: 'Basic/Open-Ended', 'Command-Based/Syntax', or 'Manifests'.

Here are the definitions for each category:
- 'Basic/Open-Ended': These questions test conceptual knowledge, definitions, or ask for explanations. They do not require writing a specific command or a YAML manifest. Examples: "What is a Pod?", "Explain the role of the kube-scheduler.", "What is the difference between a Deployment and a StatefulSet?".
- 'Command-Based/Syntax': These questions require the user to provide a specific command-line instruction, typically using `kubectl`, `helm`, or another CLI tool. The answer is a single command. Examples: "Create a new namespace named 'development'.", "Scale the deployment 'frontend' to 3 replicas.", "List all pods in the 'default' namespace.".
- 'Manifests': These questions require the user to write or edit a Kubernetes YAML manifest file. The answer is a YAML configuration. Examples: "Create a YAML manifest for a Pod named 'my-pod' with the image 'nginx'.", "Edit the provided deployment YAML to add a new environment variable.".

Based on the question text and hint provided, you must respond with ONLY ONE of the following category names, and nothing else:
Basic/Open-Ended
Command-Based/Syntax
Manifests"""

    def categorize_question(self, question: dict) -> QuestionCategory:
        """
        Classifies a single question using the AI model.
        Returns a QuestionCategory enum member.
        """
        prompt_text = question.get('prompt', '')
        q_type = question.get('type', 'N/A')
        user_prompt = f"Question: \"{prompt_text}\"\nHint (Question Type): \"{q_type}\""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=20,
            )
            category_str = response.choices[0].message.content.strip()

            # Map the string response to the enum
            for category_enum in QuestionCategory:
                if category_enum.value == category_str:
                    return category_enum
            
            logging.warning(f"AI returned an unknown category '{category_str}' for question ID {question['id']}. Skipping.")
            return None

        except Exception as e:
            logging.error(f"Failed to categorize question ID {question['id']}: {e}")
            return None


def main():
    """Main function to run the reorganization script."""
    parser = argparse.ArgumentParser(description="Reorganize questions by schema category using AI.")
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Perform a dry run without making any changes to the database."
    )
    parser.add_argument(
        '--model',
        type=str,
        default='gpt-3.5-turbo',
        help="The AI model to use for categorization (e.g., 'gpt-4-turbo')."
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    api_key = os.getenv('OPENAI_API_KEY') or get_api_key()
    if not api_key:
        logging.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable or use 'kubelingo config set openai'.")
        sys.exit(1)

    categorizer = AICategorizer(api_key=api_key, model=args.model)
    
    print("Fetching all questions from the database...")
    all_questions = get_all_questions()

    if not all_questions:
        print("No questions found in the database. Nothing to do.")
        return

    print(f"Found {len(all_questions)} questions. Starting categorization...")

    conn = get_db_connection()
    updated_count = 0
    failed_count = 0

    try:
        with tqdm(all_questions, desc="Categorizing questions") as pbar:
            for q_dict in pbar:
                new_category = categorizer.categorize_question(q_dict)

                if new_category:
                    if str(q_dict.get('schema_category')) == new_category.value:
                        pbar.set_postfix(status=f"Skipped (already '{new_category.value}')")
                        continue
                    
                    pbar.set_postfix(status=f"Updating to '{new_category.value}'")
                    if not args.dry_run:
                        q_dict['schema_category'] = new_category.value
                        # The dict from get_all_questions has a 'type' key for compatibility,
                        # but add_question expects 'question_type'. We rename it before calling.
                        q_dict['question_type'] = q_dict.pop('type', None)
                        # Use add_question to update the record in the database
                        add_question(conn=conn, **q_dict)
                    updated_count += 1
                else:
                    pbar.set_postfix(status="Failed")
                    failed_count += 1

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()

    print("\nReorganization complete.")
    print(f"  - Questions updated: {updated_count}")
    print(f"  - Questions failed/skipped: {failed_count}")
    if args.dry_run:
        print("\nNOTE: This was a dry run. No changes were saved to the database.")

if __name__ == '__main__':
    main()
