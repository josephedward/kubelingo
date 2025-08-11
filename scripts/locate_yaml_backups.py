#!/usr/bin/env python3
"""
Locates the most recent YAML backup file.
This utility scans configured backup directories and reports the single most recently modified file.
"""
import argparse
import datetime
import os
import sys
from pathlib import Path
from typing import List

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.utils.config import YAML_BACKUP_DIRS
from kubelingo.utils.path_utils import find_yaml_files_from_paths


def get_backup_files(directories: List[str]) -> List[Path]:
    """Finds all YAML backup files in the given directories."""
    return find_yaml_files_from_paths(directories)


def main():
    """Main function to locate the most recent YAML backup file."""
    parser = argparse.ArgumentParser(
        description="Locates the most recent YAML backup file by modification time.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "dirs",
        nargs="*",
        default=[],
        help="One or more directories to scan. If not provided, uses all configured default backup directories.",
    )
    args = parser.parse_args()

    if args.dirs:
        scan_dirs = args.dirs
    else:
        scan_dirs = YAML_BACKUP_DIRS

    try:
        files = get_backup_files(scan_dirs)
    except Exception as e:
        print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)

    if not files:
        dirs_str = ", ".join(scan_dirs)
        print(f"No YAML backups found in {dirs_str}")
        sys.exit(0)

    latest_file = max(files, key=lambda p: p.stat().st_mtime)
    stat = latest_file.stat()
    mod_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')

    print("--- Most Recent YAML Backup ---")
    print(f"Path: {latest_file}")
    print(f"Modified: {mod_time}")
    print(f"Size: {stat.st_size / 1024:.2f} KB")


if __name__ == "__main__":
    main()
