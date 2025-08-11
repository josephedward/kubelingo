#!/usr/bin/env python3
"""
Locates the most recent YAML backup file by timestamp.
"""
import argparse
import sys
import re
from pathlib import Path
from typing import List, Optional

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.utils.config import YAML_BACKUP_DIRS
from kubelingo.utils.path_utils import find_yaml_files_from_paths


def get_backup_files(directories: List[str], pattern: Optional[str] = None) -> List[Path]:
    """Finds all YAML backup files in the given directories, optionally filtering by a regex pattern."""
    all_files = find_yaml_files_from_paths(directories)

    if pattern:
        regex = re.compile(pattern)
        all_files = [f for f in all_files if regex.search(str(f))]

    return all_files


def main():
    """Main function to locate the most recent YAML backup file."""
    parser = argparse.ArgumentParser(
        description="Locate the most recent YAML backup file by timestamp.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "dirs",
        nargs="*",
        default=[],
        help="One or more directories to scan. If not provided, uses all configured default backup directories.",
    )
    parser.add_argument("--pattern", help="Regex pattern to filter file paths.")
    args = parser.parse_args()

    scan_dirs = args.dirs or YAML_BACKUP_DIRS

    try:
        files = get_backup_files(scan_dirs, args.pattern)
    except Exception as e:
        print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)

    if not files:
        dirs_str = ', '.join(scan_dirs)
        print(f"No YAML backups found in {dirs_str}", file=sys.stderr)
        sys.exit(0)

    latest_file = max(files, key=lambda p: p.stat().st_mtime)
    print(str(latest_file))


if __name__ == "__main__":
    main()
