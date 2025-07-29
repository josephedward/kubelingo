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

try:
    from colorama import Fore, Style
except ImportError:
    # Fallback if colorama is not available
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = ""
    class Style:
        RESET_ALL = ""

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

# Quiz data directory (project root 'question-data/' directory)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DATA_DIR = os.path.join(ROOT, 'question-data')
DEFAULT_DATA_FILE = os.path.join(DATA_DIR, 'json', 'ckad_quiz_data.json')
YAML_QUESTIONS_FILE = os.path.join(DATA_DIR, 'json', 'yaml_edit_questions.json')
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







    
# Legacy alias for cloud-mode static branch
def main():
    while True:
        print_banner()
        print()
        parser = argparse.ArgumentParser(description='Kubelingo: Interactive kubectl and YAML quiz tool')
        
        # Kubernetes module shortcut
        parser.add_argument('--k8s', action='store_true', dest='k8s_mode',
                            help='Run Kubernetes exercises. A shortcut for the "kubernetes" module.')

        # Core quiz options
        parser.add_argument('-f', '--file', type=str, default=DEFAULT_DATA_FILE,
                            help='Path to quiz data JSON file for command quiz')
        parser.add_argument('-n', '--num', type=int, default=0,
                            help='Number of questions to ask (default: all)')
        parser.add_argument('--randomize', action='store_true',
                            help='Randomize question order (for modules that support it)')
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
        
        # Handle --k8s shortcut
        if args.k8s_mode:
            args.module = 'kubernetes'

        restart_loop = False

        # If no arguments provided, show an interactive menu of modules
        if len(sys.argv) == 1:
            mods = discover_modules()
            # Exclude internal-only and CSV quiz modules from root menu
            modules = [m for m in mods if m not in ('llm', 'killercoda_ckad')]
            # Stylize custom quiz as 'kustom' and ensure it appears after Kubernetes
            ordered = []
            if 'kubernetes' in modules:
                ordered.append('kubernetes')
            if 'custom' in modules:
                ordered.append('kustom')
            # append any other modules (if present)
            for m in modules:
                if m not in ('kubernetes', 'custom'):
                    ordered.append(m)
            modules = ordered
            if questionary:
                try:
                    choices = []
                    for mod in modules:
                        if mod == 'custom':
                            title = 'Custom Quiz'
                        elif mod == 'killercoda_ckad':
                            title = 'Killercoda CKAD'
                        else:
                            title = mod.replace('_', ' ').title()
                        choices.append(questionary.Choice(title=title, value=mod))
                    choices.append(questionary.Choice(title='Help', value='help'))
                    choices.append(questionary.Choice(title='Exit', value=None))
                    action = questionary.select(
                        "What would you like to do?",
                        choices=choices
                    ).ask()
                    if action is None:
                        print("\nExiting.")
                        break
                    if action == 'help':
                        parser.print_help()
                        continue
                    args.module = action
                except (EOFError, KeyboardInterrupt):
                    print("\nExiting.")
                    break
            else:
                # Fallback prompt
                valid = modules + ['help', 'exit']
                while True:
                    try:
                        print(f"What would you like to do? Available options: {', '.join(valid)}")
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
                args.module = action
        
        if restart_loop:
            sys.argv = [sys.argv[0]]
            continue

        # If certain flags are used without a module, default to kubernetes
        if args.module is None and (
            args.file != DEFAULT_DATA_FILE or args.num != 0 or args.category or args.review_only or args.live
        ):
            args.module = 'kubernetes'


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
