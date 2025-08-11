#!/usr/bin/env python3
"""
Finds and displays all SQLite backup files from configured directories.
"""
import argparse
import datetime
import sys
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from kubelingo.utils.path_utils import find_sqlite_files
    from kubelingo.utils.config import SQLITE_BACKUP_DIRS
except ImportError as e:
    print(f"Error: A required kubelingo module is not available: {e}. "
          "Ensure you run this from the project root.", file=sys.stderr)
    sys.exit(1)


def main():
    """Finds and prints all SQLite backup files."""
    parser = argparse.ArgumentParser(
        description="Finds and displays all SQLite backup files."
    )
    parser.add_argument(
        "--path-only",
        action="store_true",
        help="If set, only prints the paths of the files and suppresses other output.",
    )
    args = parser.parse_args()

    backup_dirs = SQLITE_BACKUP_DIRS
    if not backup_dirs:
        if not args.path_only:
            print("No SQLite backup directories are configured.", file=sys.stderr)
        sys.exit(1)

    try:
        backup_files = find_sqlite_files(backup_dirs)
    except Exception as e:
        if not args.path_only:
            print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)

    if not backup_files:
        if not args.path_only:
            print("No SQLite backup files found.")
        sys.exit(1)
        
    sorted_files = sorted(backup_files, key=lambda p: p.stat().st_mtime, reverse=True)

    if args.path_only:
        for f in sorted_files:
            print(f)
    else:
        print(f"Searching for SQLite backup files in: {', '.join(backup_dirs)}...")
        print(f"\nFound {len(sorted_files)} backup file(s), sorted by most recent:\n")
        for f in sorted_files:
            mod_time = f.stat().st_mtime
            mod_time_str = datetime.datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  - {f} (Last modified: {mod_time_str})")


if __name__ == "__main__":
    main()
