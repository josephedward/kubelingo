#!/usr/bin/env python3
"""
Displays the schema of the live SQLite database.
"""
import sqlite3
import sys
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from kubelingo.utils.path_utils import get_live_db_path
except ImportError as e:
    print(f"Error: A required kubelingo module is not available: {e}. "
          "Ensure you run this from the project root.", file=sys.stderr)
    sys.exit(1)

def main():
    """Displays the schema of the live database."""
    try:
        db_path = get_live_db_path()
        if not db_path or not Path(db_path).exists():
            print("Live database not found.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error finding live database: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Displaying schema for the live database: {db_path}\n")

    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            print("No tables found in the database.")
        else:
            for table_name, schema in tables:
                print(f"-- Schema for table: {table_name}")
                print(f"{schema};\n")

    except sqlite3.Error as e:
        print(f"Error reading database schema: {e}", file=sys.stderr)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
