#!/usr/bin/env python3
"""
List SQLite backup files in the backups directory.
"""
import argparse
import glob
import os
import sys

def main():
    parser = argparse.ArgumentParser(description='Locate SQLite backup files')
    parser.add_argument(
        'directories', nargs='*', help='Directory(ies) to scan for .db backups (default: configured backup dirs)'
    )
    args = parser.parse_args()
    # Determine directories to scan
    if args.directories:
        dirs = args.directories
    else:
        try:
            from kubelingo.utils.config import SQLITE_BACKUP_DIRS
            dirs = SQLITE_BACKUP_DIRS
        except ImportError:
            dirs = ['backups']
    # Collect .db files from each directory
    files = []
    for d in dirs:
        pattern = os.path.join(d, '*.db')
        files.extend(glob.glob(pattern))
    files = sorted(files)
    if not files:
        print('No SQLite backups found in', ', '.join(dirs))
        sys.exit(0)
    for path in files:
        size = os.path.getsize(path)
        mtime = os.path.getmtime(path)
        print(f"{path}  {size} bytes  modified={mtime}")

if __name__ == '__main__':
    main()