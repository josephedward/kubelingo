#!/usr/bin/env python3
"""
Restore the Kubelingo questions database from the read-only backup.

This script copies the version-controlled snapshot of the original question bank
(`question-data-backup/kubelingo_original.db`) into the default user database location
(`~/.kubelingo/kubelingo.db`), replacing any existing live database.
"""
import os
import shutil

def main():
    # Determine paths
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir)
    )
    backup_db = os.path.join(project_root, 'question-data-backup', 'kubelingo_original.db')
    if not os.path.isfile(backup_db):
        print(f"Backup DB not found at '{backup_db}'.")
        return
    # Prepare user DB directory
    home = os.path.expanduser('~')
    app_dir = os.path.join(home, '.kubelingo')
    os.makedirs(app_dir, exist_ok=True)
    dst_db = os.path.join(app_dir, 'kubelingo.db')
    # Copy
    try:
        shutil.copy2(backup_db, dst_db)
        print(f"Restored questions DB from '{backup_db}' to '{dst_db}'.")
    except Exception as e:
        print(f"Failed to restore DB: {e}")

if __name__ == '__main__':
    main()