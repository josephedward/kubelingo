import sys
import argparse
from pathlib import Path

# Add project root to path to allow importing from kubelingo
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.database import get_db_connection, get_all_questions
from kubelingo.utils import path_utils


def verify_questions(db_path: str):
    """
    Connects to the database and prints a summary of question counts per category.
    """
    if not Path(db_path).exists():
        print(f"Database file not found at: {db_path}")
        return

    print(f"Verifying database: {db_path}")
    conn = get_db_connection(db_path=db_path)

    try:
        cursor = conn.cursor()

        # Get total questions
        cursor.execute("SELECT COUNT(*) FROM questions")
        total_questions = cursor.fetchone()[0]
        print(f"\nTotal questions in database: {total_questions}")

        if total_questions == 0:
            return

        # Get counts per category
        print("\nQuestions per category:")
        cursor.execute("SELECT category, COUNT(*) FROM questions GROUP BY category ORDER BY category")
        rows = cursor.fetchall()

        if not rows:
            print("  No categories found.")
        else:
            for row in rows:
                category, count = row
                category_name = category if category else "Uncategorized"
                print(f"  - {category_name}: {count}")

        # Get counts per schema_category
        print("\nQuestions per schema_category:")
        cursor.execute("SELECT schema_category, COUNT(*) FROM questions GROUP BY schema_category ORDER BY schema_category")
        rows = cursor.fetchall()

        if not rows:
            print("  No schema_categories found.")
        else:
            for row in rows:
                schema_category, count = row
                schema_category_name = schema_category if schema_category else "Uncategorized"
                print(f"  - {schema_category_name}: {count}")

        print("\n--- Data Integrity Checks ---")
        all_questions = get_all_questions(conn=conn)

        uncategorized = [q for q in all_questions if not q.get('category')]
        if uncategorized:
            print(f"\nFound {len(uncategorized)} uncategorized questions. The app may ignore these.")
            print("Consider assigning a category to them:")
            for q in uncategorized[:10]:  # To avoid spamming, show first 10
                print(f"  - ID: {q.get('id')}, Source: {q.get('source_file')}")
            if len(uncategorized) > 10:
                print(f"  ... and {len(uncategorized) - 10} more.")
        else:
            print("\nAll questions have a category assigned.")

        no_schema = [q for q in all_questions if not q.get('schema_category')]
        if no_schema:
            print(f"\nFound {len(no_schema)} questions with no schema_category. The app may ignore these.")
            for q in no_schema[:10]:
                print(f"  - ID: {q.get('id')}, Source: {q.get('source_file')}")
            if len(no_schema) > 10:
                print(f"  ... and {len(no_schema) - 10} more.")
        else:
            print("All questions have a schema_category assigned.")

        no_prompt = [q for q in all_questions if not q.get('prompt')]
        if no_prompt:
            print(f"\nFound {len(no_prompt)} questions with no prompt.")
            for q in no_prompt:
                print(f"  - ID: {q.get('id')}, Source: {q.get('source_file')}")
        else:
            print("All questions have a prompt.")

        # Check for answerable questions
        unanswerable = []
        for q in all_questions:
            # A question is considered answerable if it has any of these fields with a non-empty value.
            # Note: `answer` and `answers` are assumed to be fields promoted from `metadata` in some YAML questions.
            if not (q.get('response') or
                    q.get('validator') or
                    q.get('validation_steps') or
                    q.get('correct_yaml') or
                    q.get('answer') or
                    q.get('answers')):
                unanswerable.append(q)

        if unanswerable:
            print(f"\nFound {len(unanswerable)} questions without a way to check answers.")
            print("Consider adding a `response`, `validator`, `validation_steps`, `correct_yaml`, or `answer`/`answers` field:")
            for q in unanswerable[:10]:
                print(f"  - ID: {q.get('id')}, Source: {q.get('source_file')}")
            if len(unanswerable) > 10:
                print(f"  ... and {len(unanswerable) - 10} more.")
        else:
            print("\nAll questions have a method for answer validation.")

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify questions in a Kubelingo database.")
    parser.add_argument(
        "db_path",
        nargs="?",
        default=None,
        help="Path to the SQLite database file. If not provided, uses the live database.",
    )
    args = parser.parse_args()

    database_path = args.db_path
    if database_path is None:
        database_path = path_utils.get_live_db_path()

    verify_questions(database_path)
