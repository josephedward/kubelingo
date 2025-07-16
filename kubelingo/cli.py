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

# Import from local modules (support both package and direct script use)
try:
    from kubelingo.modules.vim_yaml_editor import VimYamlEditor, vim_commands_quiz
except ImportError:
    try:
        from modules.vim_yaml_editor import VimYamlEditor, vim_commands_quiz
    except ImportError:
        print("Warning: modules/vim_yaml_editor.py not found. YAML/Vim exercises will not be available.")
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
YAML_QUESTIONS_FILE = os.path.join(DATA_DIR, 'yaml_edit_questions.json')
# History file for storing past quiz performance
HISTORY_FILE = os.path.join(os.path.expanduser('~'), '.cli_quiz_history.json')

# Quiz-related functions are now part of the 'kubernetes' module.
def load_questions(data_file):
    """Loads and flattens questions from a JSON data file."""
    try:
        with open(data_file, 'r') as f:
            sections = json.load(f)
    except Exception as e:
        print(Fore.RED + f"Error loading quiz data from {data_file}: {e}" + Style.RESET_ALL)
        return []

    all_questions = []
    for section in sections:
        category = section.get('category', 'General')
        # Support both 'questions' and 'prompts' keys.
        qs = section.get('questions', []) or section.get('prompts', [])
        for q in qs:
            if 'category' not in q:
                q['category'] = category
            all_questions.append(q)
    return all_questions


def mark_question_for_review(data_file, category, prompt_text):
    """Adds 'review': True to the matching question in the JSON data file."""
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(Fore.RED + f"Error opening data file for review flagging: {e}" + Style.RESET_ALL)
        return
    changed = False
    for section in data:
        if section.get('category') == category:
            for item in section.get('prompts', []):
                if item.get('prompt') == prompt_text:
                    item['review'] = True
                    changed = True
                    break
        if changed:
            break
    if not changed:
        print(Fore.RED + f"Warning: question not found in {data_file} to flag for review." + Style.RESET_ALL)
        return
    try:
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(Fore.RED + f"Error writing data file when flagging for review: {e}" + Style.RESET_ALL)


def unmark_question_for_review(data_file, category, prompt_text):
    """Removes 'review' flag from the matching question in the JSON data file."""
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(Fore.RED + f"Error opening data file for un-flagging: {e}" + Style.RESET_ALL)
        return
    changed = False
    for section in data:
        if section.get('category') == category:
            for item in section.get('prompts', []):
                if item.get('prompt') == prompt_text and item.get('review'):
                    del item['review']
                    changed = True
                    break
        if changed:
            break
    if not changed:
        print(Fore.RED + f"Warning: flagged question not found in {data_file} to un-flag." + Style.RESET_ALL)
        return
    try:
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(Fore.RED + f"Error writing data file when un-flagging: {e}" + Style.RESET_ALL)


def commands_equivalent(ans, expected):
    """
    Basic command comparison. Ignores extra whitespace and order of arguments.
    This is a simplified version. For full kubectl command comparison, a more
    sophisticated normalization (like in k8s_quiz.py) would be better.
    """
    if not ans or not expected:
        return False
    try:
        # Split commands into arguments and sort for comparison
        return sorted(shlex.split(ans)) == sorted(shlex.split(expected))
    except ValueError:
        return False  # Handle malformed command strings, e.g., unmatched quotes


def run_command_quiz(args):
    """Run a quiz session for command-line questions."""
    start_time = datetime.datetime.now()
    questions = load_questions(args.file)

    # In interactive mode, prompt user for quiz type (flagged/category)
    # This is determined by seeing if `questionary` is available and if no
    # filtering arguments were passed via the command line.
    is_interactive = questionary and not args.category and not args.review_only and not args.num
    if is_interactive:
        # Loop to allow going "back" up the menu hierarchy.
        while True:
            try:
                # First, check for any questions flagged for review
                flagged_questions = [q for q in questions if q.get('review')]
                if flagged_questions:
                    review_action = questionary.select(
                        "Review only flagged questions?",
                        choices=[
                            {'name': 'Yes', 'value': True},
                            {'name': 'No', 'value': False},
                            {'name': 'Back to main menu', 'value': 'back'}
                        ],
                        use_indicator=True
                    ).ask()

                    if review_action is None:  # User pressed Ctrl+C
                        print(f"\n{Fore.YELLOW}Quiz cancelled.{Style.RESET_ALL}")
                        return
                    if review_action == 'back':
                        return  # Exit this function to go back to the main menu prompt.
                    
                    args.review_only = review_action
                
                # If not reviewing flagged, or if there are no flagged questions, ask for category
                if not args.review_only:
                    categories = sorted({q['category'] for q in questions if q.get('category')})
                    if categories:
                        choices = ['All']
                        if flagged_questions:
                            choices.append('Back to previous step')
                        choices.extend(categories)

                        selected_category = questionary.select(
                            "Choose a subject area:",
                            choices=choices,
                            use_indicator=True
                        ).ask()

                        if selected_category is None:  # User pressed Ctrl+C
                            print(f"\n{Fore.YELLOW}Quiz cancelled.{Style.RESET_ALL}")
                            return
                        
                        if selected_category == 'Back to previous step':
                            # Reset flags and restart the loop to show the review prompt again.
                            args.review_only = False
                            args.category = None
                            continue

                        if selected_category != 'All':
                            args.category = selected_category
                
                # If we've reached here without continuing, we have our quiz options.
                break

            except (EOFError, KeyboardInterrupt):
                print(f"\n{Fore.YELLOW}Quiz cancelled.{Style.RESET_ALL}")
                return

    if args.review_only:
        questions = [q for q in questions if q.get('review')]
        if not questions:
            print(Fore.YELLOW + "No questions flagged for review found." + Style.RESET_ALL)
            return

    if args.category:
        questions = [q for q in questions if q.get('category') == args.category]
        if not questions:
            print(Fore.YELLOW + f"No questions found in category '{args.category}'." + Style.RESET_ALL)
            return

    if not questions:
        print(Fore.YELLOW + "No questions available for this quiz." + Style.RESET_ALL)
        return

    num_to_ask = args.num if args.num > 0 else len(questions)
    questions_to_ask = random.sample(questions, min(num_to_ask, len(questions)))

    if not questions_to_ask:
        print(Fore.YELLOW + "No questions to ask." + Style.RESET_ALL)
        return

    correct_count = 0
    per_category_stats = {}
    total_asked = len(questions_to_ask)

    print(f"\n{Fore.CYAN}=== Starting Kubelingo Quiz ==={Style.RESET_ALL}")
    print(f"File: {Fore.CYAN}{os.path.basename(args.file)}{Style.RESET_ALL}, Questions: {Fore.CYAN}{total_asked}{Style.RESET_ALL}")

    for i, q in enumerate(questions_to_ask, 1):
        category = q.get('category', 'General')
        if category not in per_category_stats:
            per_category_stats[category] = {'asked': 0, 'correct': 0}
        per_category_stats[category]['asked'] += 1

        print(f"\n{Fore.YELLOW}Question {i}/{total_asked} (Category: {category}){Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}{q['prompt']}{Style.RESET_ALL}")

        try:
            user_answer = input(f'{Fore.CYAN}Your answer: {Style.RESET_ALL}').strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Fore.YELLOW}Quiz interrupted.{Style.RESET_ALL}")
            break
        
        is_correct = commands_equivalent(user_answer, q.get('response', ''))
        if is_correct:
            correct_count += 1
            per_category_stats[category]['correct'] += 1
            print(f"{Fore.GREEN}Correct!{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Incorrect.{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Correct answer: {q.get('response', '')}{Style.RESET_ALL}")

        if q.get('explanation'):
            print(f"{Fore.CYAN}Explanation: {q['explanation']}{Style.RESET_ALL}")

        # --- Post-question action menu ---
        action_interrupted = False
        back_to_main = False
        while True:
            print() # Spacer
            try:
                is_flagged = q.get('review', False)
                flag_option = "Un-flag for Review" if is_flagged else "Flag for Review"
                
                if questionary:
                    choices = ["Next Question", flag_option, "Get LLM Clarification", "Back to Main Menu"]
                    action = questionary.select("Choose an action:", choices=choices, use_indicator=True).ask()
                    if action is None: raise KeyboardInterrupt
                else:
                    # Fallback for no questionary
                    print("Choose an action:")
                    print("  1: Next Question")
                    print(f"  2: {flag_option}")
                    print("  3: Get LLM Clarification")
                    print("  4: Back to Main Menu")
                    choice = input("Enter choice [1]: ").strip()
                    action_map = {'1': "Next Question", '2': flag_option, '3': "Get LLM Clarification", '4': "Back to Main Menu"}
                    action = action_map.get(choice, "Next Question")

                if action == "Next Question":
                    break
                elif action == "Back to Main Menu":
                    back_to_main = True
                    break
                elif action.startswith("Flag for Review"):
                    mark_question_for_review(args.file, q['category'], q['prompt'])
                    q['review'] = True
                    print(Fore.MAGENTA + "Question flagged for review." + Style.RESET_ALL)
                elif action.startswith("Un-flag for Review"):
                    unmark_question_for_review(args.file, q['category'], q['prompt'])
                    q['review'] = False
                    print(Fore.MAGENTA + "Question un-flagged." + Style.RESET_ALL)
                elif action == "Get LLM Clarification":
                    print(f"\n{Fore.CYAN}--- AI Clarification ---{Style.RESET_ALL}")
                    print("(AI feature is not yet implemented. This would provide a detailed explanation.)")
                    print(f"{Fore.CYAN}------------------------{Style.RESET_ALL}")

            except (EOFError, KeyboardInterrupt):
                print(f"\n{Fore.YELLOW}Quiz interrupted.{Style.RESET_ALL}")
                action_interrupted = True
                break

        if action_interrupted or back_to_main:
            break

    end_time = datetime.datetime.now()
    duration = str(end_time - start_time).split('.')[0]

    print(f"\n{Fore.CYAN}=== Quiz Complete ==={Style.RESET_ALL}")
    score = (correct_count / total_asked * 100) if total_asked > 0 else 0
    print(f"You got {Fore.GREEN}{correct_count}{Style.RESET_ALL} out of {Fore.YELLOW}{total_asked}{Style.RESET_ALL} correct ({Fore.CYAN}{score:.1f}%{Style.RESET_ALL}).")
    print(f"Time taken: {Fore.CYAN}{duration}{Style.RESET_ALL}")

    if back_to_main:
        return 'back_to_main'

    # Save history
    new_history_entry = {
        'timestamp': start_time.strftime('%Y-%m-%d %H:%M:%S'),
        'num_questions': total_asked,
        'num_correct': correct_count,
        'duration': duration,
        'data_file': os.path.basename(args.file),
        'category_filter': args.category,
        'per_category': per_category_stats
    }

    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                history_data = json.load(f)
                if isinstance(history_data, list):
                    history = history_data
        except (json.JSONDecodeError, IOError):
            pass  # Start with fresh history if file is corrupt or unreadable

    history.insert(0, new_history_entry)

    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except IOError as e:
        print(Fore.RED + f"Error saving quiz history: {e}" + Style.RESET_ALL)


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

        # Standalone exercise modes
        parser.add_argument('--yaml-exercises', action='store_true',
                            help='Run semantic YAML editing exercises')
        parser.add_argument('--yaml-edit', action='store_true', dest='yaml_exercises',
                            help='Alias for --yaml-exercises (semantic YAML editing exercises)')
        parser.add_argument('--vim-quiz', action='store_true',
                            help='Run Vim commands quiz')
        
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

    # If no arguments provided, show an interactive menu
    if len(sys.argv) == 1:
        if questionary:
            try:
                # Interactive modules: k8s cluster exercises and custom quizzes
                choices = ['k8s', 'kustom', 'help']
                action = questionary.select(
                    "What would you like to do?",
                    choices=choices
                ).ask()
                if action is None:
                    print("\nExiting.")
                    break
                if action == 'help':
                    parser.print_help()
                    break

                if action == 'k8s':
                    if run_command_quiz(args) == 'back_to_main':
                        restart_loop = True
                
                elif action == 'kustom':
                    args.module = 'custom'
                else:
                    args.module = action
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break
        else:
            # Fallback prompt
            valid = ['k8s', 'kustom', 'help']
            while True:
                try:
                    print("What would you like to do? Available options: k8s, kustom, help")
                    action = input("Enter choice: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print("\nExiting.")
                    break
                if action in valid:
                    break
                print("Invalid choice. Please enter one of: k8s, kustom, help.")
            if action == 'help':
                parser.print_help()
                break

            if action == 'k8s':
                if run_command_quiz(args) == 'back_to_main':
                    restart_loop = True

            elif action == 'kustom':
                args.module = 'custom'
            else:
                args.module = action
    
    if restart_loop:
        sys.argv = [sys.argv[0]]
        continue

    # Handle modes that exit immediately
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

    if args.vim_quiz:
        if not vim_commands_quiz:
            print("Vim quiz module not loaded.")
            break
        score = vim_commands_quiz()
        print(f"\nVim Quiz completed with {score:.1%} accuracy")
        break
    
    if args.yaml_exercises:
        if not VimYamlEditor:
            print("YAML editor module not loaded.")
            break
        run_yaml_editing_mode(YAML_QUESTIONS_FILE)
        break

    # Handle module-based execution.
    if args.module:
        module_name = args.module.lower()
        if module_name in ('k8s', 'kubernetes'):
            if run_command_quiz(args) == 'back_to_main':
                restart_loop = True
        elif module_name == 'kustom':
            module_name = 'custom'
        
        # 'llm' is not a standalone module from the CLI, but an in-quiz helper.
        if module_name == 'llm':
            print(f"{Fore.RED}The 'llm' feature is available as a command during a quiz, not as a standalone module.{Style.RESET_ALL}")
            break

        if restart_loop:
            sys.argv = [sys.argv[0]]
            continue

        # Prepare logging for other modules
        log_file = 'quiz_log.txt'
        logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(message)s')
        logger = logging.getLogger()
        # The `custom` module needs special handling for the file path
        if module_name == 'custom':
            if not args.custom_file and not args.exercises:
                print(Fore.RED + "For the 'kustom' module, you must provide a quiz file with --custom-file or --exercises." + Style.RESET_ALL)
                return
        # Load and run the specified module's session
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
        break

    # Default to the classic command quiz if no module was selected and no other mode was triggered.
    if not args.module and not restart_loop:
        if run_command_quiz(args) == 'back_to_main':
            restart_loop = True

    if restart_loop:
        sys.argv = [sys.argv[0]]
        continue
    else:
        break

# Alias for backward-compatibility
run_yaml_exercise_mode = run_yaml_editing_mode

if __name__ == '__main__':
    main()
