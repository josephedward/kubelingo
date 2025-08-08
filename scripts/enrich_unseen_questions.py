import argparse
import json
import os
import sys
from pathlib import Path
import yaml

# Add project root to sys.path to allow importing kubelingo modules
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.database import get_db_connection
from kubelingo.modules.question_generator import AIQuestionGenerator


def get_existing_prompts(conn):
    """Fetch all unique question prompts from the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT prompt FROM questions")
    return {row[0] for row in cursor.fetchall()}


def main():
    parser = argparse.ArgumentParser(
        description="Generate new questions from a source file if they don't exist in the database."
    )
    parser.add_argument(
        "--source-file",
        type=str,
        default="/Users/user/Documents/GitHub/kubelingo/question-data/unified.json",
        help="Path to the JSON file with source questions.",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="question-data/yaml/ai_generated_new_questions.yaml",
        help="Path to save the newly generated questions in YAML format.",
    )
    parser.add_argument(
        "--num-questions",
        type=int,
        default=5,
        help="Maximum number of new questions to generate.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview unseen questions without generating new ones.",
    )
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY environment variable not set. AI generation is disabled.")
        if not args.dry_run:
            sys.exit(1)

    try:
        conn = get_db_connection()
        existing_prompts = get_existing_prompts(conn)
        conn.close()
        print(f"INFO: Found {len(existing_prompts)} existing questions in the database.")
    except Exception as e:
        print(f"WARNING: Could not connect to database or fetch questions: {e}")
        existing_prompts = set()

    try:
        with open(args.source_file, 'r') as f:
            source_questions = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: Error reading source file {args.source_file}: {e}")
        sys.exit(1)

    unseen_questions = []
    for question in source_questions:
        prompt = question.get('prompt') or question.get('question')
        if prompt and prompt not in existing_prompts:
            unseen_questions.append(question)

    print(f"INFO: Found {len(unseen_questions)} unseen questions in {args.source_file}.")

    if args.dry_run:
        print("INFO: Dry run enabled. Listing unseen question prompts:")
        for i, q in enumerate(unseen_questions[:args.num_questions]):
            print(f"  {i+1}. {q.get('prompt') or q.get('question')}")
        return

    if not unseen_questions:
        print("INFO: No new questions to generate.")
        return

    if not os.environ.get("OPENAI_API_KEY"):
        print("WARNING: Cannot generate questions because OPENAI_API_KEY is not set.")
        return

    generator = AIQuestionGenerator()
    generated_questions = []

    questions_to_generate = unseen_questions[:args.num_questions]
    print(f"INFO: Attempting to generate up to {len(questions_to_generate)} new questions...")

    for i, base_question in enumerate(questions_to_generate):
        prompt = base_question.get('prompt') or base_question.get('question')
        print(f"INFO: [{i+1}/{len(questions_to_generate)}] Generating question for prompt: \"{prompt}\"")
        try:
            new_question = generator.generate_question(base_question)
            if new_question:
                generated_questions.append(new_question)
                print("  -> SUCCESS: Successfully generated question.")
            else:
                print("  -> WARNING: Failed to generate question (AI returned empty response).")
        except Exception as e:
            print(f"  -> ERROR: An error occurred during generation: {e}")

    if generated_questions:
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            yaml.dump(generated_questions, f, default_flow_style=False, sort_keys=False)
        print(f"SUCCESS: Successfully generated {len(generated_questions)} new questions and saved them to {args.output_file}")
    else:
        print("WARNING: No questions were generated.")


if __name__ == "__main__":
    main()
