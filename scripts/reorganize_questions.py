#!/usr/bin/env python3
"""
This script reorganizes all questions in the database by assigning them to a
schema category ('Basic/Open-Ended', 'Command-Based/Syntax', 'Manifests')
and a subject matter area using various methods.
"""
import argparse
import os
import sys
from tqdm import tqdm
from typing import Dict, Optional, List, Any
from collections import Counter

# Ensure the parent directory is on sys.path to allow for package imports
if __name__ == '__main__' and __package__ is None:
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(pkg_dir)
    sys.path.insert(0, project_root)
    # At this point, `import kubelingo` should work
    __package__ = 'scripts'

from kubelingo.database import get_db_connection, get_all_questions, _row_to_question_dict
from kubelingo.question import Question, ValidationStep, QuestionCategory, QuestionSubject
from kubelingo.modules.ai_categorizer import AICategorizer
from kubelingo.utils.ui import Fore, Style


# --- Method 1: AI-based categorization ---
def reorganize_by_ai(db_path: Optional[str] = None):
    """Categorize questions using an AI model."""
    try:
        categorizer = AICategorizer()
    except (ImportError, ValueError) as e:
        print(f"{Fore.RED}Failed to initialize AI Categorizer: {e}{Style.RESET_ALL}")
        print(f"{Fore.RED}Please ensure an AI provider is configured (e.g., set OPENAI_API_KEY).{Style.RESET_ALL}")
        return

    conn = get_db_connection(db_path=db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE schema_category IS NULL OR subject_matter IS NULL")
    rows = cursor.fetchall()
    
    if not rows:
        print(f"{Fore.GREEN}All questions are already categorized. No migration needed.{Style.RESET_ALL}")
        conn.close()
        return

    print(f"Found {len(rows)} questions to categorize using AI...")
    
    updated_count = 0
    with tqdm(rows, desc="Categorizing questions") as pbar:
        for row in pbar:
            q_dict = _row_to_question_dict(row)
            q_id = q_dict.get('id')
            
            result = categorizer.categorize_question(q_dict)
            
            if result:
                schema_category_from_ai = result.get("schema_category")
                subject_matter = result.get("subject_matter")

                # Map AI output to the database schema for robustness, as the model may
                # sometimes return the descriptive text instead of the simple value.
                schema_category_map = {
                    "basic": "basic",
                    "command": "command",
                    "manifest": "manifest",
                    "Basic/Open-Ended": "basic",
                    "Command-Based/Syntax": "command",
                    "Manifests": "manifest",
                }
                schema_category = schema_category_map.get(schema_category_from_ai)

                if schema_category and subject_matter:
                    cursor.execute(
                        "UPDATE questions SET schema_category = ?, subject_matter = ? WHERE id = ?",
                        (schema_category, subject_matter, q_id)
                    )
                    updated_count += 1
                    pbar.set_postfix(status="Success")
                else:
                    pbar.set_postfix(status=f"Invalid AI data for {q_id}")
            else:
                pbar.set_postfix(status=f"Failed: {q_id}")

    conn.commit()
    conn.close()
    
    print("\nAI reorganization complete.")
    print(f"  - Questions updated: {updated_count}")
    print(f"  - Questions failed/skipped: {len(rows) - updated_count}")


# --- Method 2: Rule-based from question_type ---
def map_type_to_schema(q_type: str) -> str:
    q = (q_type or '').lower()
    if q in ('yaml_author', 'yaml_edit', 'live_k8s_edit'):
        return QuestionCategory.MANIFEST.value
    if q in ('command', 'live_k8s'):
        return QuestionCategory.COMMAND.value
    if q == 'socratic':
        return QuestionCategory.OPEN_ENDED.value
    # default fallback
    return QuestionCategory.COMMAND.value


def reorganize_by_type_mapping(db_path: Optional[str] = None):
    """Reassign schema_category based on the question_type column."""
    print("Reassigning schema category based on question_type...")
    conn = get_db_connection(db_path=db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, question_type FROM questions")
    rows = cursor.fetchall()
    total = len(rows)
    updated = 0
    for row in tqdm(rows, desc="Updating categories by type"):
        qid = row['id']
        q_type = row['question_type'] or ''
        new_cat = map_type_to_schema(q_type)
        cursor.execute(
            "UPDATE questions SET schema_category = ? WHERE id = ?", (new_cat, qid)
        )
        if cursor.rowcount > 0:
            updated += 1
    conn.commit()
    conn.close()
    print(f"\nReassigned schema_category for {updated}/{total} questions.")


# --- Method 3: Rule-based from dataclass logic ---
def reorganize_by_dataclass_logic(db_path: Optional[str] = None):
    """
    Iterates through all questions, determines schema category using dataclass logic, and updates them.
    """
    print("Reorganizing question categories based on dataclass logic...")
    conn = get_db_connection(db_path=db_path)
    if not conn:
        print("Failed to connect to the database.")
        return

    all_questions = get_all_questions()
    print(f"Found {len(all_questions)} total questions to process.")

    updated_count = 0
    questions_by_source = {}
    
    cursor = conn.cursor()

    for q_dict in tqdm(all_questions, desc="Updating categories by dataclass logic"):
        try:
            q_copy = q_dict.copy()

            if q_copy.get('validation_steps'):
                q_copy['validation_steps'] = [
                    ValidationStep(**step) for step in q_copy['validation_steps'] if isinstance(step, dict)
                ]
            q_copy.pop('validation', None)

            question_obj = Question(**q_copy)

            new_category = question_obj.schema_category.value if question_obj.schema_category else None

            source_file = q_dict.get('source_file', 'unknown')
            if source_file not in questions_by_source:
                questions_by_source[source_file] = []
            questions_by_source[source_file].append(new_category)

            if new_category and new_category != q_dict.get('schema_category'):
                cursor.execute(
                    "UPDATE questions SET schema_category = ? WHERE id = ?",
                    (new_category, q_dict['id'])
                )
                updated_count += 1

        except Exception as e:
            print(f"  [ERROR] Could not process question ID {q_dict.get('id')}: {e}")
    
    conn.commit()
    conn.close()
    print(f"\nReorganization complete. Updated {updated_count} questions.")

    # Report on files with mixed content
    print("\nChecking for quiz files with mixed categories...")
    mixed_files = 0
    for source, categories in questions_by_source.items():
        unique_categories = set(c for c in categories if c)
        if len(unique_categories) > 1:
            print(f"  - File '{source}' contains multiple categories: {Counter(categories)}")
            mixed_files += 1

    if mixed_files == 0:
        print("No mixed-category quiz files found.")
    else:
        print(f"\nFound {mixed_files} files with mixed categories.")


def main():
    """Main function to run the reorganization script."""
    parser = argparse.ArgumentParser(
        description="Reorganize question categories and subjects using various methods.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-m", "--method",
        choices=['ai', 'type-mapping', 'dataclass'],
        default='ai',
        help=(
            "Choose the reorganization method:\n"
            "  - ai:           Use an AI model to classify schema and subject (default).\n"
            "  - type-mapping: Use rules to map `question_type` to `schema_category`.\n"
            "  - dataclass:    Use the Question dataclass logic to determine `schema_category`."
        )
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to the SQLite database file. Defaults to the live application database.",
    )
    args = parser.parse_args()

    if args.method == 'ai':
        reorganize_by_ai(db_path=args.db_path)
    elif args.method == 'type-mapping':
        reorganize_by_type_mapping(db_path=args.db_path)
    elif args.method == 'dataclass':
        reorganize_by_dataclass_logic(db_path=args.db_path)


if __name__ == '__main__':
    main()
