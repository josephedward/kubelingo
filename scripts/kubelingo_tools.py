#!/usr/bin/env python3
"""
Kubelingo: An interactive menu for managing questions.
"""

import sys
from pathlib import Path
import subprocess
import argparse

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
from kubelingo.question import QuestionSubject
from kubelingo.utils.config import DATABASE_FILE

# Import handlers from the consolidated question_manager script
# Note: This relies on the sys.path modification above to find the 'scripts' module
try:
    from scripts.question_manager import (
        handle_ai_questions, handle_from_pdf,
        handle_resource_reference, handle_kubectl_operations,
        handle_manifests, handle_service_account,
        handle_remove_question,
        handle_set_triage_status,
        handle_build_index,
        handle_list_triaged,
        handle_ai_quiz,
        handle_validation_steps,
        do_consolidate,
        do_create_quizzes,
        do_deduplicate,
        do_diff,
        do_export,
        do_import_ai,
        do_index,
        do_init,
        do_list_backups,
        do_backup_stats,
        do_statistics,
        do_group_backups,
        do_import_bak,
        do_migrate_all,
        do_migrate_bak,
        do_verify,
        do_organize_generated,
        do_index_sqlite,
        do_schema,
        do_list_sqlite,
        do_unarchive,
        do_restore,
        do_create_from_yaml,
        do_diff_db,
        _manage_database
    )
except ImportError as e:
    print(f"Failed to import from scripts.question_manager: {e}", file=sys.stderr)
    print("Please ensure you are running this script from the repository root.", file=sys.stderr)
    sys.exit(1)


class MockArgs:
    """Helper to create mock argparse.Namespace objects for function calls."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def _run_script(script_name: str, *args):
    """Helper to run a script from the scripts directory."""
    script_path = scripts_dir / script_name
    if not script_path.exists():
        print(f"Error: Script '{script_name}' not found at '{script_path}'", file=sys.stderr)
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
        print("\nScript execution cancelled.", file=sys.stderr)
        return False

def _generate_questions():
    """Handles the 'Generate Questions' option with an interactive menu."""
    choice = questionary.select(
        "Select a question generator:",
        choices=[
            "From PDF", 
            "From AI (subject-based)",
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
        output_file = questionary.text("Path to the output YAML file:", default="yaml/generated/from_pdf.yaml").ask()
        if not output_file: return
        num_q = questionary.text("Number of questions per chunk?", default="5").ask()
        handle_from_pdf(MockArgs(pdf_path=pdf_path, output_file=output_file, num_questions_per_chunk=int(num_q)))
    
    elif choice == "From AI (subject-based)":
        subjects = sorted([s.value for s in QuestionSubject])
        subject = questionary.select(
            "Subject for the new questions:",
            choices=subjects
        ).ask()
        if not subject: return

        # Sanitize subject to prevent issues with special characters like '&'
        subject = subject.replace(' & ', ' and ').replace('&', 'and')

        category = questionary.select("Category of questions:", choices=['Basic', 'Command', 'Manifest'], default='Command').ask()
        num_q = questionary.text("Number of questions to generate?", default="3").ask()
        sanitized_subject = subject.lower().replace(' ', '_')
        output_file = questionary.text("Path to the output YAML file:", default=f"yaml/generated/{sanitized_subject}.yaml").ask()
        if not output_file: return
        example_file = questionary.text("(Optional) Path to YAML source file for example questions:").ask()
        
        handle_ai_questions(MockArgs(
            subject=subject, category=category, num_questions=int(num_q), 
            output_file=output_file, example_source_file=example_file
        ))

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
        default="yaml/generated"
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


def _not_implemented():
    """Prints a 'not implemented' message."""
    questionary.print("This feature is not yet implemented.", style="bold yellow")


def _startup_ai_configuration():
    """Placeholder for initial AI provider setup on app start."""
    # Per instructions, this should ask for provider and check/set API keys.
    # This is a complex flow that requires configuration management.
    # For now, this is a placeholder.
    print("\nStartup AI configuration check...")


def _learn_socratic():
    _not_implemented()


def _learn_missed():
    _not_implemented()


def _drill_open_ended():
    _not_implemented()


def _drill_basic_terminology():
    _not_implemented()


def _drill_command_syntax():
    _not_implemented()


def _drill_yaml_manifest():
    _not_implemented()


def _settings_ai():
    # As per user spec, this would show a detailed menu for managing AI providers and keys.
    _not_implemented()


def _settings_clusters():
    _not_implemented()


def _settings_help():
    _not_implemented()


def _settings_report_bug():
    """Runs the bug ticket reporting script."""
    _run_script("bug_ticket.py")


def _show_question_management_menu():
    """Displays the question and data management menu, formerly the main interactive mode."""
    tasks = {
        "generate": _generate_questions,
        "add": _add_questions,
        "remove": _remove_questions,
        "triage": _manage_triaged_questions,
        "database": _manage_database,
    }
    menu_choices = [
        questionary.Choice(
            title="Generate Questions",
            value="generate"
        ),
        questionary.Choice(
            title="Add Questions",
            value="add"
        ),
        questionary.Choice(
            title="Remove Questions",
            value="remove"
        ),
        questionary.Choice(
            title="Triaged Questions",
            value="triage"
        ),
        questionary.Choice(
            title="Database Management",
            value="database"
        ),
        questionary.Separator(),
        "Back",
    ]

    while True:
        choice = questionary.select(
            "--- Question & Data Management ---",
            choices=menu_choices,
            use_indicator=True
        ).ask()

        if not choice or choice == "Back":
            break

        task_function = tasks.get(choice)
        if task_function:
            task_function()

        print() # Add a newline for better spacing
        if not questionary.confirm("Return to the Management Menu?", default=True).ask():
            break
        print() # Add a newline for better spacing


def main():
    """Display the main application menu."""
    # Placeholder for startup AI configuration
    _startup_ai_configuration()

    # Dummy data for counts, as per the new design
    missed_count = 2
    open_ended_count = 60
    basic_terminology_count = 700
    command_syntax_count = 244
    yaml_manifest_count = 80

    tasks = {
        "socratic": _learn_socratic,
        "missed": _learn_missed,
        "drill_open_ended": _drill_open_ended,
        "drill_basic": _drill_basic_terminology,
        "drill_command": _drill_command_syntax,
        "drill_yaml": _drill_yaml_manifest,
        "settings_ai": _settings_ai,
        "settings_clusters": _settings_clusters,
        "settings_questions": _show_question_management_menu,
        "settings_help": _settings_help,
        "report_bug": _settings_report_bug,
    }

    while True:
        menu_choices = [
            questionary.Separator("--- Learn ---"),
            questionary.Choice("Socratic Mode (Socratic Tutor)", value="socratic"),
            questionary.Choice(f"Missed Questions ({missed_count})", value="missed"),
            questionary.Separator("--- Drill ---"),
            questionary.Choice(f"Open Ended Questions ({open_ended_count})", value="drill_open_ended"),
            questionary.Choice(f"Basic Terminology ({basic_terminology_count})", value="drill_basic"),
            questionary.Choice(f"Command Syntax ({command_syntax_count})", value="drill_command"),
            questionary.Choice(f"YAML Manifest ({yaml_manifest_count})", value="drill_yaml"),
            questionary.Separator("--- Settings ---"),
            questionary.Choice("AI", value="settings_ai"),
            questionary.Choice("Clusters", value="settings_clusters"),
            questionary.Choice("Question Management", value="settings_questions"),
            questionary.Choice("Help", value="settings_help"),
            questionary.Choice("Report Bug", value="report_bug"),
            questionary.Separator(),
            "Exit",
        ]

        choice = questionary.select(
            "--- KubeLingo ---",
            choices=menu_choices,
            use_indicator=True
        ).ask()

        if not choice or choice == "Exit":
            print("Exiting KubeLingo.")
            break

        task_function = tasks.get(choice)
        if task_function:
            task_function()

        print() # for spacing


if __name__ == '__main__':
    main()
