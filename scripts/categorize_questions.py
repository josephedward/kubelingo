#!/usr/bin/env python3
"""
Identify questions with missing or invalid subject and optionally assign one.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
from kubelingo.database import get_db_connection, SUBJECT_MATTER

def main():
    parser = argparse.ArgumentParser(description='Categorize questions by subject')
    parser.add_argument(
        '--assign', nargs=2, metavar=('ROWID', 'SUBJECT'),
        help='Assign SUBJECT to the question with given ROWID'
    )
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor()

    if args.assign:
        rowid, subject = args.assign
        if subject not in SUBJECT_MATTER:
            print(f"Invalid subject. Must be one of: {SUBJECT_MATTER}")
            sys.exit(1)
        cur.execute('UPDATE questions SET subject = ? WHERE rowid = ?', (subject, rowid))
        conn.commit()
        print(f"Assigned subject '{subject}' to question rowid {rowid}")
    else:
        cur.execute('SELECT rowid, id, prompt, subject FROM questions')
        rows = cur.fetchall()
        missing = []
        for row in rows:
            subj = row[3]
            if subj not in SUBJECT_MATTER:
                missing.append(row)
        if not missing:
            print('All questions have valid subjects.')
        else:
            print('Questions with missing or invalid subjects:')
            for row in missing:
                print(f"[{row[0]}] id={row[1]} subject={row[3]}\n  Prompt: {row[2]!r}\n")
    conn.close()

if __name__ == '__main__':
    main()