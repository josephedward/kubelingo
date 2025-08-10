#!/usr/bin/env python3
"""
Reclassify all questions in the Kubelingo database into the three immutable schema categories
using OpenAI's classification: Basic/Open-Ended, Command-Based/Syntax, Manifests.
"""
import os
import sqlite3
import sys

try:
    import openai
except ImportError:
    print("Error: openai package is required. Install with `pip install openai`. ")
    sys.exit(1)

from kubelingo.utils.config import DATABASE_FILE

def classify_prompt(prompt, model="gpt-3.5-turbo"):
    """Ask OpenAI to classify a question into one of the three schema categories."""
    system = (
        "You are a classification assistant for Kubernetes quiz questions.\n"
        "Given a question prompt, classify it as exactly one of: Basic/Open-Ended, "
        "Command-Based/Syntax, or Manifests. Respond with the category name only."
    )
    user = f"Question: {prompt}\nCategory:"  # model completes the category
    try:
        resp = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0
        )
        text = resp.choices[0].message.content.strip()
        # Normalize exact names
        for allowed in ["Basic/Open-Ended", "Command-Based/Syntax", "Manifests"]:
            if allowed.lower() in text.lower():
                return allowed
        # Fallback: return text as-is
        return text
    except Exception as e:
        print(f"Error during classification: {e}")
        return None

def main():
    api_key = os.getenv("OPENAI_API_KEY") or None
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        sys.exit(1)
    openai.api_key = api_key

    # Connect to DB
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, prompt, schema_category FROM questions")
    rows = cursor.fetchall()
    total = len(rows)
    print(f"Found {total} questions in the database.")
    for idx, row in enumerate(rows, start=1):
        qid = row["id"]
        prompt = row["prompt"]
        current = row["schema_category"]
        print(f"[{idx}/{total}] ID={qid} (current={current})...", end=" ")
        category = classify_prompt(prompt)
        if category and category != current:
            cursor.execute(
                "UPDATE questions SET schema_category = ? WHERE id = ?",
                (category, qid)
            )
            conn.commit()
            print(f"updated to {category}")
        else:
            print("no change")
    conn.close()

if __name__ == '__main__':
    main()