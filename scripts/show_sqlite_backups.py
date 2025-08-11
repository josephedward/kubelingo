#!/usr/bin/env python3
"""Lists all SQLite backup files."""

from pathlib import Path

def main():
    """Finds and prints paths of all SQLite backup files."""
    repo_root = Path(__file__).resolve().parent.parent
    backup_dir = repo_root / 'backups' / 'sqlite'

    if not backup_dir.is_dir():
        print(f"Backup directory not found: {backup_dir}")
        return

    db_files = sorted(list(backup_dir.glob('*.db')))

    if not db_files:
        print(f"No SQLite backup files found in {backup_dir}")
        return

    print("Found SQLite backup files:")
    for file_path in db_files:
        print(f"  - {file_path}")

if __name__ == "__main__":
    main()
