#!/usr/bin/env python3
"""
Compare two SQLite databases (schema only) and report differences.
"""
import sys
import argparse
import sqlite3
import difflib
from pathlib import Path

def load_schema(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE sql NOT NULL ORDER BY type, name"
    )
    rows = cursor.fetchall()
    conn.close()
    # Return list of normalized SQL statements
    stmts = [row[0].strip() + ';' for row in rows if row[0]]
    return stmts

def main():
    parser = argparse.ArgumentParser(
        description="Diff schema of two SQLite database files."
    )
    parser.add_argument(
        'db_a', help='First SQLite database file'
    )
    parser.add_argument(
        'db_b', nargs='?', help='Second SQLite database file (defaults to active DB)'
    )
    parser.add_argument(
        '--schema-only', action='store_true', help='Only compare schema (default)'
    )
    args = parser.parse_args()

    a = Path(args.db_a)
    if not a.is_file():
        print(f"File not found: {a}")
        sys.exit(1)
    b = Path(args.db_b) if args.db_b else None
    if b and not b.is_file():
        print(f"File not found: {b}")
        sys.exit(1)

    # Load schemas
    schema_a = load_schema(str(a))
    schema_b = load_schema(str(b)) if b else []

    # Diff
    diff = difflib.unified_diff(
        schema_a,
        schema_b,
        fromfile=str(a),
        tofile=str(b) if b else 'new_db',
        lineterm=''
    )
    for line in diff:
        print(line)

if __name__ == '__main__':
    main()