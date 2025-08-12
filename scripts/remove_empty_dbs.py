import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
# Directories to scan for database files.
SCAN_DIRS = [
    PROJECT_ROOT / ".kubelingo",
    PROJECT_ROOT / "archive",
]
SQLITE_EXTENSIONS = [".db", ".sqlite3"]


def is_db_empty(db_path: Path) -> bool:
    """
    Checks if a SQLite database is empty by looking for user-created tables.

    Args:
        db_path: The path to the SQLite database file.

    Returns:
        True if the database has no user tables, False otherwise.
    """
    # A 0-byte file is not a valid DB, but is certainly empty.
    if db_path.stat().st_size == 0:
        return True

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Check for any tables that are not internal SQLite tables.
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        tables = cursor.fetchall()
        return len(tables) == 0
    except sqlite3.DatabaseError:
        # This file is not a valid SQLite database. For safety, we will not
        # consider it "empty" and will not delete it.
        print(
            f"Warning: Could not open '{db_path.relative_to(PROJECT_ROOT)}' as a database. Skipping."
        )
        return False
    finally:
        if conn:
            conn.close()


def remove_empty_dbs():
    """
    Scans configured directories for SQLite files and removes any that are empty.
    """
    print("Scanning for and removing empty databases...")
    deleted_count = 0
    for scan_dir in SCAN_DIRS:
        if not scan_dir.is_dir():
            continue

        print(f"-> Scanning directory: {scan_dir.relative_to(PROJECT_ROOT)}")
        found_files = []
        for ext in SQLITE_EXTENSIONS:
            found_files.extend(scan_dir.rglob(f"*{ext}"))

        if not found_files:
            print("  No SQLite files found.")
            continue

        for file_path in found_files:
            if is_db_empty(file_path):
                print(f"  - Deleting empty database: {file_path.relative_to(PROJECT_ROOT)}")
                try:
                    file_path.unlink()
                    deleted_count += 1
                except OSError as e:
                    print(f"    Error deleting file: {e}")

    print(f"\nScan complete. Deleted {deleted_count} empty database(s).")


if __name__ == "__main__":
    remove_empty_dbs()
