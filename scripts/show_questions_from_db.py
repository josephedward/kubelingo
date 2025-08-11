import sys
from pathlib import Path

# Add project root to path to allow importing from kubelingo
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.database import get_all_questions, get_db_connection
from kubelingo.utils import path_utils


def main():
    """
    Connects to the live database, fetches all questions, and prints a summary.
    """
    db_path = path_utils.get_live_db_path()
    print(f"Reading from database at: {db_path}")

    conn = None
    try:
        conn = get_db_connection(db_path)
        questions = get_all_questions(conn)
    except Exception as e:
        print(f"Error connecting to or reading from database: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

    if not questions:
        print("No questions found in the database.")
        return

    print(f"\nSuccessfully found {len(questions)} questions in the database.")
    print("Here are the first 5 question prompts:")
    for i, q in enumerate(questions[:5]):
        print(f"  {i+1}. {q.get('prompt', 'N/A')}")

    print("\nTo see more, you could query the database directly or use the application's CLI.")


if __name__ == "__main__":
    main()
