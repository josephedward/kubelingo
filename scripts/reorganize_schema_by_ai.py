#!/usr/bin/env python3
"""
Reorganize questions in the database by AI-driven schema_category classification.

This script scans all questions in the SQLite database, uses the OpenAI API to classify each
question prompt into one of the three schema categories (Basic/Open-Ended, Command-Based/Syntax,
Manifests), and updates the `schema_category` column accordingly.

Usage:
  pip install openai
  export OPENAI_API_KEY=your_key_here   # or configure via `kubelingo config set openai`
  python3 scripts/reorganize_schema_by_ai.py [--dry-run] [--model MODEL]
"""
import argparse
import os
import sys
import sqlite3

try:
    import openai
except ImportError:
    print("Error: openai package not installed. Run `pip install openai`.")
    sys.exit(1)

from kubelingo.database import get_db_connection
from kubelingo.utils.config import get_api_key, DATABASE_FILE

ALLOWED_CATEGORIES = [
    "Basic/Open-Ended",
    "Command-Based/Syntax",
    "Manifests",
]

def classify(prompt: str, model: str) -> str:
    """Use OpenAI to classify a prompt into one of the allowed categories."""
    system_msg = (
        "You are a classification assistant for Kubernetes quiz questions.\n"
        "Classify each question into exactly one of: Basic/Open-Ended, Command-Based/Syntax, Manifests.\n"
        "Reply with only the category name, no additional text."
    )
    user_msg = f"Question: {prompt.strip()}"
    resp = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0,
        max_tokens=16,
    )
    category = resp.choices[0].message.content.strip()
    return category

def main():
    parser = argparse.ArgumentParser(description="AI-driven schema_category updater for kubelingo DB.")
    parser.add_argument("--dry-run", action="store_true", help="Show classifications without updating DB.")
    parser.add_argument("--model", type=str, default="gpt-3.5-turbo", help="OpenAI model to use.")
    args = parser.parse_args()

    # Initialize API key
    api_key = os.getenv('OPENAI_API_KEY') or get_api_key()
    if not api_key:
        print("Error: No OpenAI API key configured. Use OPENAI_API_KEY or `kubelingo config set openai`.")
        sys.exit(1)
    openai.api_key = api_key

    # Connect to DB
    db_path = DATABASE_FILE
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch all questions
    cursor.execute("SELECT id, prompt, schema_category FROM questions")
    rows = cursor.fetchall()
    print(f"Found {len(rows)} questions in {db_path}")

    updated = {cat: 0 for cat in ALLOWED_CATEGORIES}
    for row in rows:
        qid = row['id']
        prompt = row['prompt']
        current = row['schema_category']
        try:
            new_cat = classify(prompt, args.model)
        except Exception as e:
            print(f"[Error] Classification failed for {qid}: {e}")
            continue
        if new_cat not in ALLOWED_CATEGORIES:
            print(f"[Warning] Invalid category '{new_cat}' for question {qid}, skipping.")
            continue
        if current == new_cat:
            continue
        print(f"{qid}: {current} -> {new_cat}")
        if not args.dry_run:
            cursor.execute(
                "UPDATE questions SET schema_category = ? WHERE id = ?",
                (new_cat, qid)
            )
            updated[new_cat] += 1

    if not args.dry_run:
        conn.commit()
        print("\nUpdates applied:")
        for cat, cnt in updated.items():
            print(f"  {cat}: {cnt}")
    else:
        print("(dry-run) no changes applied.")

    conn.close()

if __name__ == '__main__':
    main()