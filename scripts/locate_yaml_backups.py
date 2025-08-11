#!/usr/bin/env python3
"""
List YAML backup files in configured backup locations or specified directories.
"""
import argparse
import os
import sys

# Ensure project root is in python path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, str(project_root))

from kubelingo.utils.path_utils import get_all_yaml_files, get_all_yaml_backups
from kubelingo.utils.config import YAML_BACKUP_DIRS


def main():
    parser = argparse.ArgumentParser(description='Locate YAML backup files in configured backup locations or specified directories.')
    parser.add_argument('--source-dir', action='append', dest='source_dirs', help='Specific directory to scan. Can be used multiple times.')
    args = parser.parse_args()

    if args.source_dirs:
        dirs_to_scan = args.source_dirs
        print(f"Scanning specified directories: {dirs_to_scan}")
        files = get_all_yaml_files(dirs=dirs_to_scan)
    else:
        dirs_to_scan = YAML_BACKUP_DIRS
        print(f"Scanning default backup directories: {dirs_to_scan}")
        files = get_all_yaml_backups()

    if not files:
        print('No YAML backups found in:', dirs_to_scan)
        sys.exit(0)

    print(f"\nFound {len(files)} backup files:")
    for path in sorted(files):
        size = os.path.getsize(path)
        mtime = os.path.getmtime(path)
        print(f"{path}  {size} bytes  modified={mtime}")


if __name__ == '__main__':
    main()
