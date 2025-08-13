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
        sanitized_subject = subject.lower().replace(' ', '_').replace('&', 'and')
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


def main():
    """Display the question management menu."""
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(
            description="A unified tool for managing Kubelingo's questions, YAML, and database files.",
            formatter_class=argparse.RawTextHelpFormatter,
        )
        subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

        # --- Sub-parsers from original question_manager.py ---
        p_build_index = subparsers.add_parser('build-index', help='Builds or updates the question index from YAML files.', description="Scans YAML files in a directory, hashes them, and updates the SQLite question database.")
        p_build_index.add_argument('directory', default='yaml/questions', nargs='?', help='Path to the directory containing YAML question files. Defaults to "yaml/questions".')
        p_build_index.add_argument('--quiet', action='store_true', help="Suppress progress output.")
        p_build_index.set_defaults(func=handle_build_index)

        p_list_triage = subparsers.add_parser('list-triage', help='Lists all questions marked for triage.')
        p_list_triage.set_defaults(func=handle_list_triaged)

        p_triage = subparsers.add_parser('triage', help='Marks a question for triage.')
        p_triage.add_argument('question_id', help='The ID of the question to triage.')
        p_triage.set_defaults(func=handle_set_triage_status, un_triage=False)

        p_untriage = subparsers.add_parser('untriage', help='Removes a question from triage.')
        p_untriage.add_argument('question_id', help='The ID of the question to un-triage.')
        p_untriage.set_defaults(func=handle_set_triage_status, un_triage=True)

        p_remove = subparsers.add_parser('remove', help='Removes a question from the database by ID.')
        p_remove.add_argument('question_id', help='The ID of the question to remove.')
        p_remove.set_defaults(func=handle_remove_question)

        # --- Sub-parsers from original generator.py ---
        p_from_pdf = subparsers.add_parser('from-pdf', help="Generate Kubelingo quiz questions from a PDF.")
        p_from_pdf.add_argument("--pdf-path", required=True, help="Path to the PDF file.")
        p_from_pdf.add_argument("--output-file", required=True, help="Path to save the generated YAML file.")
        p_from_pdf.add_argument("--num-questions-per-chunk", type=int, default=5, help="Number of questions to generate per text chunk.")
        p_from_pdf.set_defaults(func=handle_from_pdf)

        p_ai_quiz = subparsers.add_parser('ai-quiz', help='Generate and validate Kubernetes quizzes via OpenAI')
        p_ai_quiz.add_argument('--num', type=int, default=5, help='Number of questions to generate')
        p_ai_quiz.add_argument('--mock', action='store_true', help='Use mock data for testing validation')
        p_ai_quiz.add_argument('--output', default=None, help='Output JSON file path')
        p_ai_quiz.set_defaults(func=handle_ai_quiz)

        p_ref = subparsers.add_parser('resource-reference', help="Generate a YAML quiz for Kubernetes resource references.")
        p_ref.set_defaults(func=handle_resource_reference)

        p_ops = subparsers.add_parser('kubectl-operations', help="Generate the Kubectl Operations quiz manifest.")
        p_ops.set_defaults(func=handle_kubectl_operations)

        p_ai_q = subparsers.add_parser('ai-questions', help="Generate AI questions and save them to a YAML file.")
        p_ai_q.add_argument("--subject", required=True, help="Subject for the new questions (e.g., 'Kubernetes Service Accounts').")
        p_ai_q.add_argument("--category", choices=['Basic', 'Command', 'Manifest'], default='Command', help="Category of questions to generate.")
        p_ai_q.add_argument("--num-questions", type=int, default=3, help="Number of questions to generate.")
        p_ai_q.add_argument("--example-source-file", help="Path to a YAML file to use as a source of example questions.")
        p_ai_q.add_argument("--output-file", required=True, help="Path to the output YAML file.")
        p_ai_q.set_defaults(func=handle_ai_questions)

        p_val = subparsers.add_parser('validation-steps', help="Generate validation_steps for Kubernetes questions")
        p_val.add_argument('in_path', type=Path, help="JSON file or directory to process")
        p_val.add_argument('--overwrite', action='store_true', help="Overwrite original files")
        p_val.set_defaults(func=handle_validation_steps)

        p_sa = subparsers.add_parser('service-account', help="Generate static Kubernetes ServiceAccount questions.")
        p_sa.add_argument('--to-db', action='store_true', help='Add generated questions to the kubelingo database')
        p_sa.add_argument('-n', '--num', type=int, default=0, help='Number of questions to output (default: all)')
        p_sa.add_argument('-o', '--output', type=str, help='Write generated questions to a JSON file')
        p_sa.set_defaults(func=handle_service_account)

        p_man = subparsers.add_parser('manifests', help="Generates YAML quiz manifests and solution files from question-data JSON.")
        p_man.set_defaults(func=handle_manifests)

        # --- Sub-parsers from original yaml_manager.py ---
        p_consolidate = subparsers.add_parser('consolidate', help="Consolidate unique YAML questions from across the repository into a single file.")
        p_consolidate.add_argument('-o', '--output', type=Path, help=f'Output file path for consolidated questions.')
        p_consolidate.set_defaults(func=do_consolidate)
        
        p_create_quizzes = subparsers.add_parser('create-quizzes', help="Create quizzes from consolidated YAML backup.")
        p_create_quizzes.set_defaults(func=do_create_quizzes)
        
        p_deduplicate = subparsers.add_parser('deduplicate', help="Deduplicate YAML questions in a directory.")
        p_deduplicate.add_argument("directory", type=str, help="Directory containing YAML question files.")
        p_deduplicate.add_argument("-o", "--output-file", type=str, help="Output file for consolidated unique questions.")
        p_deduplicate.add_argument("--dry-run", action="store_true", help="Perform a dry run without writing files.")
        p_deduplicate.set_defaults(func=do_deduplicate)
        
        p_diff = subparsers.add_parser('diff', help="Diff YAML backup files to track changes.")
        p_diff.add_argument('files', nargs='*', help="Two YAML files to compare. If not provided, compares all backups.")
        p_diff.add_argument("--range", help="Number of recent versions to diff (e.g., '5' for last 5). 'all' to diff all.", default="all")
        p_diff.set_defaults(func=do_diff)
        
        p_export = subparsers.add_parser('export', help="Export questions DB to YAML.")
        p_export.add_argument("-o", "--output", help="Output YAML file path.")
        p_export.set_defaults(func=do_export)

        p_import_ai = subparsers.add_parser('import-ai', help="Import from YAML with AI categorization.")
        p_import_ai.add_argument("output_db", help="Path to the new SQLite database file to be created.")
        p_import_ai.add_argument("--search-dir", action='append', help="Directory to search for YAML files. Can be used multiple times.")
        p_import_ai.set_defaults(func=do_import_ai)

        p_index = subparsers.add_parser('index', help="Finds all YAML files and creates an index file with their metadata.")
        p_index.set_defaults(func=do_index)
        
        p_init = subparsers.add_parser('init', help="Initializes the database from consolidated YAML backups.")
        p_init.set_defaults(func=do_init)
        
        p_list_backups = subparsers.add_parser('list-backups', help='Finds and displays all YAML backup files.')
        p_list_backups.add_argument("--path-only", action="store_true", help="Only prints the paths of the files.")
        p_list_backups.set_defaults(func=do_list_backups)
        
        p_backup_stats = subparsers.add_parser('backup-stats', help="Show stats for the latest YAML backup file.")
        p_backup_stats.add_argument('paths', nargs='*', help='Path(s) to YAML file(s) or directories.')
        p_backup_stats.add_argument('-p', '--pattern', help='Regex to filter filenames')
        p_backup_stats.add_argument('--json', action='store_true', help='Output stats in JSON format')
        p_backup_stats.set_defaults(func=do_backup_stats)
        
        p_stats = subparsers.add_parser('stats', help="Get statistics about questions in YAML files.")
        p_stats.add_argument("path", nargs='?', default=None, help="Path to a YAML file or directory.")
        p_stats.set_defaults(func=do_statistics)

        p_group_backups = subparsers.add_parser('group-backups', help="Group legacy YAML backup quizzes into a single module.")
        p_group_backups.set_defaults(func=do_group_backups)

        p_import_bak = subparsers.add_parser('import-bak', help="Import questions from legacy YAML backup directory.")
        p_import_bak.set_defaults(func=do_import_bak)

        p_migrate_all = subparsers.add_parser('migrate-all', help="Migrate all YAML questions from standard directories to DB.")
        p_migrate_all.set_defaults(func=do_migrate_all)

        p_migrate_bak = subparsers.add_parser('migrate-bak', help="Clear DB and migrate from YAML backup directory.")
        p_migrate_bak.set_defaults(func=do_migrate_bak)

        p_verify = subparsers.add_parser('verify', help="Verify YAML question import and loading.")
        p_verify.add_argument("paths", nargs='+', help="Path(s) to YAML file(s) or directories to verify.")
        p_verify.set_defaults(func=do_verify)

        p_organize = subparsers.add_parser('organize-generated', help="Consolidate, import, and clean up AI-generated YAML questions.")
        p_organize.add_argument('--source-dir', default='questions/generated_yaml', help="Directory with generated YAML files.")
        p_organize.add_argument('--output-file', default='questions/ai_generated_consolidated.yaml', help="Consolidated output YAML file.")
        p_organize.add_argument('--db-path', default=None, help="Path to the SQLite database file.")
        p_organize.add_argument('--no-cleanup', action='store_true', help="Do not delete original individual YAML files after consolidation.")
        p_organize.add_argument('--dry-run', action='store_true', help="Show what would be done without making changes.")
        p_organize.set_defaults(func=do_organize_generated)

        # New commands from sqlite_manager
        p_index_sqlite = subparsers.add_parser("index-sqlite", help="Index all SQLite files.")
        p_index_sqlite.add_argument("dirs", nargs="*", default=[], help="Directories to scan. Scans repo if not provided.")
        p_index_sqlite.set_defaults(func=do_index_sqlite)

        p_schema = subparsers.add_parser("schema", help="Show SQLite DB schema.")
        p_schema.add_argument('db_path', nargs='?', default=None, help=f"Path to SQLite DB file (default: {DATABASE_FILE})")
        p_schema.add_argument('-o', '--output', type=str, help="Write schema to a file.")
        p_schema.set_defaults(func=do_schema)

        p_list_sqlite = subparsers.add_parser("list-sqlite", help="List SQLite backup files.")
        p_list_sqlite.add_argument('directories', nargs='*', help='Directories to scan (default: configured backup dirs).')
        p_list_sqlite.add_argument("--path-only", action="store_true", help="Only print file paths.")
        p_list_sqlite.set_defaults(func=do_list_sqlite)

        p_unarchive = subparsers.add_parser("unarchive", help="Move SQLite files from archive/ and prune.")
        p_unarchive.set_defaults(func=do_unarchive)

        p_restore = subparsers.add_parser("restore", help="Restore live DB from a backup.")
        p_restore.add_argument('backup_db', nargs='?', help='Path to backup .db file. Interactive if not provided.')
        p_restore.add_argument('--pre-backup-dir', default='backups', help='Dir for pre-restore backup.')
        p_restore.add_argument('--no-pre-backup', action='store_true', help='Skip pre-restore backup.')
        p_restore.add_argument('-y', '--yes', action='store_true', help='Skip confirmation.')
        p_restore.set_defaults(func=do_restore)

        p_create_from_yaml = subparsers.add_parser("create-from-yaml", help="Populate SQLite DB from YAML files.")
        p_create_from_yaml.add_argument("--yaml-files", nargs="*", type=str, help="YAML files. Uses latest backup if not provided.")
        p_create_from_yaml.add_argument("--db-path", type=str, default=None, help="Path to SQLite DB file.")
        p_create_from_yaml.add_argument("--clear", action="store_true", help="Clear DB before populating.")
        p_create_from_yaml.set_defaults(func=do_create_from_yaml)

        p_diff_db = subparsers.add_parser("diff-db", help="Diff two SQLite DBs.")
        p_diff_db.add_argument('db_a', nargs='?', help='First SQLite DB file. Interactive if not provided.')
        p_diff_db.add_argument('db_b', nargs='?', help='Second SQLite DB file. Interactive if not provided.')
        p_diff_db.add_argument('--no-schema', action='store_true', help='Do not compare schema.')
        p_diff_db.add_argument('--no-counts', action='store_true', help='Do not compare row counts.')
        p_diff_db.set_defaults(func=do_diff_db)

        args = parser.parse_args()
        if hasattr(args, 'func'):
            args.func(args)
        else:
            parser.print_help()
    else:
        # Interactive mode
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
            "Exit",
        ]

        while True:
            choice = questionary.select(
                "--- Manage Questions & Data ---",
                choices=menu_choices,
                use_indicator=True
            ).ask()

            if not choice or choice == "Exit":
                print("Exiting.")
                break

            task_function = tasks.get(choice)
            if task_function:
                task_function()

            print() # Add a newline for better spacing
            if not questionary.confirm("Return to the Main Menu?", default=True).ask():
                print("Exiting.")
                break
            print() # Add a newline for better spacing


if __name__ == '__main__':
    main()
