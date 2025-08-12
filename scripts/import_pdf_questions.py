#!/usr/bin/env python3
"""
Import new quiz questions from the "Killer Shell - Exam Simulators.pdf" into the Kubelingo database.

This script extracts text from the PDF, parses each "Question <n> | <title>" block,
checks if that question already exists in the live DB, and if not, inserts it.
After importing, it backs up the updated live DB to the project backup.
"""
import os
import re
import sys
import subprocess
import tempfile
import shutil

from kubelingo.database import init_db, add_question, get_db_connection
from kubelingo.utils.config import DATABASE_FILE, BACKUP_DATABASE_FILE

def main():
    # Initialize DB
    init_db()
    # Locate PDF in project root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    pdf_path = os.path.join(project_root, 'Killer Shell - Exam Simulators.pdf')
    if not os.path.isfile(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        return

    # Convert PDF to text via pdftotext
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
        txt_path = tmp.name
    try:
        subprocess.run(['pdftotext', pdf_path, txt_path], check=True)
    except Exception as e:
        print(f"Failed to extract text from PDF: {e}")
        return

    # Read extracted text
    with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()

    # Split into question blocks by "Question <n> |"
    parts = re.split(r"Question\s+(\d+)\s*\|", text)
    # parts: [pre, num1, content1, num2, content2, ...]
    imported = 0
    for i in range(1, len(parts), 2):
        qnum = parts[i].strip()
        content = parts[i+1].strip()
        # First line is title, rest is body
        lines = content.splitlines()
        if not lines:
            continue
        title = lines[0].strip()
        body = '\n'.join(lines[1:]).strip()
        prompt = f"Simulator Question {qnum}: {title}\n{body}" if body else f"Simulator Question {qnum}: {title}"

        # Check DB for existing entries
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM questions WHERE prompt LIKE ?", (f"%Simulator Question {qnum}:%",)
        )
        exists = cursor.fetchone()[0] > 0
        conn.close()
        if exists:
            print(f"Skipping Question {qnum}, already in DB.")
            continue

        # Insert new question
        qid = f"sim_pdf::{qnum}"
        try:
            add_question(
                id=qid,
                prompt=prompt,
                source_file='pdf_simulator',
                response=None,
                category='Simulator',
                source='pdf',
                validation_steps=[],
                validator=None,
            )
            print(f"Added Question {qnum} to DB.")
            imported += 1
        except Exception as e:
            print(f"Failed to add Question {qnum}: {e}")

    print(f"Imported {imported} new questions from PDF.")

    # Backup updated DB
    try:
        shutil.copy2(DATABASE_FILE, BACKUP_DATABASE_FILE)
        print(f"Backed up live DB to {BACKUP_DATABASE_FILE}")
    except Exception as e:
        print(f"Failed to backup DB: {e}")

if __name__ == '__main__':
    main()