#!/usr/bin/env python
import argparse
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


# Heuristics to identify questions that likely need context from a previous question.
# These are case-insensitive.
VAGUE_QUESTION_STARTS = [
    "create the pod that was just described",
    "do the same",
    "change pod's image",
    "get nginx pod's ip",
    "get pod's yaml",
    "get information about the pod",
    "get pod logs",
    "if pod crashed and restarted",
]


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


def process_markdown_file(
    filepath: str, client: openai.OpenAI, all_questions: bool = False
):
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
    for i in range(len(questions_and_details)):
        current_q_text = questions_and_details[i]["question"]

        # Decide if question needs enrichment
        needs_enrichment = all_questions
        if not needs_enrichment:
            for start in VAGUE_QUESTION_STARTS:
                if current_q_text.lower().startswith(start):
                    needs_enrichment = True
                    break

        if needs_enrichment and i > 0:
            previous_q_text = questions_and_details[i - 1]["question"]
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
    parser = argparse.ArgumentParser(
        description="Enrich markdown quiz questions using AI to make them self-contained."
    )
    parser.add_argument(
        "files", nargs="+", help="Path(s) to the markdown file(s) to process."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Attempt to enrich all questions, not just ones matching heuristics.",
    )

    args = parser.parse_args()

    client = get_openai_client()

    for file in args.files:
        process_markdown_file(file, client, args.all)

    print("\nDone.")


if __name__ == "__main__":
    main()
