#!/usr/bin/env python3
"""
Finds and displays SQLite backup files from configured directories, sorted by most recent.
"""
import datetime
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
    """Finds and prints SQLite backup files."""
    backup_dirs = SQLITE_BACKUP_DIRS
    if not backup_dirs:
        print("No SQLite backup directories are configured.", file=sys.stderr)
        sys.exit(1)

    print(f"Searching for SQLite backup files in: {', '.join(backup_dirs)}...")

    try:
        backup_files = find_and_sort_files_by_mtime(backup_dirs, [".db", ".sqlite", ".sqlite3"])
    except Exception as e:
        print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)

    if not backup_files:
        print("No SQLite backup files found.")
        sys.exit(0)

    print(f"\nFound {len(backup_files)} backup file(s), sorted by most recent:\n")
    for file_path in backup_files:
        mod_time = file_path.stat().st_mtime
        mod_time_str = datetime.datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
        print(f"- {mod_time_str} | {file_path.name} ({file_path.parent})")


if __name__ == "__main__":
    main()
