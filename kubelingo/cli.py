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
        flagged_questions = [q for q in questions if q.get('review')]
        categories = sorted({q['category'] for q in questions if q.get('category')})
        choices = []
        if flagged_questions:
            choices.append({'name': 'Flagged Questions', 'value': 'flagged'})
        choices.append({'name': 'All Questions', 'value': 'all'})
        for category in categories:
            choices.append({'name': category, 'value': category})
        selected = questionary.select(
            "Choose a quiz type or subject area:",
            choices=choices,
            use_indicator=True
        ).ask()
        if selected is None:
            print(f"\n{Fore.YELLOW}Quiz cancelled.{Style.RESET_ALL}")
            return
        if selected == 'flagged':
            args.review_only = True
        elif selected == 'all':
            pass
        else:
            args.category = selected

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
    pass
# Alias for backward-compatibility
run_yaml_exercise_mode = run_yaml_editing_mode

if __name__ == '__main__':
    main()
