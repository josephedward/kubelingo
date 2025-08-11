import sys
from pathlib import Path

# Add project root to path to allow importing from kubelingo
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.database import get_db_connection
from kubelingo.utils import path_utils


def verify_questions():
    """
    Connects to the database and prints a summary of question counts per category.
    """
    db_path = path_utils.get_live_db_path()
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

    finally:
        conn.close()


if __name__ == "__main__":
    verify_questions()
