#!/usr/bin/env python3
"""
Kubelingo: A simple CLI tool to quiz commands (or other strings) based on supplied JSON data.
"""
# Load environment variables from a .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import os
import json
import argparse
import sys
import logging
import subprocess
import shutil
import datetime
from dataclasses import asdict
try:
    import readline  # Enable rich input editing, history, and arrow keys
except ImportError:
    pass # readline not available
# Provide pytest.anything for test wildcard assertions
try:
    import pytest
    from unittest.mock import ANY
    pytest.anything = lambda *args, **kwargs: ANY
except ImportError:
    pass

# Support running this script directly: ensure the parent directory is on sys.path
if __name__ == '__main__' and __package__ is None:
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    # Add project root (parent of package dir) so that 'import kubelingo' works
    sys.path.insert(0, os.path.dirname(pkg_dir))
    __package__ = 'kubelingo'

# Base session loader
from kubelingo.modules.base.loader import discover_modules, load_session
from kubelingo.modules.base.session import SessionManager
try:
    from kubelingo.modules.kubernetes.session import (
        get_all_flagged_questions,
        NewSession,
    )
    from kubelingo.modules.kubernetes.study_mode import KubernetesStudyMode
except Exception:
    get_all_flagged_questions = None
    NewSession = None
    KubernetesStudyMode = None
# Unified question-data loaders (question-data/yaml)
from kubelingo.modules.question_generator import AIQuestionGenerator
from kubelingo.modules.db_loader import DBLoader
from kubelingo.sandbox import spawn_pty_shell, launch_container_sandbox
try:
    from kubelingo.self_healing import run_self_healing_cycle
except ImportError:
    # Self-healing feature not available
    def run_self_healing_cycle():
        pass
from kubelingo.utils.path_utils import find_yaml_files
from kubelingo.utils.ui import (
    Fore, Style, print_banner, humanize_module, show_session_type_help, show_quiz_type_help
)
try:
    import questionary
    from questionary import Separator
except ImportError:
    questionary = None
    Separator = None
from pathlib import Path
import subprocess

# Repository root for scripts
repo_root = Path(__file__).resolve().parent.parent
from pathlib import Path
import subprocess
from kubelingo.utils.config import (
    LOGS_DIR,
    HISTORY_FILE,
    LOG_FILE,
    get_openai_api_key,
    save_openai_api_key,
    API_KEY_FILE,
    YAML_QUIZ_DIR,
    get_cluster_configs,
    save_cluster_configs,
    SQLITE_BACKUP_DIRS,
)

def show_history():
    """Display quiz history and aggregated statistics."""
    # The logger is not configured at this stage, so we create a dummy one for the manager.
    # History reading doesn't involve logging in SessionManager.
    dummy_logger = logging.getLogger('kubelingo_history')
    session_manager = SessionManager(dummy_logger)
    history = session_manager.get_history()

    if history is None:
        print(f"No quiz history found ({HISTORY_FILE}).")
        return
    if not isinstance(history, list) or not history:
        print("No quiz history available.")
        return
    print("Quiz History:")
    for entry in history:
        ts = entry.get('timestamp')
        nq = entry.get('num_questions', 0)
        nc = entry.get('num_correct', 0)
        pct = (nc / nq * 100) if nq else 0
        duration = entry.get('duration', '')
        data_file = entry.get('data_file', '')
        filt = entry.get('category_filter') or 'ALL'
        print(f"{ts}: {nc}/{nq} ({pct:.1f}%), Time: {duration}, File: {data_file}, Category: {filt}")
    print()
    # Aggregate per-category performance
    agg = {}
    for entry in history:
        for cat, stats in entry.get('per_category', {}).items():
            asked = stats.get('asked', 0)
            correct = stats.get('correct', 0)
            if cat not in agg:
                agg[cat] = {'asked': 0, 'correct': 0}
            agg[cat]['asked'] += asked
            agg[cat]['correct'] += correct
    if agg:
        print("Aggregate performance per category:")
        for cat, stats in agg.items():
            asked = stats['asked']
            correct = stats['correct']
            pct = (correct / asked * 100) if asked else 0
            print(f"{cat}: {correct}/{asked} ({pct:.1f}%)")
    else:
        print("No per-category stats to aggregate.")
    # Reset terminal colors after history display
    print(Style.RESET_ALL)


def show_modules():
    """Display available DB-backed modules."""
    print(f"{Fore.CYAN}Available quiz modules (from database):{Style.RESET_ALL}")
    try:
        from kubelingo.modules.db_loader import DBLoader
        loader = DBLoader()
        modules = loader.discover()
        if not modules:
            print(f"{Fore.YELLOW}No modules found in the database.{Style.RESET_ALL}")
            print(f"You can populate it using 'kubelingo import-json' or 'kubelingo migrate-yaml'.")
            return

        grouped = {}
        for mod_path in modules:
            name, ext = os.path.splitext(os.path.basename(mod_path))
            if not ext:  # Handle cases where source_file might not have an extension
                ext = ".unknown"
            ext = ext.lstrip('.').upper()
            if ext not in grouped:
                grouped[ext] = []
            grouped[ext].append(humanize_module(name))

        for ext, mods in sorted(grouped.items()):
            print(f"  {Fore.GREEN}{ext}:{Style.RESET_ALL}")
            for name in sorted(mods):
                print(f"    {Fore.YELLOW}{name}{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}Failed to load modules from database: {e}{Style.RESET_ALL}")
def handle_config_command(cmd):
    """Handles 'config' subcommands."""
    import getpass
    if len(cmd) < 3:
        print("Usage: kubelingo config <action> <target> [args...]")
        print("Example: kubelingo config set openai")
        print("Example: kubelingo config list cluster")
        return

    action = cmd[1].lower()
    target = cmd[2].lower()

    if target in ('openai', 'api_key'):
        if action == 'view':
            key = get_openai_api_key()
            if key:
                print(f'OpenAI API key: {key}')
            else:
                print('OpenAI API key is not set.')
        elif action == 'set':
            value = None
            if len(cmd) >= 4:
                value = cmd[3]
            else:
                try:
                    value = getpass.getpass('Enter OpenAI API key: ').strip()
                except (EOFError, KeyboardInterrupt):
                    print(f"\n{Fore.YELLOW}API key setting cancelled.{Style.RESET_ALL}")
                    return

            if value:
                if save_openai_api_key(value):
                    print('OpenAI API key saved.')
                else:
                    print('Failed to save OpenAI API key.')
            else:
                print("No API key provided. No changes made.")
        else:
            print(f"Unknown action '{action}' for openai. Use 'view' or 'set'.")
    elif target == 'cluster':
        configs = get_cluster_configs()
        if action == 'list':
            if not configs:
                print("No Kubernetes cluster connections configured.")
                return
            print("Configured Kubernetes clusters:")
            for name, details in configs.items():
                print(f"  - {name} (context: {details.get('context', 'N/A')})")

        elif action == 'add':
            print("Adding a new Kubernetes cluster connection.")
            try:
                name = questionary.text("Enter a name for this connection:").ask()
                if not name:
                    print("Connection name cannot be empty. Aborting.")
                    return
                if name in configs:
                    print(f"A connection named '{name}' already exists. Aborting.")
                    return

                context = questionary.text("Enter the kubectl context to use:").ask()
                if not context:
                    print("Context cannot be empty. Aborting.")
                    return

                configs[name] = {'context': context}
                if save_cluster_configs(configs):
                    print(f"Cluster connection '{name}' saved.")
                else:
                    print("Failed to save cluster configuration.")
            except (KeyboardInterrupt, EOFError):
                print(f"\n{Fore.YELLOW}Cluster configuration cancelled.{Style.RESET_ALL}")

        elif action == 'remove':
            if not configs:
                print("No Kubernetes cluster connections configured to remove.")
                return

            try:
                choices = list(configs.keys())
                name_to_remove = questionary.select(
                    "Which cluster connection do you want to remove?",
                    choices=choices
                ).ask()

                if name_to_remove:
                    del configs[name_to_remove]
                    if save_cluster_configs(configs):
                        print(f"Cluster connection '{name_to_remove}' removed.")
                    else:
                        print("Failed to save cluster configuration.")
            except (KeyboardInterrupt, EOFError):
                print(f"\n{Fore.YELLOW}Cluster removal cancelled.{Style.RESET_ALL}")

        else:
            print(f"Unknown action '{action}' for cluster. Use 'list', 'add', or 'remove'.")
    else:
        print(f"Unknown config target '{target}'. Supported: openai, cluster.")

def _run_script(script_path: str):
    """Helper to run a script from the project root."""
    full_path = repo_root / script_path
    if not full_path.is_file():
        print(f"{Fore.RED}Error: Script '{full_path}' not found or is not a file.{Style.RESET_ALL}")
        return

    command = [sys.executable, str(full_path)]
    print(f"\n{Fore.CYAN}Running: {' '.join(map(str, command))}{Style.RESET_ALL}")

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Script exited with error code {e.returncode}.{Style.RESET_ALL}")
    except KeyboardInterrupt:
        # This will be caught by the outer loop in handle_tools
        raise
    except Exception as e:
        print(f"{Fore.RED}An error occurred while running the script: {e}{Style.RESET_ALL}")


# Tools/maintenance scripts runner
def handle_tools():
    """Launch the interactive tools menu."""
    if not (questionary and Separator):
        print(f"{Fore.RED}Error: 'questionary' library not found. Please install it with 'pip install questionary'.{Style.RESET_ALL}")
        return

    tasks = {
        # YAML
        'Consolidate Unique Yaml Questions': 'scripts/consolidate_unique_yaml_questions.py',
        'Create Sqlite Db From Yaml': 'scripts/create_sqlite_db_from_yaml.py',
        'Deduplicate Yaml': 'scripts/deduplicate_yaml.py',
        'Dev Verify Yaml Import': 'scripts/dev/verify_yaml_import.py',
        'Diff Yaml Backups': 'scripts/diff_yaml_backups.py',
        'Export Db To Yaml': 'scripts/export_db_to_yaml.py',
        'Import From Yaml With Ai': 'scripts/import_from_yaml_with_ai.py',
        'Index Yaml Files': 'scripts/index_yaml_files.py',
        'Legacy Group Backup Yaml Questions': 'scripts/legacy/group_backup_yaml_questions.py',
        'Legacy Migrate All Yaml Questions': 'scripts/legacy/migrate_all_yaml_questions.py',
        'Restore Db From Yaml': 'scripts/restore_db_from_yaml.py',
        'Restore Yaml To Db': 'scripts/restore_yaml_to_db.py',
        'Show Yaml Backups': 'scripts/show_yaml_backups.py',
        'Write Db From Yaml': 'scripts/write_db_from_yaml.py',
        'Yaml Statistics': 'scripts/yaml_statistics.py',
        # SQLite & DB
        'Diff Sqlite': 'scripts/diff_sqlite.py',
        'Diff Sqlite Backups': 'scripts/diff_sqlite_backups.py',
        'Fix Db Source Paths': 'scripts/fix_db_source_paths.py',
        'Index Sqlite Files': 'scripts/index_sqlite_files.py',
        'Locate Sqlite Backups': 'scripts/locate_sqlite_backups.py',
        'Remove Empty Dbs': 'scripts/remove_empty_dbs.py',
        'Restore Sqlite From Backup': 'scripts/restore_sqlite_from_backup.py',
        'Show Sqlite Backups': 'scripts/show_sqlite_backups.py',
        'Show Sqlite Schema': 'scripts/show_sqlite_schema.py',
        'Unarchive Sqlite': 'scripts/unarchive_sqlite.py',
        'View Db Schema': 'scripts/view_db_schema.py',
        # Questions
        'Categorize Questions': 'scripts/categorize_questions.py',
        'Deduplicate Questions': 'scripts/deduplicate_questions.py',
        'Fix Links': 'scripts/fix_links.py',
        'Format Questions': 'scripts/format_questions.py',
        'Lint Fix Question Format': 'scripts/lint_fix_question_format.py',
        'Reorganize Questions': 'scripts/reorganize_questions.py',
        'Validate Doc Links': 'scripts/validate_doc_links.py',
        'Legacy Add Ui Config Questions': 'scripts/legacy/add_ui_config_questions.py',
        'Legacy Check Docs Links': 'scripts/legacy/check_docs_links.py',
        'Legacy Enrich Unseen Questions': 'scripts/legacy/enrich_unseen_questions.py',
        'Legacy Find Duplicate Questions': 'scripts/legacy/find_duplicate_questions.py',
        'Legacy Reorganize Question Data': 'scripts/legacy/reorganize_question_data.py',
        # Generate
        'Generate Kubectl Operations Quiz': 'scripts/generate_kubectl_operations_quiz.py',
        'Generate Manifests': 'scripts/generate_manifests.py',
        'Generate Resource Reference Quiz': 'scripts/generate_resource_reference_quiz.py',
        'Legacy Generate Ai Quiz': 'scripts/legacy/generate_ai_quiz.py',
        'Legacy Generate Service Account Questions': 'scripts/legacy/generate_service_account_questions.py',
        'Legacy Generate Validation Steps': 'scripts/legacy/generate_validation_steps.py',
        # Other
        'Bug Ticket': 'scripts/bug_ticket.py',
        'Consolidate Backups': 'scripts/consolidate_backups.py',
        'Maintenance Menu': 'scripts/maintenance_menu.py',
        'Update Schema Category': 'scripts/update_schema_category.py',
        'Legacy Full Migrate And Cleanup': 'scripts/legacy/full_migrate_and_cleanup.py',
        'Legacy Merge Solutions': 'scripts/legacy/merge_solutions.py',
        'Legacy Suggest Citations': 'scripts/legacy/suggest_citations.py',
        'Legacy Toolbox': 'scripts/legacy/toolbox.py',
    }

    # Filter out tasks where the script doesn't exist to prevent errors
    existing_tasks = {name: path for name, path in tasks.items() if (repo_root / path).is_file()}

    # Group tasks by category for the menu
    menu_groups = {
        "YAML": [
            'Consolidate Unique Yaml Questions', 'Create Sqlite Db From Yaml', 'Deduplicate Yaml',
            'Dev Verify Yaml Import', 'Diff Yaml Backups', 'Export Db To Yaml',
            'Import From Yaml With Ai', 'Index Yaml Files', 'Legacy Group Backup Yaml Questions',
            'Legacy Migrate All Yaml Questions', 'Restore Db From Yaml', 'Restore Yaml To Db',
            'Show Yaml Backups', 'Write Db From Yaml', 'Yaml Statistics'
        ],
        "SQLite & DB": [
            'Diff Sqlite', 'Diff Sqlite Backups',
            'Fix Db Source Paths', 'Index Sqlite Files', 'Locate Sqlite Backups',
            'Remove Empty Dbs', 'Restore Sqlite From Backup', 'Show Sqlite Backups',
            'Show Sqlite Schema', 'Unarchive Sqlite', 'View Db Schema'
        ],
        "Questions": [
            'Categorize Questions', 'Deduplicate Questions', 'Fix Links', 'Format Questions',
            'Lint Fix Question Format', 'Reorganize Questions', 'Validate Doc Links',
            'Legacy Add Ui Config Questions', 'Legacy Check Docs Links',
            'Legacy Enrich Unseen Questions', 'Legacy Find Duplicate Questions',
            'Legacy Reorganize Question Data'
        ],
        "Generate": [
            'Generate Kubectl Operations Quiz', 'Generate Manifests', 'Generate Resource Reference Quiz',
            'Legacy Generate Ai Quiz', 'Legacy Generate Service Account Questions',
            'Legacy Generate Validation Steps'
        ],
        "Other": [
            'Bug Ticket', 'Consolidate Backups', 'Maintenance Menu', 'Update Schema Category',
            'Legacy Full Migrate And Cleanup', 'Legacy Merge Solutions', 'Legacy Suggest Citations', 'Legacy Toolbox'
        ]
    }

    choices = []
    for category, names in menu_groups.items():
        choices.append(Separator(f"=== {category} ==="))
        # Add only tasks that have an existing script file
        choices.extend(sorted([name for name in names if name in existing_tasks]))

    choices.extend([Separator("---------------"), "Cancel"])

    try:
        while True:
            choice = questionary.select(
                "Select a maintenance task:",
                choices=choices,
                use_indicator=True
            ).ask()

            if choice is None or choice == "Cancel":
                print("Operation cancelled.")
                break

            if choice in existing_tasks:
                _run_script(existing_tasks[choice])
                if not questionary.confirm("Run another task?", default=True).ask():
                    break
            else:
                print(f"{Fore.YELLOW}Task '{choice}' script not found or not implemented.{Style.RESET_ALL}")

    except (KeyboardInterrupt, EOFError):
        print(f"\n{Fore.YELLOW}Exiting tools menu.{Style.RESET_ALL}")


def _rebuild_db_from_yaml():
    """
    Clears the database and rebuilds it from all discoverable YAML source files.
    """
    from kubelingo.database import get_db_connection, add_question
    from kubelingo.modules.yaml_loader import YAMLLoader

    print("Attempting to rebuild database from source YAML files...")
    conn = get_db_connection()
    try:
        print("Clearing existing questions from the database...")
        conn.execute("DELETE FROM questions")
        conn.commit()
        print("Database cleared.")

        print("Discovering and loading questions from YAML files...")
        # Search in both default YAML dir and the user's custom 'yaml' dir.
        search_dirs = [str(YAML_QUIZ_DIR), str(repo_root / 'yaml')]
        yaml_files = find_yaml_files(search_dirs)

        if not yaml_files:
            print(f"{Fore.RED}No YAML source files found in {search_dirs}. Cannot rebuild database.{Style.RESET_ALL}")
            return False

        total_loaded = 0
        loader = YAMLLoader()
        for yaml_file in yaml_files:
            try:
                questions = loader.load_file(str(yaml_file))
                if not questions:
                    continue
                for q in questions:
                    q_dict = asdict(q)
                    # The 'type' key from YAML is not a DB column.
                    q_dict.pop('type', None)
                    add_question(conn=conn, **q_dict)
                total_loaded += len(questions)
                print(f"  - Loaded {len(questions)} questions from {os.path.basename(yaml_file)}")
            except Exception as e:
                print(f"{Fore.RED}Failed to load {yaml_file}: {e}{Style.RESET_ALL}")

        conn.commit()
        if total_loaded > 0:
            print(f"\n{Fore.GREEN}Successfully loaded {total_loaded} questions into the database.{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.YELLOW}No questions were loaded from any YAML files.{Style.RESET_ALL}")
            return False

    except Exception as e:
        print(f"{Fore.RED}An error occurred during database rebuild: {e}{Style.RESET_ALL}")
        return False
    finally:
        conn.close()


def restore_db():
    """
    Merges questions from the master backup into the live database.
    This is an additive process and will not remove any custom or AI-generated questions.
    Existing questions from the master backup will be updated if they have changed.
    """
    import sqlite3
    from kubelingo.database import get_db_connection, add_question
    from kubelingo.utils.config import MASTER_DATABASE_FILE, SECONDARY_MASTER_DATABASE_FILE

    # Choose a backup database file: prefer master, fallback to secondary
    backup_file = None
    if os.path.exists(MASTER_DATABASE_FILE) and os.path.getsize(MASTER_DATABASE_FILE) > 0:
        backup_file = MASTER_DATABASE_FILE
    elif os.path.exists(SECONDARY_MASTER_DATABASE_FILE) and os.path.getsize(SECONDARY_MASTER_DATABASE_FILE) > 0:
        backup_file = SECONDARY_MASTER_DATABASE_FILE
    if not backup_file:
        print(f"{Fore.YELLOW}No valid master database backup found. Falling back to rebuilding from YAML sources.{Style.RESET_ALL}")
        if not _rebuild_db_from_yaml():
             print(f"{Fore.RED}Database rebuild from YAML failed. Database may be empty.{Style.RESET_ALL}")
        return

    print(f"Merging questions from backup '{backup_file}'...")
    try:
        master_conn = sqlite3.connect(f'file:{backup_file}?mode=ro', uri=True)
        master_conn.row_factory = sqlite3.Row
        master_cursor = master_conn.cursor()
        master_cursor.execute("SELECT * FROM questions")
        master_questions = master_cursor.fetchall()
        column_names = [d[0] for d in master_cursor.description]
        master_conn.close()

        if not master_questions:
            print(f"{Fore.YELLOW}Master backup contains no questions. Nothing to merge.{Style.RESET_ALL}")
            return

        live_conn = get_db_connection()
        updated_count = 0
        for row in master_questions:
            q_dict = dict(zip(column_names, row))

            # The add_question function expects complex types, not JSON strings.
            for key in ['validation_steps', 'validator', 'pre_shell_cmds', 'initial_files', 'answers']:
                if q_dict.get(key) and isinstance(q_dict[key], str):
                    try:
                        q_dict[key] = json.loads(q_dict[key])
                    except (json.JSONDecodeError, TypeError):
                        # On error, set to a sensible default. add_question handles None.
                        q_dict[key] = None

            # add_question uses INSERT OR REPLACE, which is what we want for a merge.
            add_question(conn=live_conn, **q_dict)
            updated_count += 1

        live_conn.close()
        print(f"{Fore.GREEN}Successfully merged/updated {updated_count} questions from the master backup.{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}Failed to merge from database: {e}{Style.RESET_ALL}")


def handle_load_yaml(cmd_args):
    """Loads questions from a YAML file, clearing the database first."""
    if len(cmd_args) != 1:
        print(f"{Fore.RED}Usage: kubelingo load-yaml <path-to-yaml-file>{Style.RESET_ALL}")
        return

    yaml_file = cmd_args[0]
    if not os.path.exists(yaml_file):
        print(f"{Fore.RED}File not found: {yaml_file}{Style.RESET_ALL}")
        return

    if questionary is None:
        print(f"{Fore.RED}`questionary` package not installed. Cannot proceed with interactive confirmation.{Style.RESET_ALL}")
        return

    try:
        confirmed = questionary.confirm(
            f"This will CLEAR all questions from the database and load new ones from '{os.path.basename(yaml_file)}'. "
            "This action cannot be undone. Are you sure?",
            default=False
        ).ask()
        if not confirmed:
            print(f"{Fore.YELLOW}Import cancelled.{Style.RESET_ALL}")
            return

        from kubelingo.database import get_db_connection, add_question
        from kubelingo.modules.yaml_loader import YAMLLoader

        print("Clearing existing questions from the database...")
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM questions")
            conn.commit()
            print("Database cleared.")

            print(f"Loading questions from {yaml_file}...")
            loader = YAMLLoader()
            questions = loader.load_file(yaml_file)

            if not questions:
                print(f"{Fore.YELLOW}No questions found in {yaml_file}.{Style.RESET_ALL}")
                conn.close()
                return

            for q in questions:
                q_dict = asdict(q)
                # The 'type' key may exist in some source YAML files, but it's not a field
                # in the 'questions' database table. We must remove it before calling add_question.
                q_dict.pop('type', None)
                add_question(conn=conn, **q_dict)

            conn.commit()
            print(f"{Fore.GREEN}Successfully loaded {len(questions)} questions into the database.{Style.RESET_ALL}")

        finally:
            conn.close()

    except (KeyboardInterrupt, EOFError):
        print(f"\n{Fore.YELLOW}Import process cancelled.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}An error occurred during import: {e}{Style.RESET_ALL}")


def manage_questions_interactive():
    """Interactive prompt for managing questions."""
    if questionary is None:
        print(f"{Fore.RED}`questionary` package not installed. Cannot show interactive menu.{Style.RESET_ALL}")
        return
    try:
        from kubelingo.database import get_flagged_questions
        flagged_questions = get_flagged_questions()
        flagged_count = len(flagged_questions)

        choices = [
            questionary.Separator("--- Question Management ---"),
            {
                "name": f"List flagged questions for review ({flagged_count} flagged)",
                "value": "list_flagged",
                "disabled": flagged_count == 0
            },
            {"name": "Enrich all questions with sources (uses AI)", "value": "enrich_sources"},
            questionary.Separator("--- Data Recovery ---"),
            {"name": "Merge questions from original backup (additive)", "value": "restore_db"},
            questionary.Separator(),
            {"name": "Cancel", "value": "cancel"}
        ]
        action = questionary.select(
            "Select a question management action:",
            choices=choices,
            use_indicator=True
        ).ask()

        if action is None or action == "cancel":
            return

        if action == "list_flagged":
            if not flagged_questions:
                print(f"{Fore.YELLOW}No questions are currently flagged for review.{Style.RESET_ALL}")
                return
            print(f"{Fore.CYAN}Questions flagged for review:{Style.RESET_ALL}")
            for q in flagged_questions:
                source_info = f"({q['source_file']})" if q.get('source_file') else ""
                print(f"  - [{q['id']}] {q['prompt']} {source_info}")
        elif action == "enrich_sources":
            enrich_sources()
        elif action == "restore_db":
            confirmed = questionary.confirm(
                "This will add questions from the original backup to your database. "
                "AI-generated and custom questions will not be affected. "
                "Are you sure you want to continue?",
                default=False
            ).ask()
            if confirmed:
                restore_db()
            else:
                print(f"{Fore.YELLOW}Merge cancelled.{Style.RESET_ALL}")

        print()

    except (KeyboardInterrupt, EOFError):
        print()
        return


def manage_config_interactive():
    """Interactive prompt for managing configuration."""
    if questionary is None:
        print(f"{Fore.RED}`questionary` package not installed. Cannot show interactive menu.{Style.RESET_ALL}")
        return
    try:
        action = questionary.select(
            "What would you like to do?",
            choices=[
                {"name": "View current OpenAI API key", "value": "view_openai"},
                {"name": "Set/Update OpenAI API key", "value": "set_openai"},
                questionary.Separator("Kubernetes Clusters"),
                {"name": "List configured clusters", "value": "list_clusters"},
                {"name": "Add a new cluster connection", "value": "add_cluster"},
                {"name": "Remove a cluster connection", "value": "remove_cluster"},
                questionary.Separator(),
                {"name": "Cancel", "value": "cancel"}
            ],
            use_indicator=True
        ).ask()

        if action is None or action == "cancel":
            return

        if action == 'view_openai':
            handle_config_command(['config', 'view', 'openai'])
        elif action == 'set_openai':
            handle_config_command(['config', 'set', 'openai'])
        elif action == 'list_clusters':
            handle_config_command(['config', 'list', 'cluster'])
        elif action == 'add_cluster':
            handle_config_command(['config', 'add', 'cluster'])
        elif action == 'remove_cluster':
            handle_config_command(['config', 'remove', 'cluster'])

        # Add a newline for better spacing after the operation
        print()

    except (KeyboardInterrupt, EOFError):
        # A newline is needed to prevent the next prompt from appearing on the same line.
        print()
        return



def show_study_main_menu():
    """Shows the main interactive menu for study, review, and settings."""
    if not (questionary and Separator):
        print(f"{Fore.RED}Error: 'questionary' library not found. Please install it with 'pip install questionary'.{Style.RESET_ALL}")
        return

    while True:
        try:
            action = questionary.select(
                "Main Menu:",
                choices=[
                    {"name": "Start Study Mode", "value": "study"},
                    {"name": "Question Management", "value": "questions"},
                    {"name": "Settings", "value": "settings"},
                    Separator(),
                    {"name": "Exit", "value": "exit"}
                ],
                use_indicator=True
            ).ask()

            if action is None or action == "exit":
                break

            if action == "study":
                if KubernetesStudyMode:
                    level = questionary.select(
                        "What is your current overall skill level?",
                        choices=["beginner", "intermediate", "advanced"],
                        default="intermediate",
                        use_indicator=True,
                    ).ask()
                    if not level:
                        continue

                    study_session = KubernetesStudyMode()
                    study_session.start_study_session(user_level=level)
                else:
                    print(f"{Fore.RED}Study mode is not available.{Style.RESET_ALL}")
            elif action == "questions":
                manage_questions_interactive()
            elif action == "settings":
                manage_config_interactive()
            print() # for spacing
        except (KeyboardInterrupt, EOFError):
            print()
            break


def enrich_sources():
    """Finds and adds sources for questions without them."""
    # Check for API key first
    api_key = os.getenv('OPENAI_API_KEY') or get_openai_api_key()
    if not api_key:
        print(f"{Fore.RED}This feature requires an OpenAI API key. Please configure it first.{Style.RESET_ALL}")
        manage_config_interactive()
        api_key = os.getenv('OPENAI_API_KEY') or get_openai_api_key()
        if not api_key:
            return

    from kubelingo.database import get_all_questions, add_question, get_db_connection
    from kubelingo.modules.ai_evaluator import AIEvaluator

    print(f"{Fore.CYAN}Starting source enrichment for all questions in the database...{Style.RESET_ALL}")
    evaluator = AIEvaluator()

    all_questions = get_all_questions()
    questions_to_update = [q for q in all_questions if not q.get('source')]

    if not questions_to_update:
        print(f"{Fore.GREEN}All questions already have sources. Nothing to do.{Style.RESET_ALL}")
        return

    print(f"\nFound {Fore.YELLOW}{len(questions_to_update)}{Style.RESET_ALL} questions without a source. Starting enrichment...\n")

    conn = get_db_connection()
    if not conn:
        print(f"{Fore.RED}Failed to get database connection.{Style.RESET_ALL}")
        return

    updated_count = 0
    failed_count = 0
    for q in questions_to_update:
        prompt = q.get('prompt')
        print(f"  - Processing question ID {q['id']}: '{prompt[:60].strip()}...'")
        source_url = evaluator.find_source_for_question(prompt)
        if source_url:
            print(f"    {Fore.GREEN}-> Found source: {source_url}{Style.RESET_ALL}")
            try:
                # add_question can be used to update existing questions by ID
                add_question(
                    conn,
                    id=q['id'],
                    prompt=q['prompt'],
                    source_file=q['source_file'],
                    response=q.get('response'),
                    category=q.get('category'),
                    source=source_url,
                    validation_steps=q.get('validation_steps'),
                    validator=q.get('validator'),
                    review=q.get('review', False)
                )
                conn.commit()
                updated_count += 1
            except Exception as e:
                print(f"    {Fore.RED}-> Failed to update question {q['id']} in DB: {e}{Style.RESET_ALL}")
                failed_count += 1
        else:
            print(f"    {Fore.YELLOW}-> Could not find a source.{Style.RESET_ALL}")
            failed_count += 1

    conn.close()
    print(f"\n{Fore.CYAN}Enrichment complete.{Style.RESET_ALL}")
    print(f"  - {Fore.GREEN}Successfully updated: {updated_count}{Style.RESET_ALL}")
    print(f"  - {Fore.RED}Failed or skipped: {failed_count}{Style.RESET_ALL}")


# Legacy alias for cloud-mode static branch
def main():
    # Prevent re-entrant execution inside a sandbox shell.
    if os.getenv('KUBELINGO_SANDBOX_ACTIVE') == '1':
        # This guard prevents the CLI from re-launching itself inside a sandbox
        # shell, which would cause a nested prompt and session cancellation.
        return

    os.makedirs(LOGS_DIR, exist_ok=True)
    # Initialize the questions database and ensure schema is up-to-date (adds 'review' column)
    try:
        from kubelingo.database import init_db
        init_db()
    except Exception:
        pass
    # Initialize logging for both interactive and non-interactive modes
    import logging
    log_level = os.getenv('KUBELINGO_LOG_LEVEL', 'INFO').upper()
    numeric_level = getattr(logging, log_level, logging.INFO)
    logging.basicConfig(
        filename=LOGS_DIR + '/quiz_kubernetes_log.txt',
        level=numeric_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    # Support 'kubelingo sandbox [pty|docker]' as subcommand syntax
    if len(sys.argv) >= 3 and sys.argv[1] == 'sandbox' and sys.argv[2] in ('pty', 'docker'):
        # rewrite to explicit sandbox-mode flag
        sys.argv = [sys.argv[0], sys.argv[1], '--sandbox-mode', sys.argv[2]] + sys.argv[3:]
    # Only display banner when running interactively (not help or piped output)
    if sys.stdout.isatty() and sys.stdin.isatty() and '--help' not in sys.argv and '-h' not in sys.argv:
        print_banner()
        print()
    # Load OpenAI API key from config file or prompt user if not set
    import getpass
    is_help_request = '--help' in sys.argv or '-h' in sys.argv
    is_config_command = len(sys.argv) > 1 and sys.argv[1] == 'config'

    if not os.getenv('OPENAI_API_KEY'):
        api_key = get_openai_api_key()
        if api_key:
            os.environ['OPENAI_API_KEY'] = api_key
        elif not is_help_request and not is_config_command and sys.stdin.isatty():
            try:
                prompt = getpass.getpass('Enter your OpenAI API key to enable AI features (leave blank to skip): ')
                if prompt:
                    if save_openai_api_key(prompt):
                        os.environ['OPENAI_API_KEY'] = prompt.strip()
                        print(f"{Fore.GREEN}OpenAI API key saved to {API_KEY_FILE}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Failed to save API key.{Style.RESET_ALL}")
            except (EOFError, KeyboardInterrupt):
                print(f"\n{Fore.YELLOW}Skipping API key setup.{Style.RESET_ALL}")
    # Warn prominently if no OpenAI API key is available (skip when showing help)
    if '--help' not in sys.argv and '-h' not in sys.argv and not os.getenv('OPENAI_API_KEY'):
        print(f"{Fore.RED}AI explanations are disabled: no OpenAI API key provided.{Style.RESET_ALL}")
    parser = argparse.ArgumentParser(
        prog='kubelingo',
        usage='kubelingo [OPTIONS] [command]',
        description='Kubelingo: Interactive kubectl and YAML quiz tool'
    )
    # Unified exercise mode: run questions from question-data modules
    parser.add_argument('--exercise-module', type=str,
                        help='Run unified live exercise for a question-data module')
    
    # Kubernetes module shortcut
    parser.add_argument('--k8s', action='store_true', dest='k8s_mode',
                        help='Run Kubernetes exercises. A shortcut for the "kubernetes" module.')

    # Sandbox modes (deprecated flags) and new sandbox command support
    parser.add_argument('--pty', action='store_true', help="[DEPRECATED] Use 'kubelingo sandbox pty'.")
    parser.add_argument('--docker', action='store_true', help="[DEPRECATED] Use 'kubelingo sandbox docker'.")
    parser.add_argument('--sandbox-mode', choices=['pty', 'docker', 'container'], dest='sandbox_mode',
                        help='Sandbox mode: pty (default), docker, or container.')

    # Core quiz options
    parser.add_argument('-f', '--file', type=str, default=None,
                        help='Path to quiz source file, used as an identifier to load from database.')
    parser.add_argument('-n', '--num', type=int, default=0,
                        help='Number of questions to ask (default: all)')
    parser.add_argument('--randomize', action='store_true',
                        help='Randomize question order (for modules that support it)')
    parser.add_argument('--quiz', type=str, help='Select a quiz by name.')
    parser.add_argument('-c', '--category', type=str,
                        help='Limit quiz to a specific category.')
    parser.add_argument('--list-categories', action='store_true',
                        help='List available categories and exit')
    parser.add_argument('--history', action='store_true',
                        help='Show quiz history and statistics')
    parser.add_argument('--review-flagged', '--review-only', '--flagged', dest='review_only', action='store_true',
                        help='Quiz on flagged questions only.')
    parser.add_argument('--ai-eval', action='store_true',
                        help='Use AI for evaluation (needs OPENAI_API_KEY).')
    parser.add_argument('--start-cluster', action='store_true',
                        help='Start a temporary Kind cluster for the session.')
    # Configuration management (API keys, cluster contexts)
    parser.add_argument('--config', '-g', action='store_true',
                        help='Enter configuration mode to set API keys or Kubernetes clusters.')

    # Module-based exercises. Handled as a list to support subcommands like 'sandbox pty'.
    parser.add_argument('command', nargs='*',
                        help="Command to run (e.g. 'study', 'kubernetes', 'migrate-yaml', 'sandbox pty', 'config', 'questions', 'db', 'enrich-sources', 'tools', 'load-yaml', 'monitor', 'self-heal', 'heal')")
    parser.add_argument('--list-modules', action='store_true',
                        help='List available exercise modules and exit')
    parser.add_argument('--list-yaml', action='store_true',
                        help='List available YAML quiz files and exit')
    parser.add_argument('-u', '--custom-file', type=str, dest='custom_file',
                        help='Path to custom quiz JSON file for kustom module')
    parser.add_argument('--exercises', type=str,
                        help='Path to custom exercises JSON file for a module')
    parser.add_argument('--cluster-context', type=str,
                        help='Kubernetes cluster context to use for a module')
    # --live is deprecated, as all k8s exercises are now sandbox-based.
    # It is kept for backward compatibility but has no effect.
    parser.add_argument('--live', action='store_true', help=argparse.SUPPRESS)
    # Question-data enrichment: dedupe & AI-enrich explanations
    parser.add_argument(
        '--enrich', nargs=2, metavar=('SRC_DIR', 'DEST_FILE'),
        help='Enrich & dedupe questions from SRC_DIR to DEST_FILE.'
    )
    parser.add_argument(
        '--dry-run-enrich', action='store_true',
        help='Dry run enrichment (no file writes or API calls)'
    )
    # Enrichment feature flags
    parser.add_argument(
        '--generate-validations', action='store_true',
        help='Generate validation steps for questions using AI.'
    )
    parser.add_argument(
        '--list-questions', action='store_true',
        help='List all question prompts for the selected quiz and exit'
    )
    parser.add_argument(
        '--ai-question', type=str, metavar='TOPIC',
        help='Generate one AI question on a topic and exit.'
    )
    parser.add_argument(
        '--ai-questions', nargs=2, metavar=('COUNT','TOPIC'),
        help='Generate multiple AI questions and exit.'
    )
    parser.add_argument(
        '--ai-save', type=str, metavar='FILE',
        help='Save AI-generated questions and answers to a JSON file.'
    )
    parser.add_argument(
        '--generate-sa-questions', type=int, metavar='COUNT',
        help='Generate COUNT static ServiceAccount questions and add to database.'
    )
    parser.add_argument(
        '--enrich-model', type=str, default='gpt-3.5-turbo',
        help='AI model for enriching questions.'
    )
    parser.add_argument(
        '--enrich-format', choices=['json','yaml'], default='json',
        help='Output format for enriched questions (json or yaml).'
    )

    # Handle question-data enrichment early and exit
    enrich_args, _ = parser.parse_known_args()
    if enrich_args.enrich:
        src, dst = enrich_args.enrich
        script = repo_root / 'scripts' / 'enrich_and_dedup_questions.py'
        cmd = [sys.executable, str(script), src, dst]
        if enrich_args.dry_run_enrich:
            cmd.append('--dry-run')
        if enrich_args.generate_validations:
            cmd.append('--generate-validations')
        # Forward model and format settings
        cmd.extend(['--model', enrich_args.enrich_model])
        cmd.extend(['--format', enrich_args.enrich_format])
        subprocess.run(cmd)
        return
    # For bare invocation (no flags or commands), present an interactive menu.
    # Otherwise, parse arguments from command line.
    if len(sys.argv) == 1:
        # Interactive mode.
        args = argparse.Namespace(
            file=None, num=0, randomize=False, category=None, list_categories=False,
            history=False, review_only=False, ai_eval=False, command=[], list_modules=False,
            custom_file=None, exercises=None, cluster_context=None, live=False, k8s_mode=False,
            pty=True, docker=False, sandbox_mode='pty', exercise_module=None, module='kubernetes',
            start_cluster=False
        )

        if not (questionary and sys.stdin.isatty() and sys.stdout.isatty()):
            print("Interactive mode requires 'questionary' package and an interactive terminal.")
            return

        logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')
        logger = logging.getLogger()
        session = load_session(args.module, logger)
        if not session or not session.initialize():
            print(Fore.RED + f"Module '{args.module}' initialization failed." + Style.RESET_ALL)
            return

        try:
            # For bare 'kubelingo' invocations, the session runner will present a DB-driven menu.
            session.run_exercises(args)
            session.cleanup()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.YELLOW}Exiting.{Style.RESET_ALL}")
        return
    else:
        # Non-interactive mode
        args = parser.parse_args()
        # List YAML quiz files and exit
        if getattr(args, 'list_yaml', False):
            try:
                from kubelingo.modules.yaml_loader import YAMLLoader
                loader = YAMLLoader()
                files = loader.discover()
                if not files:
                    print('No YAML quiz files found.')
                else:
                    print('Available YAML quiz files:')
                    for path in files:
                        print(f'  - {path}')
            except Exception as e:
                print(f'Error listing YAML files: {e}')
            return
        # If --config flag provided, launch interactive config
        if getattr(args, 'config', False):
            manage_config_interactive()
            return
        # Handle config subcommand: kubelingo config <view|set> openai [KEY]
        if args.command and len(args.command) > 0:
            cmd_name = args.command[0]
            if cmd_name == 'study':
                show_study_main_menu()
                return
            elif cmd_name == 'config':
                handle_config_command(args.command)
                return
            elif cmd_name == 'monitor':
                from kubelingo.agent.monitor import HealthMonitor
                monitor = HealthMonitor(repo_path=repo_root)
                print("Running health monitor to detect issues...")
                has_issues, output = monitor.detect_issues()
                if not has_issues:
                    print("✅ No issues detected. All tests passed.")
                else:
                    print("🚨 Issues detected. Test output:")
                    print(output)
                return
            elif cmd_name in ('self-heal', 'heal'):
                run_self_healing_cycle()
                return
            elif cmd_name == 'enrich-sources':
                enrich_sources()
                return
            elif cmd_name == 'load-yaml':
                handle_load_yaml(args.command[1:])
                return
            elif cmd_name == 'questions':
                manage_questions_interactive()
                return
            elif cmd_name == 'tools':
                handle_tools()
                return
            elif cmd_name in ('migrate-yaml', 'import-json', 'import-yaml'):
                # Merge questions from the master backup into the live database
                try:
                    restore_db()
                except Exception as e:
                    print(f"{Fore.RED}Failed to migrate questions from backup: {e}{Style.RESET_ALL}")
                return
            elif cmd_name == 'restore_db':
                restore_db()
                return
        # Handle on-demand static ServiceAccount questions generation and exit
        if args.generate_sa_questions:
            script = repo_root / 'scripts' / 'generate_service_account_questions.py'
            cmd = [sys.executable, str(script), '-n', str(args.generate_sa_questions), '--to-db']
            subprocess.run(cmd)
            return
        # Handle on-demand AI-generated question and exit
        if args.ai_questions:
            # Generate multiple AI-based questions on a given topic
            try:
                count_str, topic = args.ai_questions
                count = int(count_str)
            except Exception:
                print(f"{Fore.RED}Invalid usage: --ai-questions requires COUNT and TOPIC.{Style.RESET_ALL}")
                return
            generator = AIQuestionGenerator()
            questions = generator.generate_questions(topic, count)
            if not questions:
                print(f"{Fore.RED}Failed to generate AI questions for topic '{topic}'.{Style.RESET_ALL}")
                return
            # Prepare items for display and optional saving
            items = [{'question': q.prompt, 'answer': q.response} for q in questions]
            # Save to file if requested
            if args.ai_save:
                out_path = args.ai_save
                out_dir = os.path.dirname(out_path) or '.'
                os.makedirs(out_dir, exist_ok=True)
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(items, f, indent=2, ensure_ascii=False)
                print(f"\n{Fore.GREEN}Saved {len(items)} items to {out_path}{Style.RESET_ALL}")
            # Display generated questions and answers
            print(f"\n{Fore.CYAN}AI-generated questions on '{topic}':{Style.RESET_ALL}")
            for idx, item in enumerate(items, start=1):
                print(f"{idx}. Q: {item['question']}")
                print(f"   A: {item['answer']}")
            return
        if args.ai_question:
            topic = args.ai_question.strip()
            generator = AIQuestionGenerator()
            base_q = {'prompt': f'Topic: {topic}', 'validation_steps': []}
            new_q = generator.generate_question(base_q)
            if not new_q or 'prompt' not in new_q:
                print(f"{Fore.RED}Failed to generate AI question for topic '{topic}'.{Style.RESET_ALL}")
                return
            prompt_text = new_q['prompt'].strip()
            # Validate topic mentioned in prompt
            if topic.lower() not in prompt_text.lower():
                print(f"{Fore.YELLOW}Warning: Generated question may lack explicit reference to topic '{topic}'.{Style.RESET_ALL}")
            print(f"\n{Fore.CYAN}AI-generated question:{Style.RESET_ALL}\n{prompt_text}\n")
            if new_q.get('validation_steps'):
                print(f"{Fore.CYAN}Validation steps:{Style.RESET_ALL}")
                for step in new_q['validation_steps']:
                    cmd = step.get('cmd', '')
                    print(f"  - {cmd}")
            return

        if args.quiz:
            # Dynamically discover available quiz modules from the database for --quiz
            try:
                from kubelingo.modules.db_loader import DBLoader
                from kubelingo.utils.ui import humanize_module
                loader = DBLoader()
                modules = loader.discover()
                quiz_map = {}
                for src in modules:
                    base = os.path.splitext(os.path.basename(src))[0]
                    name = humanize_module(base)
                    quiz_map[name] = src
            except Exception:
                quiz_map = {}
            if args.quiz in quiz_map:
                args.file = quiz_map[args.quiz]
            else:
                parser.error(
                    f"Quiz '{args.quiz}' not found. "
                    f"Available quizzes: {', '.join(quiz_map.keys())}"
                )

        # If a quiz is selected without specifying the number of questions, ask interactively.
        if args.quiz and args.num == 0 and questionary and sys.stdin.isatty() and sys.stdout.isatty():
            try:
                num_str = questionary.text(
                    "Enter number of questions (or press Enter for all):",
                    default=""
                ).ask()
                if num_str:
                    if num_str.isdigit() and int(num_str) > 0:
                        args.num = int(num_str)
                    else:
                        print(f"{Fore.YELLOW}Invalid input. Defaulting to all questions.{Style.RESET_ALL}")
            except (KeyboardInterrupt, EOFError):
                print(f"\n{Fore.YELLOW}Exiting.{Style.RESET_ALL}")
                return

        args.module = None
        # Early flags: history and list-modules
        if args.history:
            show_history()
            return
        if args.list_modules:
            show_modules()
            return


        # Process positional command
        args.sandbox_submode = None
        if args.command:
            args.module = args.command[0]
            if args.module == 'k8s':
                args.module = 'kubernetes'
            if args.module == 'sandbox' and len(args.command) > 1:
                subcommand = args.command[1]
                if subcommand in ['pty', 'docker']:
                    args.sandbox_submode = subcommand
                else:
                    parser.error(f"unrecognized arguments: {subcommand}")
        # Sandbox mode dispatch: if specified with other args, they are passed to the module.
        # If run alone, they launch a shell and exit.
        # Launch sandbox: new "sandbox" module or legacy --pty/--docker flags
        if args.module == 'sandbox' or ((args.pty or args.docker)
                                        and args.module is None
                                        and not args.k8s_mode
                                        and not args.exercise_module):
                # Deprecation warning for legacy flags
                if args.pty or args.docker:
                    print(f"{Fore.YELLOW}Warning: --pty and --docker flags are deprecated. Use 'kubelingo sandbox --sandbox-mode [pty|docker]' instead.{Style.RESET_ALL}", file=sys.stderr)
                # determine mode: positional > explicit flag > legacy flags > default
                if getattr(args, 'sandbox_submode', None):
                    mode = args.sandbox_submode
                elif args.sandbox_mode:
                    mode = args.sandbox_mode
                elif args.docker:
                    mode = 'docker'
                else:
                    mode = 'pty'
                if mode == 'pty':
                    # Use direct module call to respect patches on kubelingo.sandbox
                    import kubelingo.sandbox as _sb
                    _sb.spawn_pty_shell()
                elif mode in ('docker', 'container'):
                    import kubelingo.sandbox as _sb
                    _sb.launch_container_sandbox()
                else:
                    print(f"Unknown sandbox mode: {mode}")
                return

        # If unified exercise requested, load and list questions
        if args.exercise_module:
            # Load quizzes from the live database only
            from kubelingo.modules.db_loader import DBLoader
            loader = DBLoader()
            questions = []
            for src in loader.discover():
                name = os.path.splitext(os.path.basename(src))[0]
                if name == args.exercise_module:
                    questions.extend(loader.load_file(src))
            if not questions:
                print(f"No questions found for module '{args.exercise_module}'")
            else:
                print(f"Loaded {len(questions)} questions from module '{args.exercise_module}':")
                for q in questions:
                    print(f"  [{q.id}] {q.prompt} (runner={q.runner})")
            return

        # Handle --k8s shortcut
        if args.k8s_mode:
            args.module = 'kubernetes'
            # This flag now acts as a shortcut to the main interactive quiz menu,
            # which is handled by the module's session runner.
            # The logic will fall through to the module execution block at the end.

        # Global flags handling (note: history and list-modules are handled earlier)
        if args.list_categories:
            print(f"{Fore.YELLOW}Note: Categories are based on the loaded quiz data file.{Style.RESET_ALL}")
            try:
                from kubelingo.database import get_questions_by_source_file
                # Ensure a quiz file is specified before listing categories
                if not args.file:
                    print(f"{Fore.YELLOW}No quiz file specified; cannot list categories.{Style.RESET_ALL}")
                    return
                key = os.path.basename(args.file)
                questions = get_questions_by_source_file(key)
                cats = sorted({q.get('category') for q in questions if q.get('category')})
                print(f"{Fore.CYAN}Available Categories:{Style.RESET_ALL}")
                if cats:
                    for cat in cats:
                        print(Fore.YELLOW + cat + Style.RESET_ALL)
                else:
                    print("No categories found in quiz data.")
            except Exception as e:
                print(f"{Fore.RED}Error loading quiz data from {args.file}: {e}{Style.RESET_ALL}")
            return

        # If certain flags are used without a module, default to kubernetes
        if args.module is None and (
            args.file is not None or args.num != 0 or args.category or args.review_only
        ):
            args.module = 'kubernetes'


    # Handle module-based execution.
    if args.module:
        module_name = args.module.lower()

        if module_name == 'kustom':
            module_name = 'custom'

        # 'llm' is not a standalone module from the CLI, but an in-quiz helper.
        if module_name == 'llm':
            print(f"{Fore.RED}The 'llm' feature is available as a command during a quiz, not as a standalone module.{Style.RESET_ALL}")
            return

        # Prepare logging for other modules
        logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')
        logger = logging.getLogger()

        if module_name == 'custom':
            if not args.custom_file and not args.exercises:
                print(Fore.RED + "For the 'kustom' module, you must provide a quiz file with --custom-file or --exercises." + Style.RESET_ALL)
                return
        # Load and run the specified module's session
        try:
            session = load_session(module_name, logger)
            if session:
                init_ok = session.initialize()
                if not init_ok:
                    print(Fore.RED + f"Module '{module_name}' initialization failed. Exiting." + Style.RESET_ALL)
                    return
                session.run_exercises(args)
                session.cleanup()
            else:
                print(Fore.RED + f"Failed to load module '{module_name}'." + Style.RESET_ALL)
        except (ImportError, AttributeError) as e:
            print(Fore.RED + f"Error loading module '{module_name}': {e}" + Style.RESET_ALL)
        return

    # If no other action was taken, just exit.
    if not args.module:
        return
if __name__ == '__main__':
    main()
