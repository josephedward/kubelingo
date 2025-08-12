#!/usr/bin/env python3
"""
Normalize the `source_file` entries in Kubelingo's questions DB to use only basenames.

This script will strip any directory components from the `source_file` column,
so that entries like '/full/path/to/kubectl_pod_management_quiz.yaml' become
'kubectl_pod_management_quiz.yaml'.
"""
import os
import sqlite3
from kubelingo.utils.config import DATABASE_FILE

def main():
    # Connect to the questions database
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    # Fetch all current source_file values
    cursor.execute("SELECT id, source_file FROM questions")
    rows = cursor.fetchall()
    updated = 0
    for qid, src in rows:
        # Compute normalized basename
        base = os.path.basename(src) if src else src
        if base and base != src:
            cursor.execute(
                "UPDATE questions SET source_file = ? WHERE id = ?",
                (base, qid)
            )
            updated += 1
    conn.commit()
    conn.close()
    print(f"Updated {updated} source_file entries in {DATABASE_FILE}")

if __name__ == '__main__':
    main()