#!/usr/bin/env python3
#
# A script to reorganize question schema categories using an AI model.
#
# This script:
# 1. Reads all questions from the local SQLite database.
# 2. Uses an AI model (e.g., GPT-3.5 Turbo) to classify each question's prompt
#    into one of the three schema categories: OPEN_ENDED, COMMAND, or MANIFEST.
# 3. Updates the `schema_category` column in the database with the new classification.
#
# Usage:
#   - Ensure dependencies are installed: pip install openai
#   - Set your API key: export OPENAI_API_KEY="<your_key>"
#   - Run the script: python3 scripts/reorganize_schema_by_ai.py
#   - For a preview: python3 scripts/reorganize_schema_by_ai.py --dry-run
#
import argparse
import os
import sys
from pathlib import Path

# Add project root to the Python path to allow importing from 'kubelingo'
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    import openai
    from kubelingo.database import get_db_connection, get_all_questions
    from kubelingo.question import QuestionCategory
    from kubelingo.utils.ui import Fore, Style
except ImportError as e:
    print(f"Error: Failed to import necessary modules. Please ensure dependencies are installed.")
    print(f"Details: {e}")
    sys.exit(1)


class AICategorizer:
    """Uses an AI model to classify questions into schema categories."""

    def __init__(self, model: str):
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        self.client = openai.OpenAI()
        self.model = model
        self.valid_categories = {cat.name: cat.value for cat in QuestionCategory}

    def get_system_prompt(self) -> str:
        """Returns the system prompt that instructs the AI on how to classify."""
        return """You are an expert assistant for a Kubernetes learning tool. Your task is to classify question prompts into one of three categories.

The categories are:
- **OPEN_ENDED**: Conceptual questions about Kubernetes resources, architecture, or theory. The answer is typically a textual explanation. Examples: "What is a Pod?", "Explain the difference between a Deployment and a StatefulSet."
- **COMMAND**: Questions that require the user to provide a single-line command using a tool like `kubectl`, `helm`, or `vim`. Examples: "Create a pod named 'nginx' with the image 'nginx:latest'.", "Get the logs for the pod 'my-app-123'."
- **MANIFEST**: Questions that require the user to author or edit a multi-line YAML manifest file. These exercises typically involve using an editor like Vim. Examples: "Create a YAML manifest for a Deployment with 3 replicas.", "Edit the existing Service manifest to expose port 8080."

You must respond with ONLY ONE of the following category names: OPEN_ENDED, COMMAND, or MANIFEST."""

    def categorize_question(self, prompt: str) -> QuestionCategory:
        """
        Classifies a single question prompt using the AI model.

        Args:
            prompt: The text of the question prompt.

        Returns:
            The determined QuestionCategory, or None if classification fails.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": f"Categorize this prompt: \"{prompt}\""}
                ],
                temperature=0.0,
                max_tokens=10,
            )
            category_name = response.choices[0].message.content.strip()

            if category_name in self.valid_categories:
                return QuestionCategory(self.valid_categories[category_name])
            else:
                print(f"{Fore.YELLOW}Warning: AI returned an invalid category '{category_name}'.{Style.RESET_ALL}")
                return None
        except Exception as e:
            print(f"{Fore.RED}Error calling OpenAI API: {e}{Style.RESET_ALL}")
            return None


def update_question_category_in_db(conn, question_id: str, category: str):
    """Updates the schema_category for a specific question in the database."""
    cursor = conn.cursor()
    cursor.execute("UPDATE questions SET schema_category = ? WHERE id = ?", (category, question_id))


def main():
    """Main function to run the reorganization script."""
    parser = argparse.ArgumentParser(description="Reorganize question schema categories using AI.")
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-3.5-turbo",
        help="The OpenAI model to use for classification."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to the database."
    )
    args = parser.parse_args()

    print(f"{Fore.CYAN}--- AI-Powered Question Schema Reorganization ---{Style.RESET_ALL}")
    if args.dry_run:
        print(f"{Fore.YELLOW}Running in dry-run mode. No changes will be saved.{Style.RESET_ALL}")

    try:
        categorizer = AICategorizer(model=args.model)
    except ValueError as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        sys.exit(1)

    conn = get_db_connection()
    questions = get_all_questions()
    
    changed_count = 0
    unchanged_count = 0
    failed_count = 0

    try:
        for i, q in enumerate(questions):
            question_id = q.get('id')
            prompt = q.get('prompt')
            current_category = q.get('schema_category')

            if not prompt:
                continue

            print(f"\n({i + 1}/{len(questions)}) Processing QID: {question_id}")
            print(f"  Prompt: {prompt[:100]}...")

            new_category = categorizer.categorize_question(prompt)

            if new_category is None:
                print(f"  {Fore.RED}Failed to classify.{Style.RESET_ALL}")
                failed_count += 1
                continue

            if current_category != new_category.value:
                print(f"  {Fore.YELLOW}Change: '{current_category}' -> '{new_category.value}'{Style.RESET_ALL}")
                changed_count += 1
                if not args.dry_run:
                    update_question_category_in_db(conn, question_id, new_category.value)
            else:
                print(f"  {Fore.GREEN}No change: '{current_category}'{Style.RESET_ALL}")
                unchanged_count += 1
        
        if not args.dry_run:
            conn.commit()

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Operation cancelled by user.{Style.RESET_ALL}")
    finally:
        conn.close()

    print("\n--- Summary ---")
    print(f"Questions processed: {len(questions)}")
    print(f"  {Fore.YELLOW}Changed: {changed_count}{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}Unchanged: {unchanged_count}{Style.RESET_ALL}")
    print(f"  {Fore.RED}Failed: {failed_count}{Style.RESET_ALL}")

    if args.dry_run:
        print("\nThis was a dry run. To apply these changes, run the script without the --dry-run flag.")
    else:
        print("\nDatabase has been updated.")


if __name__ == "__main__":
    main()
