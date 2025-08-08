"""
Generates new quiz questions from a PDF document using an AI model,
ensuring the questions are not duplicates of existing ones in the database.
"""

import argparse
import os
import sys
import yaml
import sqlite3
from typing import List, Dict, Any

# Ensure kubelingo modules can be imported
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, PROJECT_ROOT)

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF not found. Please install it with 'pip install pymupdf'", file=sys.stderr)
    sys.exit(1)

try:
    import openai
except ImportError:
    print("openai package not found. Please install it with 'pip install openai'", file=sys.stderr)
    sys.exit(1)

from kubelingo.database import get_db_connection


def get_existing_prompts() -> List[str]:
    """Fetches all existing question prompts from the database."""
    prompts = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT prompt FROM questions")
        rows = cursor.fetchall()
        prompts = [row[0] for row in rows if row[0]]
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Found {len(prompts)} existing questions in the database.")
    return prompts


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text from a PDF file."""
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}", file=sys.stderr)
        sys.exit(1)

    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        print(f"Extracted {len(text.split())} words from {pdf_path}.")
        return text
    except Exception as e:
        print(f"Error processing PDF file: {e}", file=sys.stderr)
        sys.exit(1)


def generate_questions_from_text(
    text: str, existing_prompts: List[str], num_questions_per_chunk: int = 5
) -> List[Dict[str, Any]]:
    """Generates new questions from text using AI, avoiding existing ones."""
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    client = openai.OpenAI()

    system_prompt = """You are an expert Kubernetes administrator and trainer creating quiz questions for the CKAD exam from a provided document.
Your task is to generate new questions based on the text.
The questions should be unique and not overlap with the provided list of existing questions.
Output ONLY a YAML list of question objects. Each object must have 'id', 'question', 'answers' (a list), 'explanation', and 'source'. Use a generic source like 'Killer Shell PDF'.
The 'id' should be unique, perhaps using a slug of the question.

Example output format:
- id: create-pod-with-image
  question: How do you create a pod named 'nginx' with the image 'nginx:latest'?
  answers:
    - "kubectl run nginx --image=nginx:latest"
  explanation: "The 'kubectl run' command is used to create a pod from an image."
  source: "Killer Shell PDF"
"""

    words = text.split()
    chunk_size = 4000  # words per chunk
    chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]

    all_generated_questions = []

    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)}...")

        user_prompt = f"""
Here is a chunk of text from a Kubernetes document:
---
{chunk}
---

Here is a list of existing question prompts to avoid creating duplicates:
---
{existing_prompts}
---

Please generate {num_questions_per_chunk} new questions from the text chunk above. Ensure they are in the specified YAML format.
"""

        try:
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.5,
            )

            content = response.choices[0].message.content
            try:
                if content.strip().startswith("```yaml"):
                    content = content.strip()[7:-3].strip()
                elif content.strip().startswith("```"):
                    content = content.strip()[3:-3].strip()

                generated_questions = yaml.safe_load(content)
                if isinstance(generated_questions, list):
                    all_generated_questions.extend(generated_questions)
                    print(f"Successfully generated {len(generated_questions)} questions from chunk {i+1}.")
                else:
                    print(f"Warning: AI returned non-list data for chunk {i+1}. Skipping.", file=sys.stderr)
            except (yaml.YAMLError, TypeError) as e:
                print(f"Warning: Could not parse YAML response from AI for chunk {i+1}. Error: {e}", file=sys.stderr)
                print("AI Response was:\n" + content, file=sys.stderr)

        except openai.APIError as e:
            print(f"OpenAI API error on chunk {i+1}: {e}", file=sys.stderr)

    return all_generated_questions


def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description="Generate Kubelingo quiz questions from a PDF.")
    parser.add_argument("--pdf-path", required=True, help="Path to the PDF file.")
    parser.add_argument("--output-file", required=True, help="Path to save the generated YAML file.")
    parser.add_argument(
        "--num-questions-per-chunk", type=int, default=5, help="Number of questions to generate per text chunk."
    )
    args = parser.parse_args()

    existing_prompts = get_existing_prompts()
    pdf_text = extract_text_from_pdf(args.pdf_path)
    new_questions = generate_questions_from_text(pdf_text, existing_prompts, args.num_questions_per_chunk)

    if not new_questions:
        print("No new questions were generated. Exiting.")
        return

    output_dir = os.path.dirname(args.output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    try:
        with open(args.output_file, 'w') as f:
            yaml.dump(new_questions, f, default_flow_style=False, sort_keys=False)
        print(f"\nSuccessfully saved {len(new_questions)} new questions to {args.output_file}")
        print("Please review the generated file before importing it into the database.")
    except Exception as e:
        print(f"Error writing to output file: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
