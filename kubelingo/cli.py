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
from kubelingo.modules.kubernetes.session import (
    get_all_flagged_questions,
    NewSession,
)
from kubelingo.modules.kubernetes.study_mode import KubernetesStudyMode
# Unified question-data loaders (question-data/{json,md,yaml})
from kubelingo.modules.json_loader import JSONLoader
from kubelingo.modules.md_loader import MDLoader
from kubelingo.modules.question_generator import AIQuestionGenerator
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.modules.db_loader import DBLoader
from kubelingo.sandbox import spawn_pty_shell, launch_container_sandbox
from kubelingo.utils.ui import (
    Fore, Style, print_banner, humanize_module, show_session_type_help, show_quiz_type_help
)
try:
    import questionary
except ImportError:
    questionary = None
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
    get_api_key,
    save_api_key,
    API_KEY_FILE,
    YAML_QUIZ_DIR,
    YAML_QUIZ_BACKUP_DIR,
    get_cluster_configs,
    save_cluster_configs,
    ENABLED_QUIZZES,
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
    # Filter to only quizzes currently enabled
    enabled = set()
    from kubelingo.utils.config import ENABLED_QUIZZES
    for path in ENABLED_QUIZZES.values():
        enabled.add(os.path.basename(path))
    # Include legacy JSON default if used
    # Filter history entries
    history = [h for h in history if h.get('data_file') in enabled]
    if not history:
        print("No quiz history for current modules.")
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
            key = get_api_key()
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
                if save_api_key(value):
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


def migrate_yaml_to_db():
    """Migrates all questions from YAML files into the database and backs them up."""
    print(f"{Fore.CYAN}Starting migration of YAML questions to database...{Style.RESET_ALL}")

    from kubelingo.database import add_question, get_db_connection
    loader = YAMLLoader()
    yaml_files = loader.discover()
    # If no active YAML quiz files, restore from backup and re-discover
    if not yaml_files and os.path.exists(YAML_QUIZ_BACKUP_DIR) and os.listdir(YAML_QUIZ_BACKUP_DIR):
        print(f"{Fore.CYAN}No active YAML quiz files found; restoring from backup...{Style.RESET_ALL}")
        restore_yaml_from_backup()
        yaml_files = loader.discover()

    if not yaml_files:
        print(f"{Fore.YELLOW}No YAML quiz files found to migrate in '{YAML_QUIZ_DIR}'.{Style.RESET_ALL}")
        return

    os.makedirs(YAML_QUIZ_BACKUP_DIR, exist_ok=True)

    conn = get_db_connection()
    if not conn:
        print(f"{Fore.RED}Failed to get database connection.{Style.RESET_ALL}")
        return

    total_migrated = 0
    total_files = 0
    for file_path in yaml_files:
        filename = os.path.basename(file_path)
        print(f"  - Processing '{filename}'...")
        try:
            questions = loader.load_file(file_path)
            if not questions:
                print(f"    {Fore.YELLOW}No questions found in file, skipping.{Style.RESET_ALL}")
                continue

            for q_obj in questions:
                q_dict = asdict(q_obj)
                category = None
                # Handle both list of categories and single category string
                cats = q_dict.get('categories')
                if cats and isinstance(cats, list) and cats:
                    category = cats[0]
                elif q_dict.get('category'):
                    category = q_dict.get('category')

                # add_question will insert or update based on ID
                add_question(
                    conn,
                    id=q_dict['id'],
                    prompt=q_dict['prompt'],
                    source_file=filename,
                    response=q_dict.get('response'),
                    category=category,
                    source=q_dict.get('source'),
                    validation_steps=q_dict.get('validation_steps'),
                    validator=q_dict.get('validator'),
                    review=q_dict.get('review', False)
                )
            conn.commit()
            total_migrated += len(questions)
            total_files += 1
            print(f"    {Fore.GREEN}Migrated {len(questions)} questions.{Style.RESET_ALL}")

            # Move file to backup
            backup_path = os.path.join(YAML_QUIZ_BACKUP_DIR, filename)
            shutil.move(file_path, backup_path)
            print(f"    {Fore.CYAN}Backed up '{filename}' to '{YAML_QUIZ_BACKUP_DIR}'.{Style.RESET_ALL}")

        except Exception as e:
            print(f"    {Fore.RED}Failed to process '{filename}': {e}{Style.RESET_ALL}")

    conn.close()
    print(f"\n{Fore.GREEN}Migration complete. Migrated {total_migrated} questions from {total_files} files.{Style.RESET_ALL}")
    # Backup the live database after migration
    try:
        from kubelingo.database import DATABASE_FILE
        from kubelingo.utils.config import BACKUP_DATABASE_FILE
        os.makedirs(os.path.dirname(BACKUP_DATABASE_FILE), exist_ok=True)
        shutil.copy2(DATABASE_FILE, BACKUP_DATABASE_FILE)
        print(f"{Fore.CYAN}Database backup created at {BACKUP_DATABASE_FILE}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Failed to backup database: {e}{Style.RESET_ALL}")


def restore_yaml_from_backup():
    """Restores YAML files from the backup directory to the active quiz directory."""
    if not os.path.exists(YAML_QUIZ_BACKUP_DIR):
        print(f"{Fore.YELLOW}Backup directory '{YAML_QUIZ_BACKUP_DIR}' not found. Nothing to restore.{Style.RESET_ALL}")
        return

    if not os.listdir(YAML_QUIZ_BACKUP_DIR):
        print(f"{Fore.YELLOW}Backup directory is empty. Nothing to restore.{Style.RESET_ALL}")
        return

    print(f"{Fore.CYAN}Restoring YAML files from backup...{Style.RESET_ALL}")
    os.makedirs(YAML_QUIZ_DIR, exist_ok=True)
    
    restored_count = 0
    for filename in os.listdir(YAML_QUIZ_BACKUP_DIR):
        backup_path = os.path.join(YAML_QUIZ_BACKUP_DIR, filename)
        if os.path.isfile(backup_path) and filename.endswith(('.yaml', '.yml')):
            dest_path = os.path.join(YAML_QUIZ_DIR, filename)
            print(f"  - Restoring '{filename}'...")
            shutil.move(backup_path, dest_path)
            restored_count += 1
    
    print(f"\n{Fore.GREEN}Restore complete. Restored {restored_count} files to '{YAML_QUIZ_DIR}'.{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}You should now run 'kubelingo migrate-yaml' to load these questions into the database.{Style.RESET_ALL}")


def import_json_to_db():
    """Imports questions from JSON files into the database."""
    print(f"{Fore.CYAN}Starting import of JSON questions into the database...{Style.RESET_ALL}")

    from kubelingo.database import add_question, get_db_connection
    from kubelingo.modules.json_loader import JSONLoader
    loader = JSONLoader()
    json_files = loader.discover()

    if not json_files:
        print(f"{Fore.YELLOW}No JSON quiz files found in 'question-data/json' to import.{Style.RESET_ALL}")
        return

    conn = get_db_connection()
    if not conn:
        print(f"{Fore.RED}Failed to get database connection.{Style.RESET_ALL}")
        return

    total_imported = 0
    total_files = 0
    for file_path in json_files:
        filename = os.path.basename(file_path)
        print(f"  - Processing '{filename}'...")
        try:
            questions = loader.load_file(file_path)
            if not questions:
                print(f"    {Fore.YELLOW}No questions found, skipping.{Style.RESET_ALL}")
                continue

            for q_obj in questions:
                q_dict = asdict(q_obj)
                category = None
                cats = q_dict.get('categories')
                if cats and isinstance(cats, list) and cats:
                    category = cats[0]
                elif q_dict.get('category'):
                    category = q_dict.get('category')

                add_question(
                    conn,
                    id=q_dict['id'],
                    prompt=q_dict['prompt'],
                    source_file=filename,
                    response=q_dict.get('response'),
                    category=category,
                    source=q_dict.get('source'),
                    validation_steps=q_dict.get('validation_steps'),
                    validator=q_dict.get('validator'),
                    review=q_dict.get('review', False)
                )
            conn.commit()
            total_imported += len(questions)
            total_files += 1
            print(f"    {Fore.GREEN}Imported {len(questions)} questions.{Style.RESET_ALL}")

        except Exception as e:
            print(f"    {Fore.RED}Failed to process '{filename}': {e}{Style.RESET_ALL}")

    conn.close()
    print(f"\n{Fore.GREEN}Import complete. Imported {total_imported} questions from {total_files} files.{Style.RESET_ALL}")

    # Backup the database after import
    try:
        from kubelingo.database import DATABASE_FILE
        from kubelingo.utils.config import BACKUP_DATABASE_FILE
        if os.path.exists(DATABASE_FILE):
            os.makedirs(os.path.dirname(BACKUP_DATABASE_FILE), exist_ok=True)
            shutil.copy2(DATABASE_FILE, BACKUP_DATABASE_FILE)
            print(f"{Fore.CYAN}Database backup created at {BACKUP_DATABASE_FILE}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Failed to backup database: {e}{Style.RESET_ALL}")


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
                questionary.Separator("Data Management"),
                {"name": "Import JSON quizzes into database", "value": "import_json"},
                questionary.Separator(),
                {"name": "Cancel", "value": "cancel"}
            ],
            use_indicator=True
        ).ask()

        if action is None or action == "cancel":
            print("Operation cancelled.")
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
        elif action == 'import_json':
            import_json_to_db()

        # Add a newline for better spacing after the operation
        print()

    except (KeyboardInterrupt, EOFError):
        print(f"\n{Fore.YELLOW}Operation cancelled.{Style.RESET_ALL}")


def enrich_sources():
    """Finds and adds sources for questions without them."""
    # Check for API key first
    api_key = os.getenv('OPENAI_API_KEY') or get_api_key()
    if not api_key:
        print(f"{Fore.RED}This feature requires an OpenAI API key. Please configure it first.{Style.RESET_ALL}")
        manage_config_interactive()
        api_key = os.getenv('OPENAI_API_KEY') or get_api_key()
        if not api_key:
            return

    from kubelingo.database import get_questions_by_source_file, add_question, get_db_connection
    from kubelingo.utils.config import ENABLED_QUIZZES
    from kubelingo.modules.ai_evaluator import AIEvaluator

    print(f"{Fore.CYAN}Starting source enrichment for all enabled quizzes...{Style.RESET_ALL}")
    evaluator = AIEvaluator()

    all_questions = []
    for name, path in ENABLED_QUIZZES.items():
        source_file = os.path.basename(path)
        questions_from_db = get_questions_by_source_file(source_file)
        print(f"Loaded {len(questions_from_db)} questions from '{name}'")
        all_questions.extend(questions_from_db)

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
        api_key = get_api_key()
        if api_key:
            os.environ['OPENAI_API_KEY'] = api_key
        elif not is_help_request and not is_config_command and sys.stdin.isatty():
            try:
                prompt = getpass.getpass('Enter your OpenAI API key to enable AI features (leave blank to skip): ')
                if prompt:
                    if save_api_key(prompt):
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
                        help="Command to run (e.g. 'kubernetes', 'sandbox pty', 'config', 'enrich-sources', 'migrate-yaml', 'restore-yaml', 'import-json')")
    parser.add_argument('--list-modules', action='store_true',
                        help='List available exercise modules and exit')
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
        # Ensure database is seeded: if no backup DB exists, migrate source files into DB
        from kubelingo.utils.config import BACKUP_DATABASE_FILE, DATABASE_FILE
        if not os.path.exists(BACKUP_DATABASE_FILE):
            print(f"{Fore.CYAN}Seeding questions database from source files...{Style.RESET_ALL}")
            try:
                from kubelingo.database import init_db, add_question
                from kubelingo.modules.json_loader import JSONLoader
                from kubelingo.modules.yaml_loader import YAMLLoader
                from kubelingo.modules.md_loader import MDLoader
                from dataclasses import asdict
                init_db(clear=True)
                # Migrate JSON, YAML, and Markdown quizzes
                for loader in (JSONLoader(), YAMLLoader(), MDLoader()):
                    for file_path in loader.discover():
                        try:
                            questions = loader.load_file(file_path)
                        except Exception:
                            continue
                        source_file = os.path.basename(file_path)
                        for q in questions:
                            steps = []
                            if hasattr(q, 'validation_steps'):
                                for step in q.validation_steps or []:
                                    steps.append(asdict(step))
                            validator = getattr(q, 'validator', None)
                            add_question(
                                id=q.id,
                                prompt=q.prompt,
                                source_file=source_file,
                                response=getattr(q, 'response', None),
                                category=(q.categories[0] if getattr(q, 'categories', None) else None),
                                source=getattr(q, 'source', None),
                                validation_steps=steps,
                                validator=validator,
                                review=getattr(q, 'review', False),
                                explanation=getattr(q, 'explanation', None),
                            )
                # Create backup of newly seeded DB
                os.makedirs(os.path.dirname(BACKUP_DATABASE_FILE), exist_ok=True)
                shutil.copy2(DATABASE_FILE, BACKUP_DATABASE_FILE)
            except Exception as e:
                logger.warning(f"Automatic DB migration failed: {e}")

        try:
                while True:
                    from kubelingo.utils.config import ENABLED_QUIZZES
                    choices = []
                    # List available Kubernetes quizzes without counts
                    for name, path in ENABLED_QUIZZES.items():
                        choices.append({"name": name, "value": path})

                choices.append(questionary.Separator())
                # Flagged questions
                flagged = get_all_flagged_questions()
                if flagged:
                    choices.append({"name": f"Review {len(flagged)} Flagged Questions", "value": "review_flagged"})
                # Study mode
                choices.append({"name": "Study Mode (Socratic Tutor)", "value": "study_mode"})
                choices.append(questionary.Separator())
                choices.append({"name": "Manage Configuration", "value": "config"})
                choices.append({"name": "View Session History", "value": "history"})
                choices.append({"name": "Help", "value": "help"})
                choices.append({"name": "Exit App", "value": "exit_app"})

                action = questionary.select(
                    "Choose a Kubernetes exercise:",
                    choices=choices,
                    use_indicator=True
                ).ask()

                if action is None or action == 'exit_app':
                    print(f"{Fore.YELLOW}Exiting app. Goodbye!{Style.RESET_ALL}")
                    break
                elif action == "history":
                    show_history()
                elif action == "help":
                    show_quiz_type_help()
                elif action == "config":
                    manage_config_interactive()
                elif action == 'review_flagged':
                    current_args = argparse.Namespace(**vars(args))
                    current_args.review_only = True
                    session.run_exercises(current_args)
                elif action == 'study_mode':
                    api_key = os.getenv('OPENAI_API_KEY') or get_api_key()
                    if not api_key:
                        print(f"{Fore.RED}Study Mode requires an OpenAI API key.{Style.RESET_ALL}")
                        manage_config_interactive()
                        continue
                    study_session = KubernetesStudyMode(api_key=api_key)
                    print(f"{Fore.CYAN}Starting Socratic study session on 'pods'... (Ctrl+C to exit){Style.RESET_ALL}")
                    print(study_session.start_study_session("pods"))
                else:
                    # Any other selection is treated as a quiz (by source file in the DB)
                    current_args = argparse.Namespace(**vars(args))
                    # action may be a path or a basename; set as file identifier for DB lookup
                    current_args.file = action
                    session.run_exercises(current_args)
            session.cleanup()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.YELLOW}Exiting.{Style.RESET_ALL}")
        return
    else:
        # Non-interactive mode
        args = parser.parse_args()
        # If --config flag provided, launch interactive config
        if getattr(args, 'config', False):
            manage_config_interactive()
            return
        # Handle config subcommand: kubelingo config <view|set> openai [KEY]
        if args.command and len(args.command) > 0:
            cmd_name = args.command[0]
            if cmd_name == 'config':
                handle_config_command(args.command)
                return
            elif cmd_name == 'enrich-sources':
                enrich_sources()
                return
            elif cmd_name == 'migrate-yaml':
                migrate_yaml_to_db()
                return
            elif cmd_name == 'restore-yaml':
                restore_yaml_from_backup()
                return
            elif cmd_name == 'import-json':
                import_json_to_db()
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
            from kubelingo.utils.config import ENABLED_QUIZZES
            if args.quiz in ENABLED_QUIZZES:
                args.file = ENABLED_QUIZZES[args.quiz]
            else:
                parser.error(
                    f"Quiz '{args.quiz}' not found. "
                    f"Available quizzes: {', '.join(ENABLED_QUIZZES.keys())}"
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
            # Shortcut to display the main Kubernetes quiz menu and exit
            args.module = 'kubernetes'
            # Only interactive when no other quiz flags are present and in an interactive terminal
            if (
                args.num == 0
                and not args.category
                and not args.review_only
                and not args.list_categories
                and not args.exercise_module
                and questionary
                and sys.stdin.isatty()
                and sys.stdout.isatty()
            ):
                # Configure logging
                logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')
                logger = logging.getLogger()
                # Load session for side-effects (history, flags)
                load_session('kubernetes', logger)
                # Build menu choices from the configured quizzes
                choices = []
                for quiz_name, path in ENABLED_QUIZZES.items():
                    choices.append({"name": quiz_name, "value": path})
                # Add Exit option
                choices.append({"name": "Exit", "value": "exit_app"})
                # Prompt user to select a quiz
                choice = questionary.select(
                    "Choose a Kubernetes quiz module:",
                    choices=choices,
                    use_indicator=True
                ).ask()
                if choice == 'exit_app':
                    return
                # Set the selected module for unified exercise
                args.exercise_module = os.path.splitext(choice)[0]

        # Global flags handling (note: history and list-modules are handled earlier)
        if args.list_categories:
            print(f"{Fore.YELLOW}Note: Categories are based on the loaded quiz data file.{Style.RESET_ALL}")
            try:
                from kubelingo.database import get_questions_by_source_file
                questions = get_questions_by_source_file(os.path.basename(args.file))
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
