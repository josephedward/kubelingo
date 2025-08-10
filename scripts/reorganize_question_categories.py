#!/usr/bin/env python3
"""
One-time script to populate the `schema_category` for all questions in the database.
"""
import os
import sys

# Ensure the project root is on the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kubelingo.database import get_all_questions, get_db_connection
from kubelingo.question import Question, ValidationStep, QuestionCategory
from collections import Counter

def reorganize_question_categories():
    """
    Iterates through all questions in the database, determines their schema category
    based on the logic in the Question dataclass, and updates them.
    Also reports on any quiz files with mixed categories.
    """
    print("Connecting to the database to reorganize question categories...")
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to the database.")
        return

    all_questions = get_all_questions()
    print(f"Found {len(all_questions)} total questions to process.")

    updated_count = 0
    questions_by_source = {}
    
    cursor = conn.cursor()

    for q_dict in all_questions:
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
    print(f"\nReorganization complete. Updated {updated_count} questions with a new schema category.")

    # Report on files with mixed content
    print("\nChecking for quiz files with mixed categories...")
    mixed_files = 0
    for source, categories in questions_by_source.items():
        unique_categories = set(c for c in categories if c)
        if len(unique_categories) > 1:
            print(f"  - File '{source}' contains multiple categories: {Counter(categories)}")
            mixed_files += 1

    if mixed_files == 0:
        print("No mixed-category quiz files found. All quizzes are consistently categorized.")
    else:
        print(f"\nFound {mixed_files} files with mixed categories. The UI will use the most common category for grouping.")

if __name__ == "__main__":
    reorganize_question_categories()
