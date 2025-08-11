#!/usr/bin/env python3
"""
Displays the schema of the most recent SQLite backup file.
"""
import sqlite3
import sys
from pathlib import Path
from typing import List, Optional

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from kubelingo.utils.path_utils import find_sqlite_files_from_paths
    from kubelingo.utils.config import SQLITE_BACKUP_DIRS
except ImportError as e:
    print(f"Error: A required kubelingo module is not available: {e}. "
          "Ensure you run this from the project root.", file=sys.stderr)
    sys.exit(1)


def find_most_recent_backup(files: List[Path]) -> Optional[Path]:
    """Finds the most recent file in a list based on modification time."""
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def main():
    """Finds the most recent SQLite backup and prints its schema."""
    backup_dirs = SQLITE_BACKUP_DIRS
    if not backup_dirs:
        print("No SQLite backup directories are configured.", file=sys.stderr)
        sys.exit(1)

    try:
        backup_files = find_sqlite_files_from_paths(backup_dirs)
    except Exception as e:
        print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)

    most_recent = find_most_recent_backup(backup_files)

    if not most_recent:
        print("No SQLite backup files found.")
        sys.exit(1)

    print(f"Displaying schema for the most recent backup: {most_recent}\n")

    try:
        conn = sqlite3.connect(f"file:{most_recent}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        conn.close()

        if not tables:
            print("No tables found in the database.")
            return

        for name, sql in tables:
            print(f"-- Schema for table: {name}")
            print(f"{sql};\n")

    except sqlite3.Error as e:
        print(f"Error reading database schema: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Finds the most recent SQLite backup and prints its schema.
"""
import sqlite3
import sys
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from kubelingo.utils.path_utils import find_and_sort_files_by_mtime
    from kubelingo.utils.config import SQLITE_BACKUP_DIRS
except ImportError as e:
    print(f"Error: A required kubelingo module is not available: {e}. "
          "Ensure you run this from the project root.", file=sys.stderr)
    sys.exit(1)

def main():
    """Finds the most recent SQLite backup and prints its schema."""
    backup_dirs = SQLITE_BACKUP_DIRS
    if not backup_dirs:
        print("No SQLite backup directories are configured.", file=sys.stderr)
        sys.exit(1)

    try:
        backup_files = find_and_sort_files_by_mtime(backup_dirs, [".db", ".sqlite", ".sqlite3"])
    except Exception as e:
        print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)

    if not backup_files:
        print("No SQLite backup files found to view schema from.", file=sys.stderr)
        sys.exit(1)
    
    most_recent_db = backup_files[0]
    print(f"Displaying schema for the most recent backup: {most_recent_db}\n")

    try:
        conn = sqlite3.connect(f"file:{most_recent_db}?mode=ro", uri=True)
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
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    main()
