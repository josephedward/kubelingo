#!/usr/bin/env python3
"""
Find and optionally remove duplicate quiz questions in the Kubelingo database.

This script lists any prompts that appear more than once in the live database
(`~/.kubelingo/kubelingo.db`). With the `--delete` flag, it deletes all but
the earliest entry for each duplicate prompt, preserving the first.
"""
import os
import sqlite3
import argparse

from kubelingo.utils.config import DATABASE_FILE

def find_duplicates(conn):
    """Return a list of (prompt, count) tuples for prompts duplicated >1."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT prompt, COUNT(*) as cnt FROM questions GROUP BY prompt HAVING cnt > 1"
    )
    return cursor.fetchall()

def list_and_optionally_delete(conn, delete=False):
    dups = find_duplicates(conn)
    if not dups:
        print("No duplicate prompts found in the database.")
        return
    total_deleted = 0
    for prompt, count in dups:
        print(f"Prompt duplicated {count} times: {prompt!r}")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT rowid, id, source_file FROM questions WHERE prompt = ? ORDER BY rowid",
            (prompt,)
        )
        rows = cursor.fetchall()
        for rowid, qid, src in rows:
            print(f"  rowid={rowid}, id={qid}, source_file={src}")
        if delete:
            # Keep first row, delete the rest
            to_delete = [str(r[0]) for r in rows[1:]]
            placeholders = ",".join(to_delete)
            if to_delete:
                conn.execute(f"DELETE FROM questions WHERE rowid IN ({placeholders})")
                print(f"  Deleted {len(to_delete)} duplicates for this prompt.")
                total_deleted += len(to_delete)
    if delete:
        conn.commit()
        print(f"Total duplicates deleted: {total_deleted}")

def main():
    parser = argparse.ArgumentParser(
        description="Find and optionally delete duplicate quiz questions in the Kubelingo DB"
    )
    parser.add_argument(
        '--delete', action='store_true',
        help='Delete duplicate entries, keeping only the first occurrence'
    )
    args = parser.parse_args()

    db_path = DATABASE_FILE
    if not os.path.isfile(db_path):
        print(f"Database file not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    list_and_optionally_delete(conn, delete=args.delete)
    conn.close()

if __name__ == '__main__':
    main()