#!/usr/bin/env python
import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

import yaml
from pathlib import Path
from dotenv import load_dotenv

try:
    import openai
except ImportError:
    print(
        "Error: openai library not found. Please install it with 'pip install openai'",
        file=sys.stderr,
    )
    sys.exit(1)

# Load shared AI prompt context from root shared_context.md
repo_root = Path(__file__).resolve().parent.parent
shared_context_path = repo_root / 'shared_context.md'
if shared_context_path.exists():
    SHARED_CONTEXT = shared_context_path.read_text(encoding='utf-8')
else:
    SHARED_CONTEXT = ''


def get_openai_client() -> openai.OpenAI:
    """Returns an OpenAI client, getting API key from .env, env var, or prompt."""
    dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not found.", file=sys.stderr)
        try:
            api_key = input("Please enter your OpenAI API key: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.", file=sys.stderr)
            sys.exit(1)
    if not api_key:
        print("Error: No OpenAI API key provided.", file=sys.stderr)
        sys.exit(1)
    return openai.OpenAI(api_key=api_key)


def load_from_json(filepath: str) -> List[Dict[str, Any]]:
    """Loads questions from a JSON file, handling nested structures."""
    questions = []
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    for item in data:
        if isinstance(item, dict):
            if "prompts" in item and isinstance(item["prompts"], list):
                category = item.get("category")
                for prompt_data in item["prompts"]:
                    if isinstance(prompt_data, dict):
                        q = prompt_data.copy()
                        if category:
                            q["category"] = category
                        questions.append(q)
            elif "prompt" in item:
                questions.append(item)
    return questions


def load_from_md(filepath: str) -> List[Dict[str, Any]]:
    """Loads questions from a Markdown file with YAML frontmatter."""
    questions = []
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    # Regex to find YAML blocks followed by a ### prompt
    pattern = re.compile(r"^---\s*\n(.*?)\n^---\s*\n^###\s*(.*?)$", re.S | re.M)
    for match in pattern.finditer(content):
        yaml_str, prompt_str = match.groups()
        try:
            q_data = yaml.safe_load(yaml_str)
            if isinstance(q_data, dict):
                q_data["prompt"] = prompt_str.strip()
                questions.append(q_data)
        except yaml.YAMLError:
            continue
    return questions


def load_all_questions(base_dir: str) -> List[Dict[str, Any]]:
    """Loads all questions from json, md, and yaml files in a directory."""
    all_questions = []
    for root, _, files in os.walk(base_dir):
        for file in files:
            filepath = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            loaded = []
            if ext == ".json":
                loaded = load_from_json(filepath)
            elif ext == ".md":
                loaded = load_from_md(filepath)
            # Add yaml loader if needed in future
            for q in loaded:
                q["source_file"] = filepath
                all_questions.append(q)
    return all_questions


def generate_explanation(
    client: openai.OpenAI, question: Dict[str, Any]
) -> Optional[str]:
    """Uses OpenAI to generate a concise explanation for a question."""
    prompt_text = question.get("prompt")
    # Determine the answer, preferring response, then validation command
    answer_text = question.get("response")
    if not answer_text and "validation_steps" in question and question["validation_steps"]:
        answer_text = question["validation_steps"][0].get("cmd", "")

    if not prompt_text or not answer_text:
        return None

    api_prompt = f"""As a Kubernetes expert creating educational material, I have a quiz question and its answer.
Please write a concise, one-sentence explanation for a student. The explanation should clarify what the command does or why it's the correct approach, focusing on educational value.

Question: "{prompt_text}"

Answer: "{answer_text}"

Provide only the explanation text, without any introductory phrases like "This command...".
"""
    # Build system message with shared context
    system_message = SHARED_CONTEXT + "\n\nYou are a helpful assistant that writes concise, educational explanations for Kubernetes quiz questions."
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": api_prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip().strip('"')
    except Exception as e:
        print(f"Error calling OpenAI for prompt '{prompt_text[:30]}...': {e}", file=sys.stderr)
        return None


def main():
    """Main script logic."""
    parser = argparse.ArgumentParser(
        description="Enrich and deduplicate Kubelingo question files using AI."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the process without calling OpenAI or writing files.",
    )
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.realpath(__file__))
    question_data_dir = os.path.join(script_dir, "..", "question-data")
    output_file = os.path.join(question_data_dir, "json", "master_quiz_with_explanations.json")

    print("Loading all questions from question-data/...")
    all_questions = load_all_questions(question_data_dir)
    print(f"Found {len(all_questions)} questions across all files.")

    # Deduplicate questions, prioritizing those that already have an explanation
    unique_questions: Dict[str, Dict[str, Any]] = {}
    for q in all_questions:
        prompt = q.get("prompt", "").strip()
        if not prompt:
            continue
        if prompt not in unique_questions or (not unique_questions[prompt].get("explanation") and q.get("explanation")):
            unique_questions[prompt] = q
    
    print(f"Found {len(unique_questions)} unique questions after deduplication.")

    client = None
    if not args.dry_run:
        client = get_openai_client()

    enriched_count = 0
    final_questions = []
    for prompt, q in unique_questions.items():
        # We only need to generate an explanation if one doesn't exist and there is no simple 'response' field
        # which is often self-explanatory for command-line tools like Vim.
        if not q.get("explanation"):
            # Don't generate explanations for simple response questions like vim commands
            is_simple_response = q.get("type") == "command" and len(q.get("response", "").split()) < 3
            if not is_simple_response:
                if args.dry_run:
                    print(f"[DRY-RUN] Would generate explanation for: {prompt[:70]}...")
                    enriched_count += 1
                else:
                    print(f"Generating explanation for: {prompt[:70]}...")
                    explanation = generate_explanation(client, q)
                    if explanation:
                        q["explanation"] = explanation
                        enriched_count += 1
        final_questions.append(q)
    
    # Sort for consistent output
    final_questions.sort(key=lambda x: x.get('prompt', ''))
    
    print(f"\nEnriched {enriched_count} questions with new explanations.")

    if args.dry_run:
        print(f"[DRY-RUN] Would save {len(final_questions)} questions to {output_file}")
    else:
        print(f"Saving {len(final_questions)} unique, enriched questions to {output_file}...")
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_questions, f, indent=2)
        print("Done.")


if __name__ == "__main__":
    main()
