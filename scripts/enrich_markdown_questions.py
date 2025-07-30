#!/usr/bin/env python
import os
import re
import sys
from typing import List, Optional

try:
    import openai
except ImportError:
    print(
        "Error: openai library not found. Please install it with 'pip install openai'",
        file=sys.stderr,
    )
    sys.exit(1)


def get_openai_client() -> openai.OpenAI:
    """Returns an OpenAI client, expecting API key from environment."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)
    return openai.OpenAI(api_key=api_key)


def enrich_question(
    client: openai.OpenAI, previous_question: str, current_question: str
) -> Optional[str]:
    """Uses OpenAI to enrich a question with context from the previous one."""
    prompt = f"""As a Kubernetes expert creating educational material, I have two quiz questions. The second question depends on the first. Please rewrite the second question to be self-contained by adding context from the first.

First question: "{previous_question}"

Second question: "{current_question}"

Rewrite the second question. Provide only the rewritten question text, without any introductory phrases or explanations. For example, if the rewritten question is "Create a pod named 'x'", output just that, not "The rewritten question is: Create a pod named 'x'".
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that rewrites quiz questions to be self-contained, based on context from a previous question.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        enriched_question = response.choices[0].message.content.strip()
        # Sometimes the model still adds quotes
        enriched_question = enriched_question.strip('"')
        return enriched_question
    except Exception as e:
        print(f"Error calling OpenAI: {e}", file=sys.stderr)
        return None


def process_markdown_file(filepath: str, client: openai.OpenAI):
    """Processes a markdown file to enrich questions."""
    print(f"Processing {filepath}...")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}", file=sys.stderr)
        return

    # The pattern splits by '### ' but keeps the delimiter.
    # We assume questions start with '### '.
    parts = re.split(r"(^### .*$)", content, flags=re.MULTILINE)

    header = parts[0]
    questions_and_details: List[dict] = []

    # After split, we get [header, question1, details1, question2, details2, ...]
    for i in range(1, len(parts), 2):
        question = parts[i].strip().lstrip("### ").strip()
        details = parts[i + 1]
        questions_and_details.append({"question": question, "details": details})

    modified = False
    # Start from the second question, as the first has no predecessor for context.
    for i in range(1, len(questions_and_details)):
        previous_q_text = questions_and_details[i - 1]["question"]
        current_q_text = questions_and_details[i]["question"]

        print(f"Enriching question: '{current_q_text}'")
        enriched_q_text = enrich_question(client, previous_q_text, current_q_text)

        if enriched_q_text and enriched_q_text != current_q_text:
            questions_and_details[i]["question"] = enriched_q_text
            print(f"  -> New question: '{enriched_q_text}'")
            modified = True
        elif not enriched_q_text:
            print("  -> Failed to enrich.")
        else:
            print("  -> No change needed.")

    if modified:
        # Reconstruct the markdown file
        new_content_parts = [header]
        for q_d in questions_and_details:
            new_content_parts.append(f"### {q_d['question']}")
            new_content_parts.append(q_d["details"])

        new_content = "".join(new_content_parts)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"File {filepath} has been updated.")
    else:
        print(f"No changes needing to be made to {filepath}.")


def main():
    """Main function."""
    # This script is in scripts/, so questions-data/ is one level up.
    script_dir = os.path.dirname(os.path.realpath(__file__))
    questions_data_dir = os.path.join(script_dir, "..", "questions-data")

    if not os.path.isdir(questions_data_dir):
        print(
            f"Error: questions-data directory not found at {questions_data_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    markdown_files = []
    for root, _, files in os.walk(questions_data_dir):
        for file in files:
            if file.endswith(".md"):
                markdown_files.append(os.path.join(root, file))

    if not markdown_files:
        print(f"No markdown files found in {questions_data_dir}", file=sys.stderr)
        return

    client = get_openai_client()

    # Sort files to process them in a consistent order.
    for file_path in sorted(markdown_files):
        process_markdown_file(file_path, client)

    print("\nDone.")


if __name__ == "__main__":
    main()
