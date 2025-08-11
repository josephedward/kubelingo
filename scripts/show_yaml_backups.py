#!/usr/bin/env python3
"""Lists all YAML backup files."""

import sys
from pathlib import Path

# Add project root to sys.path to allow importing from kubelingo
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from kubelingo.utils.path_utils import find_yaml_files, get_all_yaml_backup_dirs

def main():
    """Finds and prints paths of all YAML backup files."""
    backup_dirs = get_all_yaml_backup_dirs()
    if not backup_dirs:
        print("No YAML backup directories found.")
        return

    yaml_files = find_yaml_files(backup_dirs)

    if not yaml_files:
        print("No YAML backup files found.")
        return

    print("Found YAML backup files:")
    for file_path in sorted(yaml_files):
        print(f"  - {file_path}")

if __name__ == "__main__":
    main()
