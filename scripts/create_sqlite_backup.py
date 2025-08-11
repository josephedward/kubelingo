#!/usr/bin/env python3
"""
Create a timestamped backup of the live SQLite database.
"""
import argparse
import os
import shutil
import datetime
import sys
from pathlib import Path

# Add project root to path for config import
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
from kubelingo.utils.config import DATABASE_FILE, SQLITE_BACKUP_DIRS

def main():
    parser = argparse.ArgumentParser(description='Create a backup of the live SQLite database')
    # Default to first configured SQLite backup directory, fallback to 'backups'
    default_dir = SQLITE_BACKUP_DIRS[0] if SQLITE_BACKUP_DIRS else 'backups'
    parser.add_argument('-o', '--output-dir', default=default_dir, help='Directory to store the backup')
    args = parser.parse_args()

    src = DATABASE_FILE
    if not os.path.exists(src):
        print(f"Error: live database not found at {src}")
        sys.exit(1)

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    dest_dir = args.output_dir
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f'kubelingo_{timestamp}.db')
    shutil.copy(src, dest)
    print(f"Backup created: {dest}")

if __name__ == '__main__':
    main()