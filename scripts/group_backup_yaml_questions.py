#!/usr/bin/env python3
"""
Group all legacy YAML backup quizzes into a single "legacy_yaml" module in the Kubelingo DB.

This script updates the `source_file` column for all questions imported from YAML backups
(where source='backup') so they appear as one combined module in the CLI menu.
After grouping, it snapshots the DB to the project backup.
"""
import os
import sqlite3
import shutil

from kubelingo.utils.config import DATABASE_FILE, BACKUP_DATABASE_FILE

def main():
    # Connect to the live DB
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    # Identify questions imported from YAML backups (source='backup')
    cursor.execute("SELECT COUNT(*) FROM questions WHERE source = 'backup'")
    total = cursor.fetchone()[0]
    if total == 0:
        print("No backup YAML questions found to group.")
        conn.close()
        return
    # Update source_file to unified module name
    cursor.execute(
        "UPDATE questions SET source_file = 'legacy_yaml' WHERE source = 'backup'"
    )
    conn.commit()
    conn.close()
    print(f"Grouped {total} backup YAML questions into module 'legacy_yaml'.")
    # Backup DB
    try:
        shutil.copy2(DATABASE_FILE, BACKUP_DATABASE_FILE)
        print(f"Database backup updated at: {BACKUP_DATABASE_FILE}")
    except Exception as e:
        print(f"Failed to backup database: {e}")

if __name__ == '__main__':
    main()