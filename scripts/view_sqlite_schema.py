#!/usr/bin/env python3
"""Prints the schema of the most recent SQLite backup."""

import sqlite3
from pathlib import Path

def get_most_recent_backup(backup_dir: Path):
    """Finds the most recent .db file in the backup directory."""
    if not backup_dir.is_dir():
        return None
    
    db_files = list(backup_dir.glob('*.db'))
    if not db_files:
        return None

    return max(db_files, key=lambda p: p.stat().st_mtime)

def print_db_schema(db_path: Path):
    """Connects to a SQLite DB and prints its schema."""
    print(f"Schema for {db_path}:\n")
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for table in tables:
            if table[0]:
                print(table[0])
                print("-" * 20)
        conn.close()
    except sqlite3.Error as e:
        print(f"Error reading database schema: {e}")

def main():
    """Finds the most recent SQLite backup and prints its schema."""
    repo_root = Path(__file__).resolve().parent.parent
    backup_dir = repo_root / 'backups' / 'sqlite'

    most_recent_backup = get_most_recent_backup(backup_dir)

    if not most_recent_backup:
        print(f"No SQLite backup files found in {backup_dir}")
        return
    
    print_db_schema(most_recent_backup)

if __name__ == "__main__":
    main()
