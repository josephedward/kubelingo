#!/usr/bin/env python3
"""
Display the SQLite database schema (tables, indexes, triggers) for the Kubelingo application.
"""
import sys
import argparse
from pathlib import Path

# Ensure project root on path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.database import get_db_connection
from kubelingo.utils.config import DATABASE_FILE

def main():
    parser = argparse.ArgumentParser(
        description="Show the SQLite database schema for Kubelingo."
    )
    parser.add_argument(
        '-d', '--db-path',
        type=str,
        default=None,
        help=f"Path to SQLite DB file (default: {DATABASE_FILE})"
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        help="Write schema to a file instead of stdout"
    )
    args = parser.parse_args()

    # Connect to DB (None => default DATABASE_FILE)
    conn = get_db_connection(db_path=args.db_path)
    cursor = conn.cursor()

    # Query schema entries
    cursor.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE sql NOT NULL ORDER BY type, name"
    )
    rows = cursor.fetchall()
    conn.close()

    # Collect SQL statements
    statements = []
    for row in rows:
        sql = row[3].strip()
        if sql:
            statements.append(sql + ';')

    output_text = '\n\n'.join(statements)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output_text)
        print(f"Schema written to {out_path}")
    else:
        print(output_text)

if __name__ == '__main__':
    main()