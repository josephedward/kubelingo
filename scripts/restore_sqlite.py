#!/usr/bin/env python3
"""
Restore the live SQLite database from a backup file, auto-backing up the current live DB.
"""
import argparse
import os
import shutil
import sys
import datetime
from pathlib import Path

# Add project root to path for config import
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
from kubelingo.utils.config import DATABASE_FILE

def main():
    parser = argparse.ArgumentParser(description='Restore live SQLite DB from backup')
    parser.add_argument('backup_db', help='Path to the backup .db file')
    parser.add_argument('-p', '--pre-backup-dir', default='backups', help='Directory to store pre-restore backup')
    args = parser.parse_args()

    if not os.path.exists(args.backup_db):
        print(f"Error: backup file not found: {args.backup_db}")
        sys.exit(1)

    live = DATABASE_FILE
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    pre_dest = os.path.join(args.pre_backup_dir, f'kubelingo_pre_restore_{timestamp}.db')
    os.makedirs(args.pre_backup_dir, exist_ok=True)
    if os.path.exists(live):
        shutil.copy(live, pre_dest)
        print(f"Pre-restore backup created: {pre_dest}")

    shutil.copy(args.backup_db, live)
    print(f"Restored live database from {args.backup_db}")

if __name__ == '__main__':
    main()