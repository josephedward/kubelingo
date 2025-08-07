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
import json
import argparse
import sys
import os
import logging
import subprocess
import shutil
import readline  # Enable rich input editing, history, and arrow keys
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
# Unified question-data loaders (question-data/{json,md,yaml})
from kubelingo.modules.json_loader import JSONLoader
from kubelingo.modules.md_loader import MDLoader
from kubelingo.modules.question_generator import AIQuestionGenerator
from kubelingo.modules.yaml_loader import YAMLLoader
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
import os
from kubelingo.utils.config import (
    LOGS_DIR, HISTORY_FILE, DEFAULT_DATA_FILE, LOG_FILE, VIM_QUESTIONS_FILE
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
    # Only display banner when not showing help
    if '--help' not in sys.argv and '-h' not in sys.argv:
        print_banner()
        print()
    # Attempt to load OpenAI API key from user config if not set
    import getpass
    from pathlib import Path
    if not os.getenv('OPENAI_API_KEY'):
        cfg_dir = Path.home() / '.kubelingo'
        key_file = cfg_dir / 'api_key'
        if key_file.exists():
            try:
                key = key_file.read_text(encoding='utf-8').strip()
                if key:
                    os.environ['OPENAI_API_KEY'] = key
            except Exception:
                pass
    # Prompt for key if still missing and not requesting help
    if not os.getenv('OPENAI_API_KEY') and '--help' not in sys.argv and '-h' not in sys.argv:
        try:
            prompt = getpass.getpass('Enter your OpenAI API key to enable AI features (leave blank to skip): ')
        except Exception:
            prompt = ''
        if prompt:
            try:
                cfg_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
                key_file.write_text(prompt.strip(), encoding='utf-8')
                os.chmod(str(key_file), 0o600)
                os.environ['OPENAI_API_KEY'] = prompt.strip()
                print(f"{Fore.GREEN}OpenAI API key saved to {key_file}{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}Failed to save API key: {e}{Style.RESET_ALL}")
    # Warn prominently if no OpenAI API key is available (skip when showing help)
    if '--help' not in sys.argv and '-h' not in sys.argv and not os.getenv('OPENAI_API_KEY'):
        print(f"{Fore.RED}AI explanations are disabled: no OpenAI API key provided.{Style.RESET_ALL}")
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
    parser.add_argument('--quiz', type=str, help='Select a quiz by name.')
    parser.add_argument('-c', '--category', type=str,
                        help='Limit quiz to a specific category within the selected quiz file.')
    parser.add_argument('--list-categories', action='store_true',
                        help='List available categories and exit')
    parser.add_argument('--history', action='store_true',
                        help='Show quiz history and statistics')
    parser.add_argument('--review-flagged', '--review-only', '--flagged', dest='review_only', action='store_true',
                        help='Quiz only on questions flagged for review (alias: --review-only, --flagged)')
    parser.add_argument('--ai-eval', action='store_true',
                        help='Use AI to evaluate sandbox exercises. Requires OPENAI_API_KEY.')
    parser.add_argument('--start-cluster', action='store_true',
                        help='Automatically start a temporary Kind cluster for k8s sessions.')

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
    # Question-data enrichment: dedupe & AI-enrich explanations
    parser.add_argument(
        '--enrich', nargs=2, metavar=('SRC_DIR', 'DEST_FILE'),
        help='Enrich and dedupe question-data from SRC_DIR to DEST_FILE'
    )
    parser.add_argument(
        '--dry-run-enrich', action='store_true',
        help='Dry run enrichment (no file writes or API calls)'
    )
    # Enrichment feature flags
    parser.add_argument(
        '--generate-validations', action='store_true',
        help='Generate validation_steps via AI for questions missing them'
    )
    parser.add_argument(
        '--list-questions', action='store_true',
        help='List all question prompts for the selected quiz and exit'
    )
    parser.add_argument(
        '--ai-question', type=str, metavar='TOPIC',
        help='Generate one AI-based question on a given topic (e.g. serviceaccount) and exit'
    )
    parser.add_argument(
        '--ai-questions', nargs=2, metavar=('COUNT','TOPIC'),
        help='Generate multiple AI-based questions: specify COUNT and TOPIC, then exit'
    )
    parser.add_argument(
        '--enrich-model', type=str, default='gpt-3.5-turbo',
        help='AI model to use for explanations and validation generation'
    )
    parser.add_argument(
        '--enrich-format', choices=['json','yaml'], default='json',
        help='Output format for enriched question-data (json or yaml)'
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
        # Interactive mode. We'll build up `args` manually.
        # Initialize args with defaults.
        args = argparse.Namespace(
            file=None, num=0, randomize=False, category=None, list_categories=False,
            history=False, review_only=False, ai_eval=False, command=[], list_modules=False,
            custom_file=None, exercises=None, cluster_context=None, live=False, k8s_mode=False,
            pty=False, docker=False, sandbox_mode=None, exercise_module=None, module=None,
            start_cluster=False
        )
        is_interactive = questionary and sys.stdin.isatty() and sys.stdout.isatty()

        try:
            # For interactive mode, we skip session/quiz type selection and go
            # directly to the unified Kubernetes quiz menu.
            # We default to PTY mode as the distinction is not currently relevant.
            args.pty = True
            args.docker = False
            args.module = 'kubernetes'
            # Clear file to trigger interactive selection within the module.
            args.file = None

            logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')
            logger = logging.getLogger()

            session = load_session(args.module, logger)
            if session:
                init_ok = session.initialize()
                if not init_ok:
                    print(Fore.RED + f"Module '{args.module}' initialization failed." + Style.RESET_ALL)
                    return
                # run_exercises will now show the main menu and loop internally.
                session.run_exercises(args)
                session.cleanup()
            else:
                print(Fore.RED + f"Failed to load module '{args.module}'." + Style.RESET_ALL)
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.YELLOW}Exiting.{Style.RESET_ALL}")
            return
    else:
        # Non-interactive mode
        args = parser.parse_args()
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
            # generate_questions returns a list of Question objects
            questions = generator.generate_questions(topic, count)
            if not questions:
                print(f"{Fore.RED}Failed to generate AI questions for topic '{topic}'.{Style.RESET_ALL}")
                return
            print(f"\n{Fore.CYAN}AI-generated questions on '{topic}':{Style.RESET_ALL}")
            for i, q in enumerate(questions, 1):
                print(f"{i}. {q.prompt}")
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
            # Shortcut to display the main Kubernetes quiz menu and exit
            args.module = 'kubernetes'
            # Only interactive when no other quiz flags are present
            if args.num == 0 and not args.category and not args.review_only and not args.list_categories and not args.exercise_module:
                # Configure logging
                logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')
                logger = logging.getLogger()
                # Load session for side-effects (history, flags)
                load_session('kubernetes', logger)
                # Build menu choices from enabled quizzes
                from kubelingo.utils.config import ENABLED_QUIZZES
                choices = [{"name": name, "value": path} for name, path in ENABLED_QUIZZES.items()]
                # Add Exit option
                choices.append({"name": "Exit", "value": "exit_app"})
                # Display selection menu
                questionary.select(
                    "Choose a Kubernetes exercise:",
                    choices=choices,
                    use_indicator=True
                ).ask()
                return

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
            args.file != DEFAULT_DATA_FILE or args.num != 0 or args.category or args.review_only
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
