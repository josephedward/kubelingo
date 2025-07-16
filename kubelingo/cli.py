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

# Load and filter quiz questions from JSON data
def load_questions(data_file):
    """Load quiz data from a JSON file into a list of question dicts."""
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading quiz data from {data_file}: {e}")
        sys.exit(1)
    questions = []
    for section in data:
        category = section.get('category', '')
        for item in section.get('prompts', []):
            # Skip YAML exercises here
            if item.get('yaml_exercise'):
                continue
            qtype = item.get('type', 'command')
            q = {
                'category': category,
                'prompt': item.get('prompt', ''),
                'explanation': item.get('explanation', ''),
                'type': qtype,
                'review': item.get('review', False)
            }
            if qtype == 'yaml_edit':
                if not yaml:
                    continue
                q['starting_yaml'] = item.get('starting_yaml', '')
                q['correct_yaml'] = item.get('correct_yaml', '')
            elif qtype == 'live_k8s_edit':
                q['starting_yaml'] = item.get('starting_yaml', '')
                q['assert_script'] = item.get('assert_script', '')
            else:
                q['response'] = item.get('response', '')
            questions.append(q)
    return questions

# Functions to flag or un-flag questions for review in-place in the data file
def mark_question_for_review(data_file, category, prompt_text):
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
                        help='Run exercises for a specific module (e.g., kubernetes, custom)')
    parser.add_argument('--list-modules', action='store_true',
                        help='List available exercise modules and exit')
    parser.add_argument('-u', '--custom-file', type=str, dest='custom_file',
                        help='Path to custom quiz JSON file for custom module')
    parser.add_argument('--exercises', type=str,
                        help='Path to custom exercises JSON file for a module')
    parser.add_argument('--cluster-context', type=str,
                        help='Kubernetes cluster context to use for a module')

    args = parser.parse_args()

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
                    return
                if action == 'help':
                    parser.print_help()
                    return
                # Map friendly names to module names
                if action == 'k8s':
                    args.module = 'kubernetes'
                else:
                    args.module = action
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                return
        else:
            # Fallback prompt
            valid = ['k8s', 'kustom', 'help']
            while True:
                try:
                    print("What would you like to do? Available options: k8s, kustom, help")
                    action = input("Enter choice: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print("\nExiting.")
                    return
                if action in valid:
                    break
                print("Invalid choice. Please enter one of: k8s, kustom, help.")
            if action == 'help':
                parser.print_help()
                return
            if action == 'k8s':
                args.module = 'kubernetes'
            else:
                args.module = action
    
    # Handle modes that exit immediately
    if args.history:
        show_history()
        return

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
        questions = load_questions(args.file)
        cats = sorted({q['category'] for q in questions if q.get('category')})
        print(f"{Fore.CYAN}Available Categories:{Style.RESET_ALL}")
        for cat in cats:
            print(Fore.YELLOW + cat + Style.RESET_ALL)
        return

    if args.vim_quiz:
        if not vim_commands_quiz:
            print("Vim quiz module not loaded.")
            return
        score = vim_commands_quiz()
        print(f"\nVim Quiz completed with {score:.1%} accuracy")
        return
    
    if args.yaml_exercises:
        if not VimYamlEditor:
            print("YAML editor module not loaded.")
            return
        run_yaml_editing_mode(YAML_QUESTIONS_FILE)
        return

    # Handle module-based execution.
    if args.module:
        log_file = 'quiz_log.txt'
        logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(message)s')
        logger = logging.getLogger()

        # The `custom` module needs special handling for the file path
        if args.module == 'custom':
            if not args.custom_file and not args.exercises:
                print(Fore.RED + "For the 'custom' module, you must provide a quiz file with --custom-file or --exercises." + Style.RESET_ALL)
                return
        
        session = load_session(args.module, logger)
        if session:
            init_ok = session.initialize()
            if not init_ok:
                print(Fore.RED + f"Module '{args.module}' initialization failed. Exiting." + Style.RESET_ALL)
                return

            session.run_exercises(args)
            session.cleanup()
        else:
            print(Fore.RED + f"Failed to load module '{args.module}'." + Style.RESET_ALL)
        return

    # If no module was selected and no other command was run, show help.
    parser.print_help()

# Alias for backward-compatibility
run_yaml_exercise_mode = run_yaml_editing_mode

if __name__ == '__main__':
    main()
