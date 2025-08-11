#!/usr/bin/env python3
"""
Interactively fix or assign schema_category for questions in the database.
"""
import sys
import argparse
from kubelingo.database import get_all_questions, get_db_connection

def main():
    parser = argparse.ArgumentParser(
        description="Fix missing or incorrect schema_category for database questions."
    )
    parser.add_argument(
        '--list-only', action='store_true',
        help='Only list questions needing category assignment'
    )
    args = parser.parse_args()

    questions = get_all_questions()
    to_fix = [q for q in questions if not q.get('schema_category')]
    if not to_fix:
        print("All questions have a schema_category assigned.")
        return
    for q in to_fix:
        print(f"ID: {q.get('id')} | Current category: {q.get('schema_category')}\nPrompt: {q.get('prompt')[:80]}...")
        if args.list_only:
            continue
        new_cat = input("Enter new schema_category (or leave blank to skip): ").strip()
        if not new_cat:
            print("Skipped.\n")
            continue
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE questions SET schema_category = ? WHERE id = ?",
                (new_cat, q.get('id'))
            )
            conn.commit()
            print("Updated.\n")
        except Exception as e:
            print(f"Failed to update: {e}\n")
        finally:
            conn.close()
    print("Done fixing schema categories.")

if __name__ == '__main__':
    main()