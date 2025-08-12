#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from typing import Optional

# Add project root to path to allow importing from kubelingo
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.database import add_question, get_all_questions, get_db_connection
from kubelingo.utils.config import ENABLED_QUIZZES, get_live_db_path


def fix_source_paths_in_db(db_path: Optional[str] = None):
    """
    Ensures source_file paths in the database match the canonical paths in ENABLED_QUIZZES.
    This is a data-preserving operation that does not require clearing the DB.
    """
    print("Fixing source_file paths in the database...")
    db_path = db_path or get_live_db_path()
    conn = get_db_connection(db_path=db_path)

    all_questions = get_all_questions(conn)
    if not all_questions:
        print("No questions found in the database.")
        conn.close()
        return

    # This map defines the correct source file path for a given category.
    # The application uses the full path to identify a quiz's questions.
    category_to_source_file = ENABLED_QUIZZES
    allowed_args = {
        "id",
        "prompt",
        "source_file",
        "response",
        "category",
        "source",
        "validation_steps",
        "validator",
        "review",
        "question_type",
        "schema_category",
        "answers",
        "correct_yaml",
        "difficulty",
        "explanation",
        "initial_files",
        "pre_shell_cmds",
        "subject_matter",
        "metadata",
    }

    updated_count = 0
    try:
        for q_dict in all_questions:
            category = q_dict.get("category")
            if not category:
                continue

            correct_source_file = category_to_source_file.get(category)
            if not correct_source_file:
                continue

            # If the source file is incorrect, update it.
            if q_dict.get("source_file") != correct_source_file:
                q_dict["source_file"] = correct_source_file

                # Filter dict to only include keys that add_question accepts
                q_dict_for_db = {
                    k: v for k, v in q_dict.items() if k in allowed_args
                }
                # add_question uses INSERT OR REPLACE, which updates the record in place.
                add_question(conn=conn, **q_dict_for_db)
                updated_count += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error updating source files: {e}", file=sys.stderr)
    finally:
        conn.close()

    print(f"Finished. Updated {updated_count} question(s).")


def main():
    """
    Main function to parse arguments and run the fix script.
    """
    parser = argparse.ArgumentParser(
        description="Correct source_file paths in the SQLite database based on question category."
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to the SQLite database file. Defaults to the live application database.",
    )
    args = parser.parse_args()

    fix_source_paths_in_db(db_path=args.db_path)


if __name__ == "__main__":
    main()
