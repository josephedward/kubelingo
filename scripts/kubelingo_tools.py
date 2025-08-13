#!/usr/bin/env python3
"""
Kubelingo: An interactive menu for managing questions.
"""

import sys
from pathlib import Path

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

def _run_script(script_name: str, *args):
    """Helper to run a script from the scripts directory."""
    script_path = scripts_dir / script_name
    if not script_path.exists():
        print(f"Error: Script '{script_path}' not found.", file=sys.stderr)
        return False
    command = [sys.executable, str(script_path)] + [str(a) for a in args]
    print(f"Running: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running script {script_name}: {e}", file=sys.stderr)
        return False
    except KeyboardInterrupt:
        print(f"\nScript {script_name} interrupted.", file=sys.stderr)
        return False

def _generate_questions():
    """Handles the 'Generate Questions' option."""
    print("This will launch the question generator script interactively.")
    # The generator script has its own interactive prompts if run without args
    _run_script("generator.py") 

def _add_questions():
    """Handles 'Add Questions' - import from YAML with AI categorization."""
    print("This tool imports questions from YAML files, using AI for schema inference and reformatting.")
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
    
    # The 'remove' command in question_manager handles confirmation
    _run_script("question_manager.py", "remove", question_id)

def _manage_triaged_questions():
    """Interactive menu for managing triaged questions."""
    conn = get_db_connection()
    if not conn:
        print("Could not connect to database.", file=sys.stderr)
        return
    
    while True:
        try:
            cursor = conn.cursor()
            # Assuming 'triage' is a boolean column that exists.
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
            _run_script("question_manager.py", "untriage", question_id)
        elif action == "Delete":
            _run_script("question_manager.py", "remove", question_id)
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
