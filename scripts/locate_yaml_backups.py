#!/usr/bin/env python3
"""
Locate YAML backup files in the specified directory.
"""
import os
import time
import argparse
from pathlib import Path

def main():
    """
    Lists available YAML backup files with size and timestamp.
    """
    parser = argparse.ArgumentParser(
        description="List available YAML backup files with size and timestamp."
    )
    parser.add_argument(
        "backup_dir",
        nargs="?",
        default="question-data-backup",
        help="Directory to scan for YAML backups (default: question-data-backup)",
    )
    args = parser.parse_args()
    backup_dir = Path(args.backup_dir)

    if not backup_dir.is_dir():
        print(f"No YAML backup directory found at {backup_dir}")
        return

    files = [f for f in backup_dir.iterdir() if f.is_file() and f.suffix.lower() in ('.yaml', '.yml')]

    if not files:
        print(f"No YAML backup files found in {backup_dir}")
        return

    files.sort()
    print(f"Found {len(files)} YAML backup file(s) in {backup_dir}:\n")
    for f_path in files:
        try:
            size = f_path.stat().st_size
            mtime = time.localtime(f_path.stat().st_mtime)
            ts = time.strftime('%Y-%m-%d %H:%M:%S', mtime)
            print(f"{f_path.name}\t{size} bytes\t{ts}")
        except OSError as e:
            print(f"{f_path.name}\t<error: {e}>")

if __name__ == '__main__':
    main()
