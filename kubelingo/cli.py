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

from kubelingo.question import QuestionCategory

# Base session loader
from kubelingo.modules.base.loader import discover_modules, load_session
from kubelingo.modules.base.session import SessionManager
from kubelingo.modules.kubernetes.socratic_mode import SocraticMode
# Unified question-data loaders (question-data/yaml)
from kubelingo.modules.question_generator import AIQuestionGenerator
from kubelingo.integrations.llm import get_llm_client
# from kubelingo.modules.db_loader import DBLoader
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
    get_ai_provider,
    get_active_api_key,
    get_api_key,
    get_api_key_with_source,
    save_api_key,
    QUESTIONS_DIR,
    get_cluster_configs,
    save_cluster_configs,
    SQLITE_BACKUP_DIRS,
    SUPPORTED_AI_PROVIDERS,
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


def handle_config_command(cmd):
    """Handles 'config' subcommands."""
    import getpass
    if len(cmd) < 3:
        print("Usage: kubelingo config <action> <target> [args...]")
        print("Example: kubelingo config set provider")
        print("Example: kubelingo config set openai")
        print("Example: kubelingo config list cluster")
        return

    action = cmd[1].lower()
    target = cmd[2].lower()

    if target == 'provider':
        if action == 'set':
            _setup_ai_provider_interactive(force_setup=True)
        else:
            print(f"Unknown action '{action}' for provider. Use 'set'.")
    elif target in SUPPORTED_AI_PROVIDERS:
        provider = target
        if action == 'view':
            key, source = get_api_key_with_source(provider)
            if key:
                print(f'{provider.capitalize()} API key: {key}')
                if source:
                    print(f"Source: {source}")
            else:
                print(f'{provider.capitalize()} API key is not set.')
        elif action == 'set':
            from kubelingo.integrations.llm import OpenAIClient, GeminiClient
            value = None
            if len(cmd) >= 4:
                value = cmd[3]
            else:
                try:
                    value = getpass.getpass(f'Enter {provider.capitalize()} API key: ').strip()
                except (EOFError, KeyboardInterrupt):
                    print(f"\n{Fore.YELLOW}API key setting cancelled.{Style.RESET_ALL}")
                    return

            if value:
                test_func = OpenAIClient.test_key if provider == 'openai' else GeminiClient.test_key
                print(f"Testing {provider.capitalize()} API key...")
                if test_func(value):
                    if save_api_key(provider, value):
                        print(f"{Fore.GREEN}✓ {provider.capitalize()} API key is valid and has been saved.{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}✗ {provider.capitalize()} API key is valid, but failed to save it.{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}✗ The provided API key appears to be invalid. It has not been saved.{Style.RESET_ALL}")
            else:
                print("No API key provided. No changes made.")
        else:
            print(f"Unknown action '{action}' for {provider}. Use 'view' or 'set'.")
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
        print(f"Unknown config target '{target}'. Supported: provider, openai, gemini, cluster.")


def test_ai_connection():
    """Tests the connection to the configured AI provider."""
    from kubelingo.integrations.llm import get_llm_client
    from kubelingo.utils.config import get_ai_provider

    provider = get_ai_provider()
    if not provider:
        print(f"{Fore.RED}No AI provider configured. Use 'kubelingo config' to set one up.{Style.RESET_ALL}")
        return

    print(f"Testing connection to {provider.capitalize()}...")
    try:
        client = get_llm_client()
        if client.test_connection():
            print(f"{Fore.GREEN}✓ Connection to {provider.capitalize()} successful.{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Connection to {provider.capitalize()} failed. Please check your API key and network connection.{Style.RESET_ALL}")
    except (ValueError, ImportError) as e:
        # Catches no API key, or llm not installed
        print(f"{Fore.RED}✗ Failed to initialize AI client: {e}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}✗ An unexpected error occurred during connection test: {e}{Style.RESET_ALL}")


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
        # Allow user to interrupt script
        print(f"\n{Fore.YELLOW}Script interrupted.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}An error occurred while running the script: {e}{Style.RESET_ALL}")


def _run_bootstrap_script():
    """Runs the database bootstrapping script."""
    script_path = repo_root / "scripts" / "bootstrap_database.py"
    if not script_path.exists():
        print(f"{Fore.RED}Error: Bootstrap script not found at {script_path}{Style.RESET_ALL}")
        print("Please ensure 'scripts/bootstrap_database.py' exists.")
        return

    print(f"\n{Fore.CYAN}--- Running Database Bootstrap Script ---{Style.RESET_ALL}")
    try:
        # We can ask for the source YAML file interactively here, or just use the default.
        # For now, let's just run it with its defaults.
        subprocess.run([sys.executable, str(script_path)], check=True)
        print(f"{Fore.GREEN}--- Bootstrap script finished ---{Style.RESET_ALL}")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"{Fore.RED}Error running bootstrap script: {e}{Style.RESET_ALL}")
    except (KeyboardInterrupt):
        print(f"\n{Fore.YELLOW}Bootstrap script cancelled by user.{Style.RESET_ALL}")


# handle_load_yaml is obsolete and removed. Database is managed by bootstrap_database.py


def _run_bug_ticket_script():
    """Runs the bug_ticket.py script."""
    print("\nLaunching Bug Ticket Reporter...")
    script_path = repo_root / "scripts" / "bug_ticket.py"
    if not script_path.exists():
        print(f"{Fore.RED}Error: Bug ticket script not found at {script_path}{Style.RESET_ALL}")
        return

    try:
        subprocess.run([sys.executable, str(script_path)], check=False)
    except Exception as e:
        print(f"{Fore.RED}Error running bug ticket script: {e}{Style.RESET_ALL}")


def _list_yaml_questions():
    """Lists questions from YAML files."""
    from kubelingo.modules.yaml_loader import YAMLLoader
    from kubelingo.utils.ui import Fore, Style
    import os

    print(f"\n{Fore.CYAN}--- Questions from YAML files ---{Style.RESET_ALL}")
    loader = YAMLLoader()
    try:
        # The discover method should find all relevant YAML files.
        yaml_files = loader.discover()
        if not yaml_files:
            print(f"{Fore.YELLOW}No YAML question files found.{Style.RESET_ALL}")
            return

        print(f"Found {len(yaml_files)} YAML file(s). Loading questions...")
        all_questions = []
        for file_path in yaml_files:
            try:
                questions = loader.load_file(file_path)
                if questions:
                    print(f"\n{Fore.GREEN}File: {os.path.basename(file_path)}{Style.RESET_ALL} ({len(questions)} questions)")
                    for i, q in enumerate(questions):
                        print(f"  {i+1}. [{q.id}] {q.prompt[:100]}")
                all_questions.extend(questions)
            except Exception as e:
                print(f"{Fore.YELLOW}Warning: Could not load or parse {os.path.basename(file_path)}: {e}{Style.RESET_ALL}")

        if not all_questions:
            print(f"{Fore.YELLOW}No questions could be loaded from any YAML files.{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")
    print() # for spacing


def _run_question_management():
    """Shows the question management menu from scripts/question_manager.py."""
    print("\nLaunching Question Management...")
    try:
        # Import dynamically to avoid issues with script-like modules
        from scripts.question_manager import interactive_question_manager_menu
        interactive_question_manager_menu()
        # The called function prints its own exit message.
        print(f"\n{Fore.CYAN}Returning to main menu.{Style.RESET_ALL}")
    except (KeyboardInterrupt, EOFError):
        print(f"\n{Fore.YELLOW}Exiting Question Management.{Style.RESET_ALL}")
    except ImportError as e:
        print(f"{Fore.RED}Could not load question manager: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Please ensure 'scripts/question_manager.py' exists and is runnable.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}An error occurred during question management: {e}{Style.RESET_ALL}")


def _run_drill_mode(study_session, category: QuestionCategory):
    """Runs a quiz drill for a specific question category, with a subject drill-down menu."""
    print(f"\n{Fore.CYAN}Starting drill for '{category.value}' questions...{Style.RESET_ALL}")
    try:
        from kubelingo.database import get_question_counts_by_subject
        from kubelingo.modules.yaml_loader import YAMLLoader
        from kubelingo.database import get_questions_by_filter

        # Special case for Open Ended, which is a Socratic-style session, not a drill.
        if category == QuestionCategory.OPEN_ENDED:
            # Socratic mode needs to be re-evaluated in the new architecture.
            # For now, we can say it's not a drill.
            if hasattr(study_session, '_run_socratic_mode_entry'):
                study_session._run_socratic_mode_entry()
            else:
                print(f"{Fore.YELLOW}Socratic mode is not available in this session type.{Style.RESET_ALL}")
            return

        subject_counts = get_question_counts_by_subject(category.value)
        if not subject_counts:
            print(f"{Fore.YELLOW}No questions found for category '{category.value}'. Returning to main menu.{Style.RESET_ALL}")
            # Here we could offer to generate them
            return

        choices = [questionary.Choice(title="All Subjects", value="all")]
        for subject_id, count in sorted(subject_counts.items()):
            display_name = ' '.join(word.capitalize() for word in subject_id.replace('_', ' ').split('-'))
            choices.append(questionary.Choice(title=f"{display_name} ({count})", value=subject_id))

        choices.extend([Separator(), questionary.Choice(title="Back", value="back")])

        selected_subject = questionary.select(
            f"Select a subject for {category.value}:", choices=choices, use_indicator=True
        ).ask()

        if not selected_subject or selected_subject == "back":
            return

        subject_filter = selected_subject if selected_subject != "all" else None
        
        # 1. Get question metadata from DB
        question_metadatas = get_questions_by_filter(category=category.value, subject=subject_filter)

        if not question_metadatas:
            print(f"{Fore.YELLOW}No questions found for the selected criteria.{Style.RESET_ALL}")
            return
            
        # 2. Load full question content from YAML files
        loader = YAMLLoader()
        questions_to_ask = []
        # Group by source file to minimize file IO
        questions_by_file = {}
        for meta in question_metadatas:
            source_file = meta['source_file']
            if source_file not in questions_by_file:
                questions_by_file[source_file] = []
            questions_by_file[source_file].append(meta['id'])

        project_root = Path(__file__).resolve().parent.parent
        for rel_path, qids in questions_by_file.items():
            full_path = project_root / rel_path
            if full_path.exists():
                all_from_file = loader.load_file(str(full_path))
                questions_to_ask.extend([q for q in all_from_file if q.id in qids])
            else:
                print(f"{Fore.YELLOW}Warning: source file not found: {full_path}{Style.RESET_ALL}")

        if not questions_to_ask:
            print(f"{Fore.RED}Error: Found metadata but could not load question content from YAML.{Style.RESET_ALL}")
            return

        # 3. Pass full Question objects to the session runner
        # We need to adapt run_exercises to take a list of questions directly.
        # Create a mock_args object for compatibility if needed.
        import argparse
        mock_args = argparse.Namespace(
            # Pass the loaded questions via the 'exercises' attribute
            exercises=questions_to_ask,
            # Other flags for the session
            num=0,
            randomize=True,
            ai_eval=hasattr(study_session, 'client') and study_session.client is not None,
            # Legacy/compatibility flags
            file=None,
            category=category.value,
            subject=subject_filter,
            review_only=False,
            k8s_mode=True,
            cluster_context=None
        )
        # Assuming run_exercises will be refactored to check for `args.exercises` first.
        study_session.run_exercises(mock_args)

    except (KeyboardInterrupt, EOFError):
        print() # Newline for clean exit
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred during drill mode: {e}{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}Drill session finished. Returning to main menu.{Style.RESET_ALL}")


def _list_indexed_files():
    """Lists all question files currently indexed in the database."""
    from kubelingo.database import get_indexed_files
    print("\nListing indexed question files from database...")
    try:
        files = get_indexed_files()
        if not files:
            print(f"{Fore.YELLOW}No files have been indexed yet.{Style.RESET_ALL}")
            print("You can run 'Index Question Files' from the menu to populate the database.")
            return

        print(f"{Fore.CYAN}Found {len(files)} indexed files:{Style.RESET_ALL}")
        for f in files:
            print(f"  - {f['file_path']} (last indexed: {f['last_indexed']})")
        print()
    except Exception as e:
        print(f"{Fore.RED}An error occurred while fetching indexed files: {e}{Style.RESET_ALL}")


def manage_cluster_config_interactive():
    """Interactive prompt for managing Kubernetes cluster configurations."""
    if questionary is None:
        print(f"{Fore.RED}`questionary` package not installed. Cannot show interactive menu.{Style.RESET_ALL}")
        return
    try:
        configs = get_cluster_configs()
        menu_choices = [
            questionary.Separator("--- Kubernetes Clusters ---"),
            {"name": "List configured clusters", "value": "list_clusters"},
            {"name": "Add a new cluster connection", "value": "add_cluster"},
        ]
        if configs:
            menu_choices.append({"name": "Remove a cluster connection", "value": "remove_cluster"})
        
        menu_choices.extend([
            questionary.Separator(),
            {"name": "Cancel", "value": "cancel"}
        ])

        action = questionary.select(
            "Select a cluster configuration action:",
            choices=menu_choices,
            use_indicator=True
        ).ask()

        if action is None or action == "cancel":
            return

        if action == 'list_clusters':
            handle_config_command(['config', 'list', 'cluster'])
        elif action == 'add_cluster':
            handle_config_command(['config', 'add', 'cluster'])
        elif action == 'remove_cluster':
            handle_config_command(['config', 'remove', 'cluster'])

        print()

    except (KeyboardInterrupt, EOFError):
        print()
        return


def manage_config_interactive():
    """Interactive prompt for managing AI provider configuration."""
    if questionary is None:
        print(f"{Fore.RED}`questionary` package not installed. Cannot show interactive menu.{Style.RESET_ALL}")
        return
    try:
        provider = get_ai_provider()
        provider_display = f" (current: {provider.capitalize()})" if provider else " (Not Set)"

        menu_choices = [
            {"name": f"Set active AI Provider{provider_display}", "value": "set_provider"},
            questionary.Separator("--- API Keys ---"),
        ]

        for p in SUPPORTED_AI_PROVIDERS:
            key, source = get_api_key_with_source(p)
            status = "Not Set"
            if source:
                status = f"Set (from {source})"

            menu_choices.extend([
                {"name": f"View {p.capitalize()} API Key ({status})", "value": f"view_{p}"},
                {"name": f"Set/Update {p.capitalize()} API Key", "value": f"set_{p}"},
            ])

        menu_choices.extend([
            questionary.Separator(),
            {"name": "Cancel", "value": "cancel"}
        ])

        action = questionary.select(
            "Select an AI provider configuration action:",
            choices=menu_choices,
            use_indicator=True
        ).ask()

        if action is None or action == "cancel":
            return

        if action == 'set_provider':
            # Run the full interactive setup flow
            _setup_ai_provider_interactive(force_setup=True)
        elif action.startswith('view_'):
            p = action.split('_')[1]
            handle_config_command(['config', 'view', p])
        elif action.startswith('set_'):
            p = action.split('_')[1]
            handle_config_command(['config', 'set', p])

        # Add a newline for better spacing after the operation
        print()

    except (KeyboardInterrupt, EOFError):
        # A newline is needed to prevent the next prompt from appearing on the same line.
        print()
        return





def _setup_ai_provider_interactive(force_setup=False):
    """
    Interactive prompt for setting up AI provider and API keys.
    If force_setup is False, it only prompts if settings are missing.
    """
    if not questionary:
        return

    from kubelingo.utils.config import get_ai_provider, save_ai_provider, get_api_key, save_api_key
    from kubelingo.integrations.llm import OpenAIClient, GeminiClient
    import getpass

    provider = get_ai_provider()
    # Ask for provider if not set or if forcing setup
    if not provider or force_setup:
        provider_choices = [{"name": p.capitalize(), "value": p} for p in SUPPORTED_AI_PROVIDERS]
        # Ensure the default value is valid, otherwise questionary crashes.
        default_provider = provider if provider in SUPPORTED_AI_PROVIDERS else None

        new_provider = questionary.select(
            "--- AI Provider ---\nPlease select an AI provider for feedback and study features:",
            choices=provider_choices,
            default=default_provider,
            use_indicator=True,
        ).ask()

        if not new_provider:
            if force_setup: print(f"{Fore.YELLOW}No provider selected. No changes made.{Style.RESET_ALL}")
            return  # Exit if user cancels provider selection
        provider = new_provider
        save_ai_provider(provider)
        print(f"AI provider set to {provider.capitalize()}.")

    # Ask for API key if a provider is set, but the key is missing.
    # Also asks if `force_setup` is True, allowing key to be overwritten.
    if provider and (not get_api_key(provider) or force_setup):
        # When forcing, check if a key exists and ask for overwrite confirmation.
        if force_setup and get_api_key(provider):
            if not questionary.confirm(f"API key for {provider.capitalize()} is already set. Overwrite?").ask():
                return
        elif not get_api_key(provider):
            # On first-time setup, print a helpful message.
            print(f"\nAn API key for {provider.capitalize()} is required to enable AI features.")

        try:
            key_value = getpass.getpass(f"Enter your {provider.capitalize()} API key: ").strip()
            if key_value:
                test_func = OpenAIClient.test_key if provider == 'openai' else GeminiClient.test_key
                if test_func(key_value):
                    if save_api_key(provider, key_value):
                        print(f"{Fore.GREEN}✓ API key is valid and has been saved.{Style.RESET_ALL}\n")
                    else:
                        print(f"{Fore.RED}✗ API key is valid, but failed to save it.{Style.RESET_ALL}\n")
                else:
                    print(f"{Fore.RED}✗ The provided API key appears to be invalid. It has not been saved.{Style.RESET_ALL}\n")
            else:
                if force_setup: print(f"{Fore.YELLOW}No key provided. No changes made.{Style.RESET_ALL}\n")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.YELLOW}API key entry cancelled.{Style.RESET_ALL}\n")


def _run_yaml_quiz_interactive(study_session):
    """Interactive prompt to select and run a quiz from a YAML file."""
    from kubelingo.modules.yaml_loader import YAMLLoader
    from kubelingo.utils.ui import humanize_module
    import argparse

    if questionary is None:
        print(f"{Fore.RED}`questionary` package not installed. Cannot show interactive menu.{Style.RESET_ALL}")
        return

    loader = YAMLLoader()
    try:
        # discover() searches default paths, which includes 'yaml/'
        files = loader.discover()
    except Exception as e:
        print(f"{Fore.RED}Error discovering YAML files: {e}{Style.RESET_ALL}")
        return

    if not files:
        print(f"{Fore.YELLOW}No YAML quiz files found.{Style.RESET_ALL}")
        return

    choices = []
    for f in files:
        name = humanize_module(os.path.splitext(os.path.basename(f))[0])
        choices.append(questionary.Choice(title=name, value=f))

    choices.extend([Separator(), {"name": "Cancel", "value": None}])

    yaml_file = questionary.select(
        "Select a YAML quiz to run:",
        choices=choices
    ).ask()

    if not yaml_file:
        return

    # The SocraticMode session's run_exercises method expects a list of Question objects.
    print(f"\n{Fore.CYAN}Starting quiz from '{os.path.basename(yaml_file)}'...{Style.RESET_ALL}")
    try:
        # Load the questions from the selected YAML file.
        questions = loader.load_file(yaml_file)
        if not questions:
            print(f"{Fore.YELLOW}No questions found in '{os.path.basename(yaml_file)}'.{Style.RESET_ALL}")
            return

        # Now pass the loaded list of questions to the session runner.
        study_session.run_exercises(questions)
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred during the quiz: {e}{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}Quiz session finished. Returning to main menu.{Style.RESET_ALL}")


def _run_socratic_mode(study_session: SocraticMode):
    """Runs an interactive Socratic study session."""
    try:
        # Delegate to the study session manager to handle the Socratic mode flow.
        study_session._run_socratic_mode_entry()
    except (KeyboardInterrupt, EOFError):
        print(f"\n\n{Fore.CYAN}Socratic session ended. Returning to main menu.{Style.RESET_ALL}")


def run_interactive_main_menu():
    """Displays the main interactive menu for the application."""
    if not (questionary and Separator):
        print(f"{Fore.RED}Error: 'questionary' library not found. Please install it with 'pip install questionary'.{Style.RESET_ALL}")
        return

    study_session = SocraticMode()

    while True:
        try:
            # Re-check client in loop in case API key is set during session
            api_key = get_active_api_key()
            if api_key:
                if not study_session.client:
                    try:
                        study_session.client = get_llm_client()
                    except (ValueError, ImportError):
                        study_session.client = None
            else:
                study_session.client = None  # Ensure client is None if no key

            has_api_key = bool(study_session.client)
            api_key_required_msg = "API Key Required"

            # --- Get counts for menu ---
            try:
                from kubelingo.database import get_flagged_questions, get_question_counts_by_category
                missed_count = len(get_flagged_questions())
                question_counts = get_question_counts_by_category()
            except Exception:
                missed_count = 'N/A'
                question_counts = {cat.value: 'N/A' for cat in QuestionCategory}


            # --- Build Menu Choices ---
            choices = [
                Separator("--- Learn ---"),
                questionary.Choice(
                    "Socratic Mode",
                    value=("learn", "study"),
                    disabled=api_key_required_msg if not has_api_key else "",
                ),
                questionary.Choice(
                    f"Missed Questions ({missed_count})",
                    value=("learn", "review"),
                    disabled=(api_key_required_msg if not has_api_key
                              else "No questions to review" if missed_count == 0
                              else ""),
                ),
                questionary.Choice("Run Quiz from YAML file", value=("learn", "yaml_quiz")),
                Separator("--- Drill ---"),
                questionary.Choice(
                    f"Open Ended Questions ({question_counts.get(QuestionCategory.OPEN_ENDED.value, 0)})",
                    value=("drill", QuestionCategory.OPEN_ENDED),
                    disabled=api_key_required_msg if not has_api_key else "",
                ),
                questionary.Choice(
                    f"Basic Terminology ({question_counts.get(QuestionCategory.BASIC_TERMINOLOGY.value, 0)})",
                    value=("drill", QuestionCategory.BASIC_TERMINOLOGY)
                ),
                questionary.Choice(
                    f"Command Syntax ({question_counts.get(QuestionCategory.COMMAND_SYNTAX.value, 0)})",
                    value=("drill", QuestionCategory.COMMAND_SYNTAX),
                    disabled=api_key_required_msg if not has_api_key else "",
                ),
                questionary.Choice(
                    f"YAML Manifest ({question_counts.get(QuestionCategory.YAML_MANIFEST.value, 0)})",
                    value=("drill", QuestionCategory.YAML_MANIFEST)
                ),
                Separator("--- Settings & Data ---"),
                questionary.Choice("AI Provider & Keys", value=("settings", "ai")),
                questionary.Choice("Kubernetes Clusters", value=("settings", "cluster")),
                questionary.Choice("Question Management", value=("settings", "questions")),
                questionary.Choice("Bootstrap/Rebuild Database", value=("data", "bootstrap")),
                questionary.Choice("Help", value=("settings", "help")),
                questionary.Choice("Report Bug", value=("settings", "bug")),
                Separator(),
                questionary.Choice("Exit App", value="exit"),
            ]

            choice = questionary.select(
                "Kubelingo Main Menu", choices=choices, use_indicator=True
            ).ask()

            if choice is None or choice == "exit":
                print("Exiting application. Goodbye!")
                break

            menu, action = choice

            if menu == "learn":
                if action == "study":
                    _run_socratic_mode(study_session)
                elif action == "review":
                    study_session.review_past_questions()
                elif action == "yaml_quiz":
                    _run_yaml_quiz_interactive(study_session)
            elif menu == "drill":
                # This should launch a drill-down quiz for the selected category.
                _run_drill_mode(study_session, action)
            elif menu == "data":
                if action == "bootstrap":
                    _rebuild_db_from_yaml()
            elif menu == "settings":
                if action == "ai":
                    manage_config_interactive()
                elif action == "cluster":
                    manage_cluster_config_interactive()
                elif action == "questions":
                    _run_question_management()
                elif action == "view_yaml":
                    _list_yaml_questions()
                elif action == "help":
                    show_session_type_help()
                elif action == "bug":
                    _run_bug_ticket_script()

        except (KeyboardInterrupt, TypeError, EOFError):
            print("\nExiting application. Goodbye!")
            break


def enrich_sources():
    """Finds and adds sources for questions without them by loading content from YAML files."""
    # Check for API key first
    api_key = get_active_api_key()
    if not api_key:
        provider = get_ai_provider()
        print(f"{Fore.RED}This feature requires a {provider.capitalize()} API key. Please configure it first.{Style.RESET_ALL}")
        manage_config_interactive()
        api_key = get_active_api_key()
        if not api_key:
            return

    from kubelingo.database import get_all_questions, get_db_connection
    from kubelingo.modules.ai_evaluator import AIEvaluator
    from kubelingo.modules.yaml_loader import YAMLLoader
    from kubelingo.utils.path_utils import get_all_yaml_files_in_repo

    print(f"{Fore.CYAN}Starting source enrichment for all questions in the database...{Style.RESET_ALL}")
    evaluator = AIEvaluator()
    loader = YAMLLoader()
    all_yaml_files = {f.name: f for f in get_all_yaml_files_in_repo()}

    all_questions_meta = get_all_questions()
    questions_to_update_meta = [q for q in all_questions_meta if not q.get('source')]

    if not questions_to_update_meta:
        print(f"{Fore.GREEN}All questions already have sources. Nothing to do.{Style.RESET_ALL}")
        return

    print(f"\nFound {Fore.YELLOW}{len(questions_to_update_meta)}{Style.RESET_ALL} questions without a source. Loading from YAML and enriching...\n")

    conn = get_db_connection()
    if not conn:
        print(f"{Fore.RED}Failed to get database connection.{Style.RESET_ALL}")
        return

    updated_count = 0
    failed_count = 0
    # Group by file to load each YAML only once
    questions_by_file = {}
    for q_meta in questions_to_update_meta:
        source_file = q_meta.get('source_file')
        if source_file not in questions_by_file:
            questions_by_file[source_file] = []
        questions_by_file[source_file].append(q_meta['id'])

    for source_file, q_ids in questions_by_file.items():
        if source_file not in all_yaml_files:
            print(f"    {Fore.YELLOW}Warning: Could not find source file '{source_file}' for {len(q_ids)} questions. Skipping.{Style.RESET_ALL}")
            failed_count += len(q_ids)
            continue

        try:
            questions_in_file = {q.id: q for q in loader.load_file(str(all_yaml_files[source_file]))}
        except Exception as e:
            print(f"    {Fore.RED}Error loading {source_file}: {e}{Style.RESET_ALL}")
            failed_count += len(q_ids)
            continue

        for q_id in q_ids:
            if q_id not in questions_in_file:
                failed_count += 1
                continue
            
            q = questions_in_file[q_id]
            print(f"  - Processing question ID {q.id}: '{q.prompt[:60].strip()}...'")
            source_url = evaluator.find_source_for_question(q.prompt)
            if source_url:
                print(f"    {Fore.GREEN}-> Found source: {source_url}{Style.RESET_ALL}")
                try:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE questions SET source = ? WHERE id = ?", (source_url, q_id))
                    conn.commit()
                    updated_count += 1
                except Exception as e:
                    print(f"    {Fore.RED}-> Failed to update question {q_id} in DB: {e}{Style.RESET_ALL}")
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
    # Initialize logging for both interactive and non-interactive modes
    import logging
    log_level = os.getenv('KUBELINGO_LOG_LEVEL', 'INFO').upper()
    numeric_level = getattr(logging, log_level, logging.INFO)
    logging.basicConfig(
        filename=LOGS_DIR + '/quiz_kubernetes_log.txt',
        level=numeric_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    # Silence verbose HTTP logs from the httpx library (used by llm)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # --- Interactive Mode: AI Provider and API Key Setup ---
    is_interactive = (len(sys.argv) == 1) and sys.stdout.isatty() and sys.stdin.isatty()
    if is_interactive:
        # On first run (or if config is missing), this will prompt for setup.
        # It's non-intrusive if everything is already configured.
        _setup_ai_provider_interactive(force_setup=False)

    # The application no longer performs any startup bootstrapping.
    # The database is expected to be created by the user via the bootstrap script.
    # `get_db_connection` will handle cases where the DB is missing.

    # --- Interactive Mode: AI Provider and API Key Setup ---
    # The initial provider setup is now handled by initialize_app().

    # Support 'kubelingo sandbox [pty|docker]' as subcommand syntax
    if len(sys.argv) >= 3 and sys.argv[1] == 'sandbox' and sys.argv[2] in ('pty', 'docker'):
        # rewrite to explicit sandbox-mode flag
        sys.argv = [sys.argv[0], sys.argv[1], '--sandbox-mode', sys.argv[2]] + sys.argv[3:]
    # Only display banner when running interactively (not help or piped output)
    if is_interactive and '--help' not in sys.argv and '-h' not in sys.argv:
        print_banner()
        print()
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
                        help="Command to run (e.g. 'study', 'kubernetes', 'sandbox pty', 'config', 'questions', 'bootstrap-db', 'enrich-sources', 'monitor', 'self-heal', 'heal', 'test-ai')")
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
    if len(sys.argv) == 1:
        run_interactive_main_menu()
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
                run_interactive_main_menu()
                return
            elif cmd_name == 'config':
                handle_config_command(args.command)
                return
            elif cmd_name == 'test-ai':
                test_ai_connection()
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
                print(f"{Fore.YELLOW}The 'load-yaml' command is obsolete. Use the 'Bootstrap/Rebuild Database' menu option or 'bootstrap-db' command.{Style.RESET_ALL}")
                return
            elif cmd_name == 'questions':
                _run_question_management()
                return
            elif cmd_name == 'bootstrap-db':
                _rebuild_db_from_yaml()
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
            generator = AIQuestionGenerator(llm_client=get_llm_client())
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
            generator = AIQuestionGenerator(llm_client=get_llm_client())
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
            # Dynamically discover available quiz modules from YAML files for --quiz
            try:
                from kubelingo.modules.yaml_loader import YAMLLoader
                from kubelingo.utils.ui import humanize_module
                loader = YAMLLoader()
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
        # Early flags: history
        if args.history:
            show_history()
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
            # Load quizzes from YAML files
            from kubelingo.modules.yaml_loader import YAMLLoader
            loader = YAMLLoader()
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

        # Global flags handling (note: history is handled earlier)
        if args.list_categories:
            print(f"{Fore.YELLOW}Note: Categories are based on the loaded quiz data file.{Style.RESET_ALL}")
            try:
                from kubelingo.modules.yaml_loader import YAMLLoader
                # Ensure a quiz file is specified before listing categories
                if not args.file:
                    print(f"{Fore.YELLOW}No quiz file specified; cannot list categories.{Style.RESET_ALL}")
                    return

                loader = YAMLLoader()
                questions = loader.load_file(args.file)
                cats = sorted({q.category for q in questions if q.category})

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
