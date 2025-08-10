#!/usr/bin/env python3
"""
Script to extract text from a PDF and generate new quiz questions using AI,
while verifying against the existing database to avoid duplicates.
"""
import argparse
import os
import subprocess
import sqlite3

from kubelingo.modules.question_generator import AIQuestionGenerator
from kubelingo.database import get_db_connection, add_question


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text content from a PDF using pdftotext."""
    try:
        result = subprocess.run(
            ["pdftotext", pdf_path, "-"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""


def prompt_exists(conn: sqlite3.Connection, prompt: str) -> bool:
    """Check if a question prompt already exists in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM questions WHERE prompt = ?", (prompt,))
    return cursor.fetchone() is not None


def generate_questions_from_pdf(pdf_path: str, num_questions: int = 5):
    """Generate and insert new questions from PDF content."""
    text = extract_text_from_pdf(pdf_path)
    if not text:
        print("No text extracted; aborting.")
        return

    # Truncate text for AI prompt to avoid token limits
    snippet = text[:4000]
    subject = f"Generate {num_questions} new, distinct Kubernetes quiz questions based on the following PDF content:\n\n{snippet}"

    generator = AIQuestionGenerator()
    # Generate questions using AI
    new_questions = generator.generate_questions(subject, num_questions=num_questions)

    conn = get_db_connection()
    for q in new_questions:
        if prompt_exists(conn, q.prompt):
            print(f"Skipping existing question: {q.prompt}")
            continue
        # Insert new question into database
        add_question(
            conn,
            id=q.id,
            prompt=q.prompt,
            response=q.response,
            category="killershell",
            source="pdf",
            source_file=os.path.basename(pdf_path),
            validation_steps=q.validation_steps or [],
            validator=q.validator or {},
            review=False,
            explanation=None,
            pre_shell_cmds=getattr(q, "pre_shell_cmds", None) or [],
            initial_files=getattr(q, "initial_files", None),
            question_type=getattr(q, "type", None),
        )
        conn.commit()
        print(f"Added question {q.id}")
    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Extract PDF content and generate new quiz questions."
    )
    parser.add_argument(
        "pdf_path",
        help="Path to the PDF file containing quiz content.",
    )
    parser.add_argument(
        "-n",
        "--num",
        type=int,
        default=5,
        help="Number of questions to generate.",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.pdf_path):
        print(f"PDF file not found: {args.pdf_path}")
        return
    generate_questions_from_pdf(args.pdf_path, args.num)


if __name__ == "__main__":
    main()