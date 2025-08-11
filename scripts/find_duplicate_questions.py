#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Finds and optionally removes duplicate questions from the database based on prompt text.

This script helps maintain database quality by identifying questions that share
the exact same prompt text. It can either report on these duplicates or actively
remove them, retaining only the first instance of each question.
"""
import argparse
import os
import sys
from collections import defaultdict

# Add project root to path for local imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from kubelingo.database import get_db_connection, get_all_questions, DATABASE_FILE


def find_duplicates():
    """
    Finds questions with duplicate prompts in the database.

    It leverages get_all_questions() and assumes that get_db_connection() has
    been called to point to the correct database.

    Returns:
        A dictionary where keys are duplicate prompts and values are lists of
        question dicts, sorted by question ID.
    """
    questions = get_all_questions()

    prompts = defaultdict(list)
    for q in questions:
        prompts[q['prompt']].append(q)

    duplicates = {}
    for prompt, q_list in prompts.items():
        if len(q_list) > 1:
            # Sort by ID to ensure consistent "first" item
            q_list.sort(key=lambda x: x['id'])
            duplicates[prompt] = q_list

    return duplicates


def manage_duplicates(conn, duplicates, delete=False):
    """
    Lists or deletes duplicate questions.

    Args:
        conn: A sqlite3.Connection object for database writes.
        duplicates: A dict of duplicate questions from find_duplicates().
        delete (bool): If True, delete duplicates from the DB. Otherwise, just print them.
    """
    if not duplicates:
        print("No duplicate questions found.")
        return

    print(f"Found {len(duplicates)} prompts with duplicate questions.")

    if delete:
        cursor = conn.cursor()
        deleted_count = 0
        print("\nDeleting duplicates (keeping the first occurrence of each)...")
    else:
        print("\nListing duplicate questions (use --delete to remove):")

    for prompt, q_list in duplicates.items():
        print(f"\n- Prompt: \"{prompt}\"")
        print(f"  - Keeping: {q_list[0]['id']} (source: {q_list[0]['source_file']})")

        ids_to_delete = [q['id'] for q in q_list[1:]]

        for q in q_list[1:]:
            status = "Deleting" if delete else "Duplicate"
            print(f"  - {status}: {q['id']} (source: {q['source_file']})")

        if delete and ids_to_delete:
            placeholders = ', '.join('?' for _ in ids_to_delete)
            cursor.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", ids_to_delete)
            deleted_count += len(ids_to_delete)

    if delete:
        conn.commit()
        print(f"\nSuccessfully deleted {deleted_count} duplicate questions.")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Find and optionally remove duplicate questions from the database.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Examples:
  # Dry-run: view all duplicate questions
  ./scripts/deduplicate_questions.py

  # Find and delete all duplicates, leaving one copy of each
  ./scripts/deduplicate_questions.py --delete"""
    )
    parser.add_argument(
        "--db-path",
        default=DATABASE_FILE,
        help=f"Path to the SQLite database file (default: {DATABASE_FILE})"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete duplicate questions, keeping the first occurrence of each."
    )
    args = parser.parse_args()

    if not os.path.exists(args.db_path):
        print(f"Error: Database file not found at {args.db_path}", file=sys.stderr)
        sys.exit(1)

    conn = None
    try:
        # get_db_connection will be used by get_all_questions and for deletion
        conn = get_db_connection(args.db_path)

        duplicates = find_duplicates()
        manage_duplicates(conn, duplicates, delete=args.delete)

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
