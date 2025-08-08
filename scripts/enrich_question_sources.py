import os
import sqlite3
import sys

# Add project root to path to allow imports of kubelingo
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from kubelingo.database import get_db_connection
from kubelingo.utils.config import ENABLED_QUIZZES

def build_source_map():
    """Builds a map from source_file basename to human-friendly source name."""
    source_map = {}
    for name, path in ENABLED_QUIZZES.items():
        source_file = os.path.basename(path)
        source_map[source_file] = name
    return source_map

def enrich_sources():
    """
    Scans the database for questions without a 'source' and populates it
    based on the source_file.
    """
    print("Enriching question sources in the database...")
    source_map = build_source_map()
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Find questions that need a source
        cursor.execute("SELECT id, source_file FROM questions WHERE source IS NULL OR source = ''")
        questions_to_update = cursor.fetchall()

        if not questions_to_update:
            print("All questions already have a source. No action needed.")
            return

        print(f"Found {len(questions_to_update)} questions missing a source. Updating...")
        
        updated_count = 0
        for q_id, source_file in questions_to_update:
            if source_file in source_map:
                source_name = source_map[source_file]
                cursor.execute("UPDATE questions SET source = ? WHERE id = ?", (source_name, q_id))
                updated_count += 1
            else:
                print(f"  - Warning: No source mapping found for '{source_file}' (question ID: {q_id})")

        conn.commit()
        print(f"Successfully updated {updated_count} questions.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    enrich_sources()
