#!/usr/bin/env python3
"""
Restore or merge a SQLite backup into the active Kubelingo database.
"""
import os
import sys
import shutil
import argparse
from pathlib import Path

# Inject project root for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.utils.config import DATABASE_FILE

def main():
    parser = argparse.ArgumentParser(
        description="Restore or merge from a SQLite backup into the active database."
    )
    parser.add_argument(
        'backup_file',
        type=str,
        help="Path to the SQLite backup file to restore from"
    )
    parser.add_argument(
        '-d', '--db-path',
        type=str,
        default=None,
        help=f"Target database path (default: {DATABASE_FILE})"
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help="Overwrite the target database file with the backup"
    )
    args = parser.parse_args()

    backup = Path(args.backup_file)
    if not backup.is_file():
        print(f"Backup file not found: {backup}")
        sys.exit(1)

    target = Path(args.db_path or DATABASE_FILE)
    if args.overwrite:
        # Make a copy of current DB first
        if target.exists():
            backup_current = target.with_suffix(target.suffix + '.pre_restore')
            try:
                shutil.copy2(target, backup_current)
                print(f"Current DB backed up to {backup_current}")
            except Exception as e:
                print(f"Failed to backup current DB: {e}")
                sys.exit(1)
        try:
            shutil.copy2(backup, target)
            print(f"Restored backup {backup} -> {target}")
        except Exception as e:
            print(f"Failed to restore backup: {e}")
            sys.exit(1)
    else:
        print("Merge operation is not implemented yet. Use --overwrite to replace the database.")
        sys.exit(1)

if __name__ == '__main__':
    main()