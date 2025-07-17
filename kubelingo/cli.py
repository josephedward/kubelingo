#!/usr/bin/env python3
"""
cli_quiz.py: A simple CLI tool to quiz commands (or other strings) based on supplied JSON data.
"""
import json
import random
import argparse
import sys
import datetime
import tempfile
# OS utilities
import os
import shutil
import subprocess
import logging
import shlex
from kubelingo.modules.base.loader import discover_modules, load_session

# Interactive prompts library (optional for arrow-key selection)
try:
    import questionary
except ImportError:
    questionary = None

try:
    import yaml
except ImportError:
    yaml = None

from kubelingo.modules.base.loader import discover_modules, load_session
try:
    from kubelingo.modules.vim_yaml_editor import VimYamlEditor, vim_commands_quiz
except ImportError:
    VimYamlEditor = None
    vim_commands_quiz = None

# Colored terminal output (ANSI codes)
class _AnsiFore:
    CYAN = '\033[36m'
    MAGENTA = '\033[35m'
    YELLOW = '\033[33m'
    GREEN = '\033[32m'
    RED = '\033[31m'
class _AnsiStyle:
    RESET_ALL = '\033[0m'
Fore = _AnsiFore()
Style = _AnsiStyle()

ASCII_ART = r"""
K   K U   U  BBBB  EEEEE L     III N   N  GGGG   OOO 
K  K  U   U  B   B E     L      I  NN  N G   G O   O
KK    U   U  BBBB  EEEE  L      I  N N N G  GG O   O
K  K  U   U  B   B E     L      I  N  NN G   G O   O
K   K  UUU   BBBB  EEEEE LLLLL III N   N  GGGG   OOO 
"""

# Function to print the ASCII banner with a border
def print_banner():
    lines = ASCII_ART.strip('\n').splitlines()
    width = max(len(line) for line in lines)
    border = '+' + '-'*(width + 2) + '+'
    print(Fore.MAGENTA + border + Style.RESET_ALL)
    for line in lines:
        print(Fore.MAGENTA + f"| {line.ljust(width)} |" + Style.RESET_ALL)
    print(Fore.MAGENTA + border + Style.RESET_ALL)

# Quiz data directory (project root 'data/' directory)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DATA_DIR = os.path.join(ROOT, 'data')
DEFAULT_DATA_FILE = os.path.join(DATA_DIR, 'ckad_quiz_data.json')
# History file for storing past quiz performance
HISTORY_FILE = os.path.join(os.path.expanduser('~'), '.cli_quiz_history.json')

def show_history():
    """Display quiz history and aggregated statistics."""
    if not os.path.exists(HISTORY_FILE):
        print(f"No quiz history found ({HISTORY_FILE}).")
        return
    try:
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
    except Exception as e:
        print(f"Error reading history file {HISTORY_FILE}: {e}")
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





def run_interactive_yaml_menu():
    """Shows the menu for different interactive YAML exercise types."""
    if not VimYamlEditor or not questionary:
        print(f"{Fore.RED}This feature requires the 'questionary' library and the VimYamlEditor module.{Style.RESET_ALL}")
        return

    try:
        modes = [
            "Standard Exercises",
            "Progressive Scenarios",
            "Live Cluster Exercises",
            "Create Custom Exercise",
            "Vim Commands Quiz",
            questionary.Separator(),
            "Back to Main Menu"
        ]

        action = questionary.select(
            "Choose an Interactive YAML exercise type:",
            choices=modes,
            use_indicator=True
        ).ask()

        if action is None or action == "Back to Main Menu":
            print("Returning to main menu.")
            return

        editor = VimYamlEditor()
        if action == "Standard Exercises":
            run_yaml_editing_mode(YAML_QUESTIONS_FILE)
        elif action == "Progressive Scenarios":
            file_path = input("Enter path to progressive scenarios JSON file: ").strip()
            if not file_path: return
            try:
                with open(file_path, 'r') as f:
                    exercises = json.load(f)
                editor.run_progressive_yaml_exercises(exercises)
            except Exception as e:
                print(f"Error loading exercises file {file_path}: {e}")
        elif action == "Live Cluster Exercises":
            file_path = input("Enter path to live cluster exercise JSON file: ").strip()
            if not file_path: return
            try:
                with open(file_path, 'r') as f:
                    exercise = json.load(f)
                editor.run_live_cluster_exercise(exercise)
            except Exception as e:
                print(f"Error loading live exercise file {file_path}: {e}")
        elif action == "Create Custom Exercise":
            editor.create_interactive_question()
        elif action == "Vim Commands Quiz":
            if vim_commands_quiz:
                vim_commands_quiz()
            else:
                print("Vim quiz module not available.")
    except (EOFError, KeyboardInterrupt):
        print("\nExiting interactive menu.")
        return


def run_yaml_editing_mode(data_file):
    """Run semantic YAML editing exercises from JSON definitions."""
    if VimYamlEditor is None:
        print("YAML editing requires the VimYamlEditor module.")
        return
    try:
        with open(data_file, 'r') as f:
            sections = json.load(f)
    except Exception as e:
        print(f"Error loading YAML exercise data from {data_file}: {e}")
        return
    editor = VimYamlEditor()
    yaml_exercises = []
    for section in sections:
        category = section.get('category', 'General')
        for item in section.get('prompts', []):
            if item.get('question_type') == 'yaml_edit':
                item['category'] = category
                yaml_exercises.append(item)
    if not yaml_exercises:
        print("No YAML exercises found in data file.")
        return
    print(f"\n{Fore.CYAN}=== Kubelingo YAML Editing Mode ==={Style.RESET_ALL}")
    print(f"Found {len(yaml_exercises)} YAML editing exercises.")
    print(f"Editor: {os.environ.get('EDITOR', 'vim')}")
    for idx, question in enumerate(yaml_exercises, 1):
        print(f"\n{Fore.YELLOW}Exercise {idx}/{len(yaml_exercises)}: {question.get('prompt')}{Style.RESET_ALL}")
        success = editor.run_yaml_edit_question(question, index=idx)
        if success and question.get('explanation'):
            print(f"{Fore.GREEN}Explanation: {question['explanation']}{Style.RESET_ALL}")
        if idx < len(yaml_exercises):
            try:
                cont = input("Continue to next exercise? (y/N): ")
                if not cont.lower().startswith('y'):
                    break
            except (EOFError, KeyboardInterrupt):
                print("\nExiting exercise mode.")
                break
    print(f"\n{Fore.CYAN}=== YAML Editing Session Complete ==={Style.RESET_ALL}")
    
# Legacy alias for cloud-mode static branch
def main():
    while True:
        print_banner()
        print()
        parser = argparse.ArgumentParser(description='Kubelingo: Interactive kubectl and YAML quiz tool')
        
        # Core quiz options
        parser.add_argument('-f', '--file', type=str, default=DEFAULT_DATA_FILE,
                            help='Path to quiz data JSON file for command quiz')
        parser.add_argument('-n', '--num', type=int, default=0,
                            help='Number of questions to ask (default: all)')
        parser.add_argument('-c', '--category', type=str,
                            help='Limit quiz to a specific category')
        parser.add_argument('--list-categories', action='store_true',
                            help='List available categories and exit')
        parser.add_argument('--history', action='store_true',
                            help='Show quiz history and statistics')
        parser.add_argument('--review-flagged', '--review-only', '--flagged', dest='review_only', action='store_true',
                            help='Quiz only on questions flagged for review (alias: --review-only, --flagged)')

        # Module-based exercises
        parser.add_argument('module', nargs='?', default=None,
                            help='Run exercises for a specific module (e.g., kubernetes, kustom)')
        parser.add_argument('--list-modules', action='store_true',
                            help='List available exercise modules and exit')
        parser.add_argument('-u', '--custom-file', type=str, dest='custom_file',
                            help='Path to custom quiz JSON file for kustom module')
        parser.add_argument('--exercises', type=str,
                            help='Path to custom exercises JSON file for a module')
        parser.add_argument('--cluster-context', type=str,
                            help='Kubernetes cluster context to use for a module')
        parser.add_argument('--live', action='store_true',
                            help='For the kubernetes module: run live exercises instead of the command quiz.')

        args = parser.parse_args()
        restart_loop = False

        restart_loop = False

        # If no arguments provided, show an interactive menu
        if len(sys.argv) == 1:
            if questionary:
                try:
                    # Root menu: k8s, kustom, help, exit
                    choices = [
                        questionary.Choice(title='Kubernetes Command Quiz', value='k8s'),
                        questionary.Choice(title='Interactive YAML (Vim)', value='interactive_yaml'),
                        questionary.Choice(title='Custom Quiz Module (kustom)', value='kustom'),
                        questionary.Choice(title='Help', value='help'),
                        questionary.Choice(title='Exit', value=None),
                    ]
                    action = questionary.select(
                        "What would you like to do?",
                        choices=choices
                    ).ask()
                    if action is None or action == 'exit':
                        print("\nExiting.")
                        break
                    
                    if action == 'help':
                        parser.print_help()
                        continue
                    elif action == 'interactive_yaml':
                        run_interactive_yaml_menu()
                        break
                    elif action == 'k8s':
                        args.module = 'kubernetes'
                    elif action == 'kustom':
                        args.module = 'custom'
                    else:
                        args.module = action

                except (EOFError, KeyboardInterrupt):
                    print("\nExiting.")
                    break
            else:
                # Fallback prompt
                valid = ['k8s', 'interactive-yaml', 'kustom', 'help', 'exit']
                while True:
                    try:
                        print("What would you like to do? Available options: k8s, interactive-yaml, kustom, help, exit")
                        action = input("Enter choice: ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        print("\nExiting.")
                        break
                    if action in valid:
                        break
                    print(f"Invalid choice. Please enter one of: {', '.join(valid)}.")

                if action == 'exit':
                    break
                if action == 'help':
                    parser.print_help()
                    continue
                elif action == 'interactive-yaml':
                    run_interactive_yaml_menu()
                    break
                elif action == 'k8s':
                    args.module = 'kubernetes'
                elif action == 'kustom':
                    args.module = 'custom'
        
        if restart_loop:
            sys.argv = [sys.argv[0]]
            continue

        # If certain flags are used without a module, default to kubernetes
        if args.module is None and (
            args.file != DEFAULT_DATA_FILE or args.num != 0 or args.category or args.review_only or args.live
        ):
            args.module = 'kubernetes'

        if args.interactive_yaml:
            run_interactive_yaml_menu()
            break

        if args.history:
            show_history()
            break

        if args.list_modules:
            modules = discover_modules()
            print(f"{Fore.CYAN}Available Modules:{Style.RESET_ALL}")
            if modules:
                for mod in modules:
                    print(Fore.YELLOW + mod + Style.RESET_ALL)
            else:
                print("No modules found.")
            return

        if args.list_categories:
            # Category listing is a function of the kubernetes module.
            # This provides a simple way to list them without loading the module.
            print(f"{Fore.YELLOW}Note: Categories are specific to the 'kubernetes' module command quiz.{Style.RESET_ALL}")
            try:
                with open(args.file, 'r') as f:
                    data = json.load(f)
                cats = sorted({
                    section.get('category') 
                    for section in data 
                    if section.get('category') and section.get('prompts')
                })
                print(f"{Fore.CYAN}Available Categories:{Style.RESET_ALL}")
                if cats:
                    for cat in cats:
                        print(Fore.YELLOW + cat + Style.RESET_ALL)
                else:
                    print("No categories found in data file.")
            except Exception as e:
                print(f"{Fore.RED}Error loading quiz data from {args.file}: {e}{Style.RESET_ALL}")
            break

        # Handle module-based execution.
        if args.module:
            module_name = args.module.lower()
            if module_name == 'kustom':
                module_name = 'custom'
            
            # 'llm' is not a standalone module from the CLI, but an in-quiz helper.
            if module_name == 'llm':
                print(f"{Fore.RED}The 'llm' feature is available as a command during a quiz, not as a standalone module.{Style.RESET_ALL}")
                break

            # Prepare logging for other modules
            log_file = 'quiz_log.txt'
            logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(message)s')
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
                        break
                    session.run_exercises(args)
                    session.cleanup()
                else:
                    print(Fore.RED + f"Failed to load module '{module_name}'." + Style.RESET_ALL)
            except (ImportError, AttributeError) as e:
                print(Fore.RED + f"Error loading module '{module_name}': {e}" + Style.RESET_ALL)
            break

        # If no other action was taken, break the loop.
        if not args.module:
            break
if __name__ == '__main__':
    main()
