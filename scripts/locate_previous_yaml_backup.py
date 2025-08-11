#!/usr/bin/env python3
"""
Finds and displays the most recent YAML backup file from configured directories.
"""
import datetime
import os
import sys
from pathlib import Path
from typing import List, Optional

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from kubelingo.utils.path_utils import find_yaml_files_from_paths
    from kubelingo.utils.config import YAML_BACKUP_DIRS
except ImportError as e:
    print(f"Error: A required kubelingo module is not available: {e}. "
          "Ensure you run this from the project root.", file=sys.stderr)
    sys.exit(1)


def find_most_recent_backup(files: List[Path]) -> Optional[Path]:
    """Finds the most recent file in a list based on modification time."""
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def main():
    """Finds and prints the most recent YAML backup file."""
    backup_dirs = YAML_BACKUP_DIRS
    if not backup_dirs:
        print("No YAML backup directories are configured.", file=sys.stderr)
        sys.exit(1)

    print(f"Searching for YAML backup files in: {', '.join(backup_dirs)}...")
    try:
        backup_files = find_yaml_files_from_paths(backup_dirs)
    except Exception as e:
        print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)

    if not backup_files:
        print("No YAML backup files found.")
        return

    most_recent = find_most_recent_backup(backup_files)

    print(f"\nFound {len(backup_files)} backup file(s).")
    if most_recent:
        mod_time = most_recent.stat().st_mtime
        mod_time_str = datetime.datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
        print(f"Most recent YAML backup: {most_recent}")
        print(f"Last modified: {mod_time_str}")


if __name__ == "__main__":
    main()
