#!/usr/bin/env python3
"""
Reclassify all questions in the Kubelingo database into the three immutable schema categories
using OpenAI's classification: Basic/Open-Ended, Command-Based/Syntax, Manifests.
"""
import sys
print("DEPRECATED: use the new single-purpose maintenance scripts (see docs/scripts.md) instead of reorganize_questions.py.")
sys.exit(1)
import os
import sqlite3
import sys

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai package is required. Install with `pip install openai`. ")
    sys.exit(1)

from kubelingo.utils.config import DATABASE_FILE, SUBJECT_MATTER

def classify_prompt(client, prompt, model="gpt-3.5-turbo"):
    """Ask OpenAI to classify a question into one of the three schema categories."""
    system = (
        "You are a classification assistant for Kubernetes quiz questions.\n"
        "Given a question prompt, classify it as exactly one of: Basic/Open-Ended, "
        "Command-Based/Syntax, or Manifests. Respond with the category name only."
    )
    user = f"Question: {prompt}\nCategory:"  # model completes the category
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0
        )
        text = resp.choices[0].message.content.strip()
        # Normalize exact names
        text_lower = text.lower()
        for allowed in ["Basic/Open-Ended", "Command-Based/Syntax", "Manifests"]:
            if text_lower in allowed.lower():
                return allowed
        # Fallback: if no match, do not return arbitrary text.
        return None
    except Exception as e:
        print(f"Error during classification: {e}")
        return None

def classify_subject(client, prompt, model="gpt-3.5-turbo"):
    """Ask OpenAI to classify a question into a subject matter category."""
    system_prompt = (
        "You are a classification assistant for Kubernetes quiz questions.\n"
        "Given a question prompt, classify it into exactly one of the following subject matter categories.\n"
        "Respond with the category name only.\n\n"
        "Categories:\n" + "\n".join(f"- {s}" for s in SUBJECT_MATTER)
    )
    user_prompt = f"Question: {prompt}\nCategory:"
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0
        )
        text = resp.choices[0].message.content.strip()
        # Find which official category is mentioned in the AI's response.
        for cat in SUBJECT_MATTER:
            # Match against the primary name, e.g., "Core workloads"
            primary_name = cat.split('(')[0].strip()
            if primary_name.lower() in text.lower():
                return cat

        # Fallback for cases where AI gives an exact match to a full category string
        if text in SUBJECT_MATTER:
            return text

        print(f" (subject classification failed: '{text}')", end="")
        return None
    except Exception as e:
        print(f"Error during subject classification: {e}")
        return None

def main():
    api_key = os.getenv("OPENAI_API_KEY") or None
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        sys.exit(1)
    client = OpenAI(api_key=api_key)

    # Connect to DB
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, prompt, schema_category, subject FROM questions")
    rows = cursor.fetchall()
    total = len(rows)
    print(f"Found {total} questions in the database.")
    for idx, row in enumerate(rows, start=1):
        qid = row["id"]
        prompt = row["prompt"]
        current_schema = row["schema_category"]
        current_subject = row["subject"]
        print(f"[{idx}/{total}] ID={qid} (schema={current_schema}, subject={current_subject})...", end="")

        new_schema = classify_prompt(client, prompt)
        new_subject = classify_subject(client, prompt)

        updates = []
        params = []
        log_msgs = []

        if new_schema and new_schema != current_schema:
            updates.append("schema_category = ?")
            params.append(new_schema)
            log_msgs.append(f"schema -> {new_schema}")

        if new_subject and new_subject != current_subject:
            updates.append("subject = ?")
            params.append(new_subject)
            log_msgs.append(f"subject -> {new_subject}")

        if updates:
            params.append(qid)
            cursor.execute(
                f"UPDATE questions SET {', '.join(updates)} WHERE id = ?",
                tuple(params)
            )
            conn.commit()
            print(f" updated: {', '.join(log_msgs)}")
        else:
            print(" no change")
    conn.close()

if __name__ == '__main__':
    main()
