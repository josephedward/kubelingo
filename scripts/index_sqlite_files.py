#!/usr/bin/env python3
"""
Index the live SQLite database and all configured backup files.
"""
import sys
from pathlib import Path
from kubelingo.utils.path_utils import get_live_db_path, get_all_sqlite_backup_dirs, find_sqlite_backup_files

def main():
    live = get_live_db_path()
    print("Live database:")
    print(f"  {live}")
    print()

    dirs = get_all_sqlite_backup_dirs()
    print("Configured SQLite backup directories:")
    for d in dirs:
        print(f" - {d}")
    print()

    files = find_sqlite_backup_files()
    if not files:
        print("No SQLite files found in any configured backup directories.")
        sys.exit(0)
    print("SQLite backup files:")
    for f in sorted(files):
        print(f)

if __name__ == '__main__':
    main()