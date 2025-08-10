#!/usr/bin/env python3
"""
Reassign all questions in the Kubelingo SQLite database to one of the three immutable schema categories.

This script reads each question's `question_type` column and updates its `schema_category`:
  - question_type in ('yaml_author', 'yaml_edit', 'live_k8s_edit') -> 'Manifests'
  - question_type in ('command', 'live_k8s') -> 'Command-Based/Syntax'
  - question_type == 'socratic'      -> 'Basic/Open-Ended'
  - otherwise                         -> 'Command-Based/Syntax'
"""
import sqlite3
from kubelingo.database import get_db_connection
from kubelingo.question import QuestionCategory

def map_type_to_schema(q_type: str) -> str:
    q = (q_type or '').lower()
    if q in ('yaml_author', 'yaml_edit', 'live_k8s_edit'):
        return QuestionCategory.MANIFEST.value
    if q in ('command', 'live_k8s'):
        return QuestionCategory.COMMAND.value
    if q == 'socratic':
        return QuestionCategory.OPEN_ENDED.value
    # default fallback
    return QuestionCategory.COMMAND.value

def main():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Fetch all question IDs and their type
    cursor.execute("SELECT id, question_type FROM questions")
    rows = cursor.fetchall()
    total = len(rows)
    updated = 0
    for row in rows:
        qid = row['id']
        q_type = row['question_type'] or ''
        new_cat = map_type_to_schema(q_type)
        cursor.execute(
            "UPDATE questions SET schema_category = ? WHERE id = ?", (new_cat, qid)
        )
        # sqlite3 returns -1 for executemany or unknown; treat any non-zero as updated
        if cursor.rowcount != 0:
            updated += 1
    conn.commit()
    conn.close()
    print(f"Reassigned schema_category for {updated}/{total} questions.")

if __name__ == '__main__':
    main()