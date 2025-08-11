#!/usr/bin/env python3
"""
Export the Kubelingo questions database to a YAML backup file.
"""
import argparse
import os
import sys
import sqlite3
import datetime

try:
    import yaml
except ImportError:
    print("PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

from kubelingo.database import get_db_connection

def main():
    parser = argparse.ArgumentParser(description='Export questions DB to YAML')
    parser.add_argument('-o', '--output', help='Output YAML file path')
    args = parser.parse_args()

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    if args.output:
        out_file = args.output
    else:
        out_dir = 'backups'
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, f'questions_{timestamp}.yaml')

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT * FROM questions')
    rows = cur.fetchall()

    data = [dict(r) for r in rows]
    with open(out_file, 'w') as f:
        yaml.safe_dump(data, f)

    print(f'Exported {len(data)} questions to {out_file}')

if __name__ == '__main__':
    main()