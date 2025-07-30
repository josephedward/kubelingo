#!/usr/bin/env python3
"""
Kubelingo: A simple CLI tool to quiz commands (or other strings) based on supplied JSON data.
"""
import json
import argparse
import sys
import os
import logging
import readline  # Enable rich input editing, history, and arrow keys
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
    Fore, Style, print_banner, humanize_module, show_session_type_help, show_quiz_type_help
)
import os
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
    # Support 'kubelingo sandbox [pty|docker]' as subcommand syntax
    if len(sys.argv) >= 3 and sys.argv[1] == 'sandbox' and sys.argv[2] in ('pty', 'docker'):
        # rewrite to explicit sandbox-mode flag
        sys.argv = [sys.argv[0], sys.argv[1], '--sandbox-mode', sys.argv[2]] + sys.argv[3:]
    print_banner()
    print()
    # Warn prominently if no OpenAI API key is set
    if not os.getenv('OPENAI_API_KEY'):
        print(f"{Fore.RED}AI explanations are disabled: OPENAI_API_KEY is not set.{Style.RESET_ALL}")
        print(f"{Fore.RED}To enable AI features, select 'Enter OpenAI API Key to enable AI features' from the menu, or install 'kubelingo[llm]' and set OPENAI_API_KEY.{Style.RESET_ALL}")
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
    parser.add_argument('--ai-eval', action='store_true',
                        help='Use AI to evaluate sandbox exercises. Requires OPENAI_API_KEY.')

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
    # --live is deprecated, as all k8s exercises are now sandbox-based.
    # It is kept for backward compatibility but has no effect.
    parser.add_argument('--live', action='store_true', help=argparse.SUPPRESS)

    args = parser.parse_args()
    # Early flags: history and list-modules
    if args.history:
        show_history()
        return
    if args.list_modules:
        show_modules()
        return
    # For bare invocation (no flags or commands), present an interactive menu.
    if len(sys.argv) == 1:
        if questionary and sys.stdin.isatty() and sys.stdout.isatty():
            # This block provides a robust questionary-based menu.
            while True:  # Main loop to allow returning to the main menu
                # Session type selection
                choice = questionary.select(
                    "Select a session type:",
                    choices=[
                        questionary.Choice("PTY Shell", value="pty"),
                        questionary.Choice("Docker Container (requires Docker)", value="docker"),
                        questionary.Separator(),
                        questionary.Choice("Enter OpenAI API Key to enable AI features", value="api_key"),
                        questionary.Choice("Help", value="help"),
                        questionary.Choice("Exit", value="exit"),
                    ],
                    use_indicator=True
                ).ask()

                if choice is None or choice == 'exit':
                    return

                if choice == 'help':
                    show_session_type_help()
                    input("Press Enter to continue...")
                    continue  # Go back to session type selection

                if choice == 'api_key':
                    key = questionary.text("Enter your OpenAI API Key (leave blank to cancel):").ask()
                    if key:
                        os.environ['OPENAI_API_KEY'] = key
                        print(f"{Fore.GREEN}OpenAI API key set for this session. AI features enabled.{Style.RESET_ALL}")
                    continue  # Go back to session type selection

                session_type = choice

                # Quiz type selection
                quiz_choice = questionary.select(
                    f"Session: {session_type.upper()}. Select quiz type:",
                    choices=[
                        questionary.Choice("K8s (preinstalled)", value="k8s"),
                        questionary.Choice("Kustom (upload your own quiz)", value="kustom"),
                        questionary.Choice("Review flagged questions", value="review"),
                        questionary.Separator(),
                        questionary.Choice("Help", value="help"),
                        questionary.Choice("Back to main menu", value="back"),
                        questionary.Choice("Exit", value="exit"),
                    ],
                    use_indicator=True
                ).ask()

                if quiz_choice is None or quiz_choice == 'exit':
                    return

                if quiz_choice == 'back':
                    continue  # Restart the main loop

                if quiz_choice == 'help':
                    show_quiz_type_help()
                    input("Press Enter to continue...")
                    continue  # Restart the main loop to show quiz types again

                if quiz_choice == 'k8s':
                    args.module = 'kubernetes'
                elif quiz_choice == 'kustom':
                    args.module = 'custom'
                    path = questionary.path("Enter path to your custom quiz JSON file:").ask()
                    if not path:
                        print(f"{Fore.YELLOW}No file provided. Returning to main menu.{Style.RESET_ALL}")
                        continue
                    args.custom_file = path
                elif quiz_choice == 'review':
                    args.module = 'kubernetes'
                    args.review_only = True

                # Set sandbox mode from session type
                if session_type == 'pty':
                    args.pty = True
                elif session_type == 'docker':
                    args.docker = True

                # We have a module and sandbox type, so we can break the loop and proceed.
                break
        else:
            # Fallback to simple text menu if not in a TTY or questionary is not available
            # Session type selection
            while True:
                print()
                print("Select a session type:")
                print(" 1) PTY Shell")
                print(" 2) Docker Container (requires Docker)")
                print(" 3) Enter OpenAI API Key to enable AI features")
                print(" 4) Exit")
                choice = input("Choice [1-4]: ").strip()
                if choice == '1':
                    args.pty = True
                    break
                if choice == '2':
                    args.docker = True
                    break
                if choice == '3':
                    key = input("Enter your OpenAI API Key (leave blank to cancel): ").strip()
                    if key:
                        os.environ['OPENAI_API_KEY'] = key
                        print(f"{Fore.GREEN}OpenAI API key set for this session. AI features enabled.{Style.RESET_ALL}")
                    continue
                if choice == '4':
                    return
                print(f"{Fore.RED}Invalid choice.{Style.RESET_ALL}")
            # Quiz type selection
            while True:
                print()
                print("Select quiz type:")
                print(" 1) K8s (preinstalled)")
                print(" 2) Kustom (upload your own quiz)")
                print(" 3) Review flagged questions")
                print(" 4) Help")
                print(" 5) Exit")
                sub = input("Choice [1-5]: ").strip()
                if sub == '1':
                    args.module = 'kubernetes'; break
                if sub == '2':
                    args.module = 'custom'
                    path = input("Enter path to your custom quiz JSON file: ").strip()
                    if not path:
                        print(f"{Fore.YELLOW}No file provided. Returning to main menu.{Style.RESET_ALL}")
                        return
                    args.custom_file = path; break
                if sub == '3':
                    args.module = 'kubernetes'; args.review_only = True; break
                if sub == '4':
                    show_quiz_type_help(); input("Press Enter to continue..."); continue
                if sub == '5':
                    return
                print(f"{Fore.RED}Invalid choice.{Style.RESET_ALL}")
        # Reset quiz file to allow default or custom file selection
        args.file = None

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
    # Bare invocation (no args): simple text-based menu
    if len(sys.argv) == 1:
        # Session type selection
        while True:
            print()
            print("Select a session type:")
            print(" 1) PTY Shell")
            print(" 2) Docker Container (requires Docker)")
            print(" 3) Enter OpenAI API Key to enable AI features")
            print(" 4) Exit")
            choice = input("Choice [1-4]: ").strip()
            if choice == '1':
                args.pty = True
                break
            if choice == '2':
                args.docker = True
                break
            if choice == '3':
                key = input("Enter your OpenAI API Key (leave blank to cancel): ").strip()
                if key:
                    os.environ['OPENAI_API_KEY'] = key
                    print(f"{Fore.GREEN}OpenAI API key set for this session. AI features enabled.{Style.RESET_ALL}")
                continue
            if choice == '4':
                return
            print(f"{Fore.RED}Invalid choice.{Style.RESET_ALL}")
        # Quiz type selection
        while True:
            print()
            print("Select quiz type:")
            print(" 1) K8s (preinstalled)")
            print(" 2) Kustom (upload your own quiz)")
            print(" 3) Review flagged questions")
            print(" 4) Help")
            print(" 5) Exit")
            sub = input("Choice [1-5]: ").strip()
            if sub == '1':
                args.module = 'kubernetes'; break
            if sub == '2':
                args.module = 'custom'
                path = input("Enter path to your custom quiz JSON file: ").strip()
                if not path:
                    print(f"{Fore.YELLOW}No file provided. Returning to main menu.{Style.RESET_ALL}")
                    return
                args.custom_file = path; break
            if sub == '3':
                args.module = 'kubernetes'; args.review_only = True; break
            if sub == '4':
                show_quiz_type_help(); input("Press Enter to continue..."); continue
            if sub == '5':
                return
            print(f"{Fore.RED}Invalid choice.{Style.RESET_ALL}")
        args.file = None

    # Global flags handling (note: history and list-modules are handled earlier)
    if args.list_categories:
        print(f"{Fore.YELLOW}Note: Categories are based on the loaded quiz data file.{Style.RESET_ALL}")
        try:
            from kubelingo.modules.kubernetes.session import load_questions
            questions = load_questions(args.file)
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
        args.file != DEFAULT_DATA_FILE or args.num != 0 or args.category or args.review_only
    ):
        args.module = 'kubernetes'

    # Handle module-based execution.
    if args.module:
        module_name = args.module.lower()

        # Optional Rust-based command quiz for non-interactive (--num) runs
        if module_name == 'kubernetes' and getattr(args, 'num', 0) > 0:
            try:
                from kubelingo.bridge import rust_bridge
                if rust_bridge.is_available():
                    # Attempt Rust-backed command quiz
                    if rust_bridge.run_command_quiz(args):
                        return
                    # Rust execution failed; fallback to Python quiz
                    print("Rust command quiz execution failed. Falling back to Python quiz.")
            except (ImportError, AttributeError):
                pass  # Fall through to Python implementation

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
