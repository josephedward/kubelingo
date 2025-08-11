#!/usr/bin/env python3
"""
Reorganize questions in the database by AI-driven schema_category classification.

This script scans all questions in the SQLite database, uses the OpenAI API to classify each
question prompt into one of the three schema categories (Basic/Open-Ended, Command-Based/Syntax,
Manifests), and updates the `schema_category` column accordingly.

Usage:
  pip install openai
  export OPENAI_API_KEY=your_key_here   # or configure via `kubelingo config set openai`
  python3 scripts/reorganize_schema_by_ai.py [--dry-run] [--model MODEL]
"""
import argparse
import os
import sys
import sqlite3

try:
    import openai
except ImportError:
    print("Error: openai package not installed. Run `pip install openai`.")
    sys.exit(1)

from kubelingo.database import get_db_connection
from kubelingo.utils.config import get_api_key, DATABASE_FILE

ALLOWED_CATEGORIES = [
    "Basic/Open-Ended",
    "Command-Based/Syntax",
    "Manifests",
]

def classify(prompt: str, model: str) -> str:
    """Use OpenAI to classify a prompt into one of the allowed categories."""
    system_msg = (
        "You are a classification assistant for Kubernetes quiz questions.\n"
        "Classify each question into exactly one of: Basic/Open-Ended, Command-Based/Syntax, Manifests.\n"
        "Reply with only the category name, no additional text."
    )
    user_msg = f"Question: {prompt.strip()}"
    resp = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0,
        max_tokens=16,
    )
    category = resp.choices[0].message.content.strip()
    return category

def main():
    parser = argparse.ArgumentParser(description="AI-driven schema_category updater for kubelingo DB.")
    parser.add_argument("--dry-run", action="store_true", help="Show classifications without updating DB.")
    parser.add_argument("--model", type=str, default="gpt-3.5-turbo", help="OpenAI model to use.")
    args = parser.parse_args()

    # Initialize API key
    api_key = os.getenv('OPENAI_API_KEY') or get_api_key()
    if not api_key:
        print("Error: No OpenAI API key configured. Use OPENAI_API_KEY or `kubelingo config set openai`.")
        sys.exit(1)
    openai.api_key = api_key

    # Connect to DB
    db_path = DATABASE_FILE
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch all questions
    cursor.execute("SELECT id, prompt, schema_category FROM questions")
    rows = cursor.fetchall()
    print(f"Found {len(rows)} questions in {db_path}")

    updated = {cat: 0 for cat in ALLOWED_CATEGORIES}
    for row in rows:
        qid = row['id']
        prompt = row['prompt']
        current = row['schema_category']
        try:
            new_cat = classify(prompt, args.model)
        except Exception as e:
            print(f"[Error] Classification failed for {qid}: {e}")
            continue
        if new_cat not in ALLOWED_CATEGORIES:
            print(f"[Warning] Invalid category '{new_cat}' for question {qid}, skipping.")
            continue
        if current == new_cat:
            continue
        print(f"{qid}: {current} -> {new_cat}")
        if not args.dry_run:
            cursor.execute(
                "UPDATE questions SET schema_category = ? WHERE id = ?",
                (new_cat, qid)
            )
            updated[new_cat] += 1

    if not args.dry_run:
        conn.commit()
        print("\nUpdates applied:")
        for cat, cnt in updated.items():
            print(f"  {cat}: {cnt}")
    else:
        print("(dry-run) no changes applied.")

    conn.close()

if __name__ == '__main__':
    main()#!/usr/bin/env python3
import os
import sys
import sqlite3
import argparse
import openai
from typing import List, Dict, Any, Optional

# --- Project Setup ---
# Add project root to sys.path to allow imports from kubelingo
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from kubelingo.database import get_db_connection
from kubelingo.question import QuestionCategory

# --- Constants ---
# Color codes for terminal output
class Fore:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    RESET = '\033[0m'

# OpenAI client initialization
# The key is expected to be in the OPENAI_API_KEY environment variable.
try:
    client = openai.OpenAI()
except openai.OpenAIError:
    print(f"{Fore.RED}Error: OpenAI API key not found.{Fore.RESET}")
    print(f"Please set the OPENAI_API_KEY environment variable.")
    sys.exit(1)


def get_system_prompt() -> str:
    """Returns the system prompt for the AI categorizer."""
    return """
You are a categorization bot for a Kubernetes learning tool called Kubelingo.
Your task is to classify a given question prompt into one of the three immutable schema categories.

The categories are:
- 'open-ended': Conceptual questions that can be answered with a term or explanation. Example: "What is a Pod in Kubernetes?"
- 'command': Questions that are solved with a single-line shell command. Example: "Create a new pod named 'nginx' with the image 'nginx:latest'."
- 'manifest': Questions that require writing or editing a multi-line YAML manifest. Example: "Create a YAML manifest for a Deployment with 3 replicas."

You must respond with ONLY the category name ('open-ended', 'command', or 'manifest') and absolutely nothing else. Your response will be parsed programmatically.
""".strip()

def get_all_questions_from_db(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Fetches all questions from the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, prompt, schema_category FROM questions")
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

def classify_question(prompt: str, model: str) -> Optional[QuestionCategory]:
    """Uses the OpenAI API to classify a question prompt."""
    if not prompt:
        return None
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": get_system_prompt()},
                {"role": "user", "content": f"Question Prompt:\n---\n{prompt}\n---"}
            ],
            temperature=0.0,
            max_tokens=10,
        )
        category_str = response.choices[0].message.content.strip().lower()

        # Validate the response from the model
        valid_categories = [cat.value for cat in QuestionCategory]
        if category_str in valid_categories:
            return QuestionCategory(category_str)
        else:
            print(f"{Fore.YELLOW}Warning: AI returned an invalid category ('{category_str}'). Skipping.{Fore.RESET}")
            return None
    except Exception as e:
        print(f"{Fore.RED}Error during API call for prompt '{prompt[:50]}...': {e}{Fore.RESET}")
        return None

def update_question_category_in_db(conn: sqlite3.Connection, qid: str, category: QuestionCategory):
    """Updates the schema_category for a given question in the database."""
    cursor = conn.cursor()
    cursor.execute("UPDATE questions SET schema_category = ? WHERE id = ?", (category.value, qid))

def main():
    """Main function to run the re-categorization script."""
    parser = argparse.ArgumentParser(
        description="Re-categorize all questions in the database using an AI model.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-3.5-turbo",
        help="The OpenAI model to use for classification (e.g., gpt-3.5-turbo, gpt-4)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="If set, preview the changes without writing them to the database."
    )
    args = parser.parse_args()

    print(f"{Fore.CYAN}--- AI-Powered Schema Reorganizer ---{Fore.RESET}")
    print(f"Model: {args.model}")
    if args.dry_run:
        print(f"{Fore.YELLOW}Running in DRY-RUN mode. No changes will be saved.{Fore.RESET}")

    conn = get_db_connection()
    questions = get_all_questions_from_db(conn)
    total = len(questions)
    print(f"Found {total} questions to process.\n")

    updated_count = 0
    for i, q in enumerate(questions, start=1):
        qid = q['id']
        prompt = q['prompt']
        current_category = q.get('schema_category')

        print(f"[{i}/{total}] Processing QID: {qid}...")
        
        new_category = classify_question(prompt, args.model)
        
        if not new_category:
            print(f"  {Fore.YELLOW}Skipping question (could not classify).{Fore.RESET}\n")
            continue

        if current_category == new_category.value:
            print(f"  {Fore.GREEN}Category is already correct: '{current_category}'. No change needed.{Fore.RESET}\n")
        else:
            print(f"  Current: '{current_category}' -> New: '{new_category.value}'")
            if not args.dry_run:
                update_question_category_in_db(conn, qid, new_category)
                print(f"  {Fore.GREEN}Database updated.{Fore.RESET}")
            updated_count += 1
        
        if i % 10 == 0 and not args.dry_run:
            # Commit changes in batches
            conn.commit()

    if not args.dry_run:
        conn.commit()
    conn.close()

    print(f"\n{Fore.CYAN}--- Reorganization Complete ---{Fore.RESET}")
    if args.dry_run:
        print(f"{updated_count} questions would be updated.")
    else:
        print(f"{updated_count} questions were updated in the database.")


if __name__ == "__main__":
    main()
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
