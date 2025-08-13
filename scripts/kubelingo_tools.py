#!/usr/bin/env python3
"""
Kubelingo: An interactive menu for managing questions.
"""

import sys
from pathlib import Path
import subprocess

try:
    import questionary
except ImportError:
    print("Error: 'questionary' library not found. Please install it with: pip install questionary", file=sys.stderr)
    sys.exit(1)

# Determine directories
scripts_dir = Path(__file__).resolve().parent
repo_root = scripts_dir.parent

# Adjust sys.path to import local helper modules
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from kubelingo.database import get_db_connection
from kubelingo.utils.path_utils import get_live_db_path

# Import handlers from the consolidated question_manager script
# Note: This relies on the sys.path modification above to find the 'scripts' module
try:
    from scripts.question_manager import (
        handle_ai_questions, handle_from_pdf, handle_ai_quiz, 
        handle_resource_reference, handle_kubectl_operations,
        handle_manifests, handle_service_account,
        do_import_ai,
        handle_remove_question,
        handle_set_triage_status
    )
except ImportError as e:
    print(f"Failed to import from scripts.question_manager: {e}", file=sys.stderr)
    print("Please ensure you are running this script from the repository root.", file=sys.stderr)
    sys.exit(1)


class MockArgs:
    """Helper to create mock argparse.Namespace objects for function calls."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def _generate_questions():
    """Handles the 'Generate Questions' option with an interactive menu."""
    choice = questionary.select(
        "Select a question generator:",
        choices=[
            "From PDF", 
            "From AI (subject-based)",
            "From AI (quiz-style)",
            "Kubernetes Resource Reference",
            "Kubernetes Operations",
            "Service Account Questions",
            "Manifests from JSON",
            questionary.Separator(),
            "Back"
        ]
    ).ask()

    if not choice or choice == "Back":
        return

    if choice == "From PDF":
        pdf_path = questionary.text("Path to the PDF file:").ask()
        if not pdf_path: return
        output_file = questionary.text("Path to the output YAML file:", default="questions/generated_yaml/from_pdf.yaml").ask()
        if not output_file: return
        num_q = questionary.text("Number of questions per chunk?", default="5").ask()
        handle_from_pdf(MockArgs(pdf_path=pdf_path, output_file=output_file, num_questions_per_chunk=int(num_q)))
    
    elif choice == "From AI (subject-based)":
        subject = questionary.text("Subject for the new questions (e.g., 'Kubernetes Service Accounts'):").ask()
        if not subject: return
        category = questionary.select("Category of questions:", choices=['Basic', 'Command', 'Manifest'], default='Command').ask()
        num_q = questionary.text("Number of questions to generate?", default="3").ask()
        output_file = questionary.text("Path to the output YAML file:", default=f"questions/generated_yaml/{subject.lower().replace(' ', '_')}.yaml").ask()
        if not output_file: return
        example_file = questionary.text("(Optional) Source file in DB for example questions:").ask()
        handle_ai_questions(MockArgs(
            subject=subject, category=category, num_questions=int(num_q), 
            output_file=output_file, example_source_file=example_file
        ))

    elif choice == "From AI (quiz-style)":
        num = questionary.text("Number of questions to generate?", default="5").ask()
        output = questionary.text("Output JSON file path:", default="questions/generated_json/ai_quiz.json").ask()
        handle_ai_quiz(MockArgs(num=int(num), output=output, mock=False))

    elif choice == "Kubernetes Resource Reference":
        handle_resource_reference(MockArgs())

    elif choice == "Kubernetes Operations":
        handle_kubectl_operations(MockArgs())

    elif choice == "Service Account Questions":
        handle_service_account(MockArgs(to_db=False, num=0, output="questions/generated_json/service_accounts.json"))

    elif choice == "Manifests from JSON":
        handle_manifests(MockArgs(json_dir="question-data/json"))

def _add_questions():
    """Handles 'Add Questions' - import from YAML with AI schema inference, rewriting, and reformatting."""
    print("This tool imports questions from YAML files, using AI for schema inference, rewriting, and reformatting.")
    db_path = get_live_db_path()
    output_db = questionary.text(
        "Enter the path for the new/updated SQLite database:",
        default=str(db_path)
    ).ask()
    if not output_db: return

    search_dir = questionary.text(
        "Enter the directory to search for YAML files:",
        default="questions/generated_yaml"
    ).ask()
    if not search_dir: return

    _run_script("question_manager.py", "import-ai", output_db, "--search-dir", search_dir)

def _remove_questions():
    """Handles 'Remove Questions'."""
    question_id = questionary.text("Enter the ID of the question to remove:").ask()
    if not question_id:
        return
    
    # The handler function includes a confirmation prompt.
    handle_remove_question(MockArgs(question_id=question_id))

def _manage_triaged_questions():
    """Interactive menu for managing triaged questions."""
    conn = get_db_connection()
    if not conn:
        print("Could not connect to database.", file=sys.stderr)
        return
    
    while True:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, prompt FROM questions WHERE triage = 1")
            rows = cursor.fetchall()
        except Exception as e:
            print(f"Error fetching triaged questions: {e}", file=sys.stderr)
            if "no such column: triage" in str(e):
                print("Hint: The 'triage' column might be missing. You may need to update your database schema.", file=sys.stderr)
            conn.close()
            return

        if not rows:
            questionary.print("No triaged questions found.", style="bold green")
            break
        
        choices = [
            questionary.Choice(title=f"ID: {row[0]} | Prompt: {row[1][:70]}...", value=row[0]) for row in rows
        ]
        choices.append(questionary.Separator())
        choices.append(questionary.Choice(title="Back to main menu", value="back"))

        question_id = questionary.select(
            f"Found {len(rows)} triaged questions. Select one to manage:",
            choices=choices
        ).ask()

        if not question_id or question_id == "back":
            break

        action = questionary.select(
            f"Action for question '{question_id}':",
            choices=["Un-triage", "Delete", "AI Edit (Not Implemented)", "Cancel"]
        ).ask()

        if action == "Un-triage":
            handle_set_triage_status(MockArgs(question_id=question_id, un_triage=True))
        elif action == "Delete":
            handle_remove_question(MockArgs(question_id=question_id))
        elif action == "AI Edit (Not Implemented)":
            questionary.print("AI editing is not yet implemented.", style="bold yellow")
        elif not action or action == "Cancel":
            continue
    conn.close()


def main():
    """Display the question management menu."""
    tasks = {
        "Generate Questions": _generate_questions,
        "Add Questions": _add_questions,
        "Remove Questions": _remove_questions,
        "Triaged Questions": _manage_triaged_questions,
    }
    
    while True:
        choice = questionary.select(
            "--- Manage Questions ---",
            choices=list(tasks.keys()) + [questionary.Separator(), "Exit"],
            use_indicator=True
        ).ask()

        if not choice or choice == "Exit":
            print("Exiting question management.")
            break
        
        tasks[choice]()
        
        print() # Add a newline for better spacing
        if not questionary.confirm("Return to the Question Management Menu?", default=True).ask():
            print("Exiting question management.")
            break
        print() # Add a newline for better spacing


if __name__ == '__main__':
    main()
