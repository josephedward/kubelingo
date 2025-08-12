#!/usr/bin/env python3
"""
This script loads all unique questions from YAML files, uses an AI to categorize
them by exercise type and subject matter, and saves them to a new database file.
"""

import argparse
import os
import sys
import dataclasses
from tqdm import tqdm
from typing import Dict, Optional

# Ensure the parent directory is on sys.path to allow for package imports
if __name__ == '__main__' and __package__ is None:
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(pkg_dir)
    sys.path.insert(0, project_root)
    __package__ = 'scripts'

from kubelingo.database import init_db, add_question, get_db_connection
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.modules.ai_categorizer import AICategorizer
from kubelingo.utils.path_utils import get_all_question_dirs, find_yaml_files
from kubelingo.utils.ui import Fore, Style
from kubelingo.question import Question


# --- Main script logic ---

def main():
    """Main function to run the import and categorization script."""
    parser = argparse.ArgumentParser(
        description="Import questions from YAML files into a new SQLite database with AI-powered categorization.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "output_db",
        help="Path to the new SQLite database file to be created.",
    )
    parser.add_argument(
        "--search-dir",
        action='append',
        help="Optional: Path to a specific directory to search for YAML files. Can be used multiple times. Defaults to searching all standard question directories."
    )
    args = parser.parse_args()

    if os.path.exists(args.output_db):
        overwrite = input(f"{{Fore.YELLOW}}Warning: Output database '{{args.output_db}}' already exists. Overwrite? (y/n): {{Style.RESET_ALL}}").lower()
        if overwrite != 'y':
            print("Operation cancelled.")
            return
        os.remove(args.output_db)

    try:
        categorizer = AICategorizer()
    except (ImportError, ValueError) as e:
        print(f"{{Fore.RED}}Failed to initialize AI Categorizer: {e}{{Style.RESET_ALL}}")
        print(f"{{Fore.RED}}Please ensure an AI provider is configured (e.g., set OPENAI_API_KEY).{{Style.RESET_ALL}}")
        sys.exit(1)

    print(f"Initializing new database at: {args.output_db}")
    init_db(db_path=args.output_db)
    conn = get_db_connection(db_path=args.output_db)

    search_dirs = args.search_dir or get_all_question_dirs()
    yaml_files = find_yaml_files(search_dirs)

    if not yaml_files:
        print(f"{{Fore.YELLOW}}No YAML files found in the specified directories.{{Style.RESET_ALL}}")
        return

    print(f"Found {len(yaml_files)} YAML file(s) to process...")

    all_questions = []
    loader = YAMLLoader()
    for file_path in yaml_files:
        try:
            questions = loader.load_file(str(file_path))
            all_questions.extend(questions)
        except Exception as e:
            print(f"{{Fore.YELLOW}}Warning: Could not process file '{file_path}': {e}{{Style.RESET_ALL}}")

    unique_questions: Dict[str, Question] = {{}}
    for q in all_questions:
        if q.prompt and q.prompt not in unique_questions:
            unique_questions[q.prompt] = q

    print(f"Found {len(unique_questions)} unique questions. Categorizing with AI...")

    processed_count = 0

    try:
        with tqdm(total=len(unique_questions), desc="Categorizing Questions") as pbar:
            for question in unique_questions.values():
                q_dict = dataclasses.asdict(question)
                ai_categories = categorizer.categorize_question(q_dict)

                schema_cat = q_dict.get('schema_category')
                subject_mat = q_dict.get('subject')

                if ai_categories:
                    schema_cat = ai_categories.get('schema_category', schema_cat)
                    subject_mat = ai_categories.get('subject_matter', subject_mat)

                add_question(
                    conn=conn,
                    id=q_dict.get('id'),
                    prompt=q_dict.get('prompt'),
                    source_file=q_dict.get('source_file'),
                    response=q_dict.get('response'),
                    category=q_dict.get('category'),
                    source=q_dict.get('source'),
                    validation_steps=q_dict.get('validation_steps'),
                    validator=q_dict.get('validator'),
                    review=q_dict.get('review', False),
                    explanation=q_dict.get('explanation'),
                    difficulty=q_dict.get('difficulty'),
                    pre_shell_cmds=q_dict.get('pre_shell_cmds'),
                    initial_files=q_dict.get('initial_files'),
                    question_type=q_dict.get('type'),
                    answers=q_dict.get('answers'),
                    correct_yaml=q_dict.get('correct_yaml'),
                    metadata=q_dict.get('metadata'),
                    schema_category=schema_cat,
                    subject_matter=subject_mat
                )
                processed_count += 1
                pbar.update(1)

    finally:
        if conn:
            conn.close()

    print(f"\\n{{Fore.GREEN}}Successfully processed and added {processed_count} questions to '{args.output_db}'.{{Style.RESET_ALL}}")

if __name__ == "__main__":
    main()
