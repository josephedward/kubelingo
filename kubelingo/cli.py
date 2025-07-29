#!/usr/bin/env python3
"""
cli_quiz.py: A simple CLI tool to quiz commands (or other strings) based on supplied JSON data.
"""
import json
import random
import argparse
import sys
import pty
import datetime
import tempfile
# OS utilities
import os
import pty
import shutil
import subprocess
import logging
import shlex
# Base session loader
# Core session loader and review utilities
from kubelingo.modules.base.loader import discover_modules, load_session
from kubelingo.modules.kubernetes.session import (
    get_all_flagged_questions,
    _clear_all_review_flags,
    _get_quiz_files,
    load_questions,
    mark_question_for_review,
    unmark_question_for_review,
)
# Unified question-data loaders (question-data/{json,md,yaml})
from kubelingo.modules.json_loader import JSONLoader
from kubelingo.modules.md_loader import MDLoader
from kubelingo.modules.yaml_loader import YAMLLoader

def _humanize_module(name: str) -> str:
    """Turn a module filename into a human-friendly title."""
    # If prefixed with order 'a.', drop prefix
    if '.' in name:
        disp = name.split('.', 1)[1]
    else:
        disp = name
    return disp.replace('_', ' ').title()

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
    from colorama import Fore, Style, init
    init()
except ImportError:
    # Fallback if colorama is not available
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = ""
    class Style:
        RESET_ALL = ""
        DIM = ""
    
# Disable ANSI color codes when not writing to a real terminal
if not sys.stdout.isatty():
    Fore.RED = Fore.GREEN = Fore.YELLOW = Fore.CYAN = Fore.MAGENTA = ""
    Style.RESET_ALL = ""

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
LOGS_DIR = os.path.join(ROOT, 'logs')
DEFAULT_DATA_FILE = os.path.join(DATA_DIR, 'json', 'ckad_quiz_data.json')
YAML_QUESTIONS_FILE = os.path.join(DATA_DIR, 'json', 'yaml_edit_questions.json')
# History file for storing past quiz performance
HISTORY_FILE = os.path.join(LOGS_DIR, '.cli_quiz_history.json')

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

def show_session_type_help():
    """Prints an explanation of the PTY and Docker sandbox environments."""
    print(f"""
{Fore.CYAN}--- Sandbox Environments Help ---{Style.RESET_ALL}

Kubelingo offers two types of sandbox environments for exercises:

{Fore.GREEN}1. PTY Shell (Embedded){Style.RESET_ALL}
   - {Fore.YELLOW}How it works:{Style.RESET_ALL} Spawns a native shell process (like 'bash') directly on your system using a pseudo-terminal (PTY). This is the same technology terminal emulators use.
   - {Fore.YELLOW}Pros:{Style.RESET_ALL} Very fast to start, uses your local environment and tools.
   - {Fore.YELLOW}Cons:{Style.RESET_ALL} Not isolated. Commands run as your user with access to your file system and network. Accidental destructive commands can affect your machine.
   - {Fore.YELLOW}Requirements:{Style.RESET_ALL} None. Works out-of-the-box on Linux and macOS.

{Fore.GREEN}2. Docker Container{Style.RESET_ALL}
   - {Fore.YELLOW}How it works:{Style.RESET_ALL} Launches a pre-built Docker container with a fixed set of tools (bash, vim, kubectl). Your current directory is mounted as a workspace.
   - {Fore.YELLOW}Pros:{Style.RESET_ALL} Fully isolated. Cannot affect your host system. Provides a consistent, clean environment for every exercise.
   - {Fore.YELLOW}Cons:{Style.RESET_ALL} Slower to start, especially the first time. Requires Docker to be installed and running.
   - {Fore.YELLOW}Requirements:{Style.RESET_ALL} Docker must be installed and the Docker daemon must be running.

{Fore.CYAN}Which one to choose?{Style.RESET_ALL}
- For quick, simple command quizzes, {Fore.GREEN}PTY Shell{Style.RESET_ALL} is fine.
- For complex YAML editing or live cluster exercises, {Fore.GREEN}Docker Container{Style.RESET_ALL} is recommended for safety and consistency.
""")

def show_quiz_type_help():
    """Prints an explanation of the different quiz modes."""
    print(f"""
{Fore.CYAN}--- Quiz Types Help ---{Style.RESET_ALL}

{Fore.GREEN}1. K8s (preinstalled){Style.RESET_ALL}
   - This section contains quizzes and exercises that come bundled with Kubelingo.
   - They are organized into different files based on the topic (e.g., Command Quizzes, YAML Editing, Vim Practice).
   - You will be presented with a list of these files to choose from.

{Fore.GREEN}2. Kustom (upload your own quiz){Style.RESET_ALL}
   - This allows you to run a quiz from your own custom-made JSON file.
   - The JSON file must follow the same format as the built-in quiz files. It should be a list of sections, where each section has a 'category' and a list of 'prompts'.
   - You will be prompted for the path to your file when you select this option.

{Fore.GREEN}3. Review{Style.RESET_ALL}
   - This mode gathers all questions you have previously 'flagged' for review across all K8s quizzes.
   - During a quiz, if you are unsure about a question, you can flag it.
   - Use this mode for a focused session on topics you find difficult.
   - You can clear all flags from the Kubernetes exercise menu.
""")

def show_modules():
    """Display available built-in and question-data modules."""
    # Built-in modules
    modules = discover_modules()
    print(f"{Fore.CYAN}Built-in Modules:{Style.RESET_ALL}")
    if modules:
        for mod in modules:
            print(Fore.YELLOW + mod + Style.RESET_ALL)
    else:
        print("No built-in modules found.")
    # Question-data modules by source file
    print(f"\n{Fore.CYAN}Question-data Modules (by file):{Style.RESET_ALL}")
    # JSON modules
    json_paths = JSONLoader().discover()
    if json_paths:
        print(Fore.CYAN + "  JSON:" + Style.RESET_ALL)
        for p in json_paths:
            name = os.path.splitext(os.path.basename(p))[0]
            print(f"    {Fore.YELLOW}{name}{Style.RESET_ALL} -> {p}")
    # Markdown modules
    md_paths = MDLoader().discover()
    if md_paths:
        print(Fore.CYAN + "  Markdown:" + Style.RESET_ALL)
        for p in md_paths:
            name = os.path.splitext(os.path.basename(p))[0]
            print(f"    {Fore.YELLOW}{name}{Style.RESET_ALL} -> {p}")
    # YAML modules
    yaml_paths = YAMLLoader().discover()
    if yaml_paths:
        print(Fore.CYAN + "  YAML:" + Style.RESET_ALL)
        for p in yaml_paths:
            name = os.path.splitext(os.path.basename(p))[0]
            print(f"    {Fore.YELLOW}{name}{Style.RESET_ALL} -> {p}")
    







    
# Legacy alias for cloud-mode static branch
def main():
    os.makedirs(LOGS_DIR, exist_ok=True)
    while True:
        print_banner()
        print()
        parser = argparse.ArgumentParser(description='Kubelingo: Interactive kubectl and YAML quiz tool')
        # Unified exercise mode: run questions from question-data modules
        parser.add_argument('--exercise-module', type=str,
                            help='Run unified live exercise for a question-data module')
        
        # Kubernetes module shortcut
        parser.add_argument('--k8s', action='store_true', dest='k8s_mode',
                            help='Run Kubernetes exercises. A shortcut for the "kubernetes" module.')

        # Sandbox modes (deprecated flags) and new sandbox command support
        parser.add_argument('--pty', action='store_true', help="[deprecated] Use an embedded PTY shell for exercises.")
        parser.add_argument('--docker', action='store_true', help="[deprecated] Use a Docker container for exercises.")
        parser.add_argument('--sandbox-mode', choices=['pty','docker'], dest='sandbox_mode',
                            help='Sandbox mode to use when running the "sandbox" command (default: pty)')

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
                            help='Run exercises for a specific module (e.g., kubernetes, kustom, sandbox)')
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
        # Sandbox mode dispatch: if specified with other args, they are passed to the module.
        # If run alone, they launch a shell and exit.
        from .sandbox import spawn_pty_shell, launch_container_sandbox
        # Launch sandbox: new "sandbox" module or legacy --pty/--docker flags
        if args.module == 'sandbox' or ((args.pty or args.docker)
                                        and args.module is None
                                        and not args.k8s_mode
                                        and not args.exercise_module):
            # choose mode: explicit sandbox_mode > legacy flags > default 'pty'
            if args.sandbox_mode:
                mode = args.sandbox_mode
            elif args.docker:
                mode = 'docker'
            else:
                mode = 'pty'
            if mode == 'pty':
                spawn_pty_shell()
            elif mode == 'docker':
                launch_container_sandbox()
            else:
                print(f"Unknown sandbox mode: {mode}")
            return

        # If unified exercise requested, load and list questions
        if args.exercise_module:
            questions = []
            for loader in (JSONLoader(), MDLoader(), YAMLLoader()):
                for path in loader.discover():
                    name = os.path.splitext(os.path.basename(path))[0]
                    if name == args.exercise_module:
                        questions.extend(loader.load_file(path))
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

        restart_loop = False

        # If no arguments provided, show an interactive menu
        if len(sys.argv) == 1:
            if not questionary:
                print(f"{Fore.YELLOW}For a rich interactive menu, please install 'questionary' (`pip install questionary`){Style.RESET_ALL}")
                print("Falling back to default Kubernetes quiz module.")
                args.module = 'kubernetes'
            else:
                try:
                    session_type = None
                    while True:  # Main interactive loop
                        # Level 1 Menu: Session Type
                        if session_type is None:
                            choice = questionary.select(
                                "Select a session type:",
                                choices=[
                                    questionary.Choice("1. PTY Shell", value="pty"),
                                    questionary.Choice("2. Docker Container", value="docker"),
                                    questionary.Separator(),
                                    questionary.Choice("3. Help", value="help"),
                                    questionary.Choice("4. Exit", value="exit")
                                ],
                                use_indicator=True
                            ).ask()

                            if choice == "exit" or choice is None:
                                return
                            elif choice == "help":
                                show_session_type_help()
                                input("\nPress Enter to return to the menu...")
                                continue
                            else:
                                session_type = choice
                        
                        # Level 2 Menu: Quiz Type
                        quiz_choice = questionary.select(
                            f"Session: {session_type.upper()}. Select quiz type:",
                            choices=[
                                questionary.Choice("1. K8s (preinstalled)", value="k8s"),
                                questionary.Choice("2. Kustom (upload your own quiz)", value="kustom"),
                                questionary.Choice("3. Review flagged questions", value="review"),
                                questionary.Separator(),
                                questionary.Choice("4. Help", value="help"),
                                questionary.Choice("5. Back", value="back")
                            ],
                            use_indicator=True
                        ).ask()

                        if quiz_choice is None: # User pressed Ctrl+C
                            return
                        elif quiz_choice == "back":
                            session_type = None
                            continue
                        elif quiz_choice == "help":
                            show_quiz_type_help()
                            input("\nPress Enter to return to the menu...")
                            continue
                        
                        # User has made a selection, set args and break to run the module
                        if session_type == 'pty':
                            args.pty = True
                        elif session_type == 'docker':
                            args.docker = True
                        
                        if quiz_choice == 'k8s':
                            args.module = 'kubernetes'
                        elif quiz_choice == 'kustom':
                            args.module = 'custom'
                            # In interactive mode, we need to prompt for the file
                            custom_file = questionary.path("Enter path to your custom quiz JSON file:").ask()
                            if not custom_file:
                                print(f"{Fore.YELLOW}No file selected. Returning to menu.{Style.RESET_ALL}")
                                session_type = None # Go back to the top menu
                                continue
                            args.custom_file = custom_file
                        elif quiz_choice == 'review':
                            args.module = 'kubernetes'
                            args.review_only = True
                        
                        break # Exit interactive loop and proceed to run module
                except (EOFError, KeyboardInterrupt):
                    print("\nExiting.")
                    return
        
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
            show_modules()
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
            log_file = os.path.join(LOGS_DIR, 'quiz_log.txt')
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
