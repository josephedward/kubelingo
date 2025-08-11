#!/usr/bin/env python3
"""
Load questions from a YAML backup into the live database.
"""
import argparse
import os
import sys
import sqlite3

try:
    import yaml
except ImportError:
    print("PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

from kubelingo.database import get_db_connection, add_question

def main():
    parser = argparse.ArgumentParser(description='Write DB from YAML backup')
    parser.add_argument('yaml_file', help='YAML file to load')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing questions')
    args = parser.parse_args()
    if not os.path.exists(args.yaml_file):
        print('File not found:', args.yaml_file, file=sys.stderr)
        sys.exit(1)
    if args.overwrite:
        conn = get_db_connection()
        conn.execute('DELETE FROM questions')
        conn.commit()
        conn.close()
    with open(args.yaml_file) as f:
        data = yaml.safe_load(f) or []
    conn = get_db_connection()
    for q in data:
        try:
            add_question(conn=conn, **q)
        except Exception as e:
            print('Error importing question', q.get('id'), e, file=sys.stderr)
    conn.close()
    print(f'Loaded {len(data)} questions into the database.')

if __name__ == '__main__':
    main()