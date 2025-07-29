#!/usr/bin/env python3
"""
Kubelingo: A simple CLI tool to quiz commands (or other strings) based on supplied JSON data.
"""
import json
import argparse
import sys
import os
import logging
# Provide pytest.anything for test wildcard assertions
try:
    import pytest
    from unittest.mock import ANY
    pytest.anything = lambda *args, **kwargs: ANY
except ImportError:
    pass

# Base session loader
from kubelingo.modules.base.loader import discover_modules, load_session
from kubelingo.modules.base.session import SessionManager
from kubelingo.modules.kubernetes.session import (
    _get_quiz_files,
)
# Unified question-data loaders (question-data/{json,md,yaml})
from kubelingo.modules.json_loader import JSONLoader
from kubelingo.modules.md_loader import MDLoader
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.utils.ui import (
    Fore, Style, questionary, print_banner, humanize_module, show_session_type_help, show_quiz_type_help
)
from kubelingo.utils.config import (
    LOGS_DIR, HISTORY_FILE, DEFAULT_DATA_FILE, LOG_FILE
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
            print(f"    {Fore.YELLOW}{humanize_module(name)}{Style.RESET_ALL} -> {p}")
    # Markdown modules
    md_paths = MDLoader().discover()
    if md_paths:
        print(Fore.CYAN + "  Markdown:" + Style.RESET_ALL)
        for p in md_paths:
            name = os.path.splitext(os.path.basename(p))[0]
            print(f"    {Fore.YELLOW}{humanize_module(name)}{Style.RESET_ALL} -> {p}")
    # YAML modules
    yaml_paths = YAMLLoader().discover()
    if yaml_paths:
        print(Fore.CYAN + "  YAML:" + Style.RESET_ALL)
        for p in yaml_paths:
            name = os.path.splitext(os.path.basename(p))[0]
            print(f"    {Fore.YELLOW}{humanize_module(name)}{Style.RESET_ALL} -> {p}")
    







    
# Legacy alias for cloud-mode static branch
def main():
    os.makedirs(LOGS_DIR, exist_ok=True)
    while True:
        # Support 'kubelingo sandbox [pty|docker]' as subcommand syntax
        if len(sys.argv) >= 3 and sys.argv[1] == 'sandbox' and sys.argv[2] in ('pty', 'docker'):
            # rewrite to explicit sandbox-mode flag
            sys.argv = [sys.argv[0], sys.argv[1], '--sandbox-mode', sys.argv[2]] + sys.argv[3:]
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
        parser.add_argument('--pty', action='store_true', help="[DEPRECATED] Use 'kubelingo sandbox --sandbox-mode pty' instead.")
        parser.add_argument('--docker', action='store_true', help="[DEPRECATED] Use 'kubelingo sandbox --sandbox-mode docker' instead.")
        parser.add_argument('--sandbox-mode', choices=['pty', 'docker', 'container'], dest='sandbox_mode',
                            help='Sandbox mode to use: pty (default), docker, or container (alias for docker).')

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

        # Module-based exercises. Handled as a list to support subcommands like 'sandbox pty'.
        parser.add_argument('command', nargs='*',
                            help="Command to run (e.g. 'kubernetes' or 'sandbox pty')")
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

        # Process positional command
        args.module = None
        args.sandbox_submode = None
        if args.command:
            args.module = args.command[0]
            if args.module == 'sandbox' and len(args.command) > 1:
                subcommand = args.command[1]
                if subcommand in ['pty', 'docker']:
                    args.sandbox_submode = subcommand
                else:
                    parser.error(f"unrecognized arguments: {subcommand}")
        # Sandbox mode dispatch: if specified with other args, they are passed to the module.
        # If run alone, they launch a shell and exit.
        from .sandbox import spawn_pty_shell, launch_container_sandbox
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
                spawn_pty_shell()
            elif mode in ('docker', 'container'):
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
            # Exit after listing modules
            sys.exit(0)

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

            # Special handling for kubernetes module to try Rust bridge first
            if module_name == 'kubernetes':
                try:
                    from kubelingo.bridge import rust_bridge
                    if rust_bridge.is_available():
                        if rust_bridge.run_command_quiz(args):
                            break  # Rust quiz ran, exit module execution
                except ImportError:
                    pass  # Fall through to Python implementation

            if module_name == 'kustom':
                module_name = 'custom'

            # 'llm' is not a standalone module from the CLI, but an in-quiz helper.
            if module_name == 'llm':
                print(f"{Fore.RED}The 'llm' feature is available as a command during a quiz, not as a standalone module.{Style.RESET_ALL}")
                break

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
