#!/usr/bin/env python3
"""
Backup current DB and restore from a YAML backup file.
"""
import argparse
import os
import shutil
import sys

from kubelingo.utils.config import DATABASE_FILE

def main():
    import write_db_from_yaml
    parser = argparse.ArgumentParser(description='Restore DB from YAML backup')
    parser.add_argument('yaml_file', help='YAML file to restore')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing questions')
    args = parser.parse_args()
    if not os.path.exists(args.yaml_file):
        print('File not found:', args.yaml_file, file=sys.stderr)
        sys.exit(1)
    backup_path = DATABASE_FILE + '.pre_restore.bak'
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    shutil.copy(DATABASE_FILE, backup_path)
    print(f'Backed up current database to {backup_path}')
    sys.argv = ['write_db_from_yaml.py', args.yaml_file]
    if args.overwrite:
        sys.argv.append('--overwrite')
    write_db_from_yaml.main()

if __name__ == '__main__':
    main()