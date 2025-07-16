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
from kubelingo.modules.k8s_quiz import normalize_command, commands_equivalent, handle_live_k8s_question
from kubelingo.modules.base.loader import discover_modules, load_session
from datetime import datetime
from datetime import timedelta

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

def load_questions(data_file):
    # Load quiz data from JSON file
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading quiz data from {data_file}: {e}")
        sys.exit(1)
    questions = []
    for cat in data:
        category = cat.get('category', '')
        for item in cat.get('prompts', []):
            if item.get('yaml_exercise'):
                continue
            question_type = item.get('type', 'command')
            question = {
                'category': category,
                'prompt': item.get('prompt', ''),
                'explanation': item.get('explanation', ''),
                'type': question_type,
                'review': item.get('review', False)
            }
            if question_type == 'yaml_edit':
                if not yaml:
                    # If yaml lib is missing, we can't process these questions.
                    continue
                question['starting_yaml'] = item.get('starting_yaml', '')
                question['correct_yaml'] = item.get('correct_yaml', '')
            elif question_type == 'live_k8s_edit':
                question['starting_yaml'] = item.get('starting_yaml', '')
                question['assert_script'] = item.get('assert_script', '')
            else:  # command
                question['response'] = item.get('response', '')
            questions.append(question)
    return questions
    
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


def run_quiz(data_file, max_q, category_filter=None, review_only=False):
    # Configure logging
    log_file = 'quiz_log.txt'
    logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(message)s')
    logger = logging.getLogger()
    
    questions = load_questions(data_file)
    # Get all categories for interactive selection if no filter is provided
    all_categories = sorted(list(set(q['category'] for q in questions if q['category'])))
    # If a filter is provided, validate it
    if category_filter and category_filter not in all_categories:
        print(f"Category '{category_filter}' not found. Available categories: {', '.join(all_categories)}")
        return
    # If no filter, but there are categories, let the user choose
    if not category_filter and all_categories and questionary is not None:
        try:
            choices = ['ALL'] + all_categories
            category_filter = questionary.select(
                "Which category do you want to be quizzed on?",
                choices=choices
            ).ask()
            if category_filter == 'ALL':
                category_filter = None
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return

    # Filter questions by category if a filter is set
    if category_filter:
        questions = [q for q in questions if q['category'] == category_filter]

    if review_only:
        questions = [q for q in questions if q.get('review')]
        if not questions:
            print(Fore.YELLOW + "No questions flagged for review found." + Style.RESET_ALL)
            return
        print(Fore.MAGENTA + f"Starting review session for {len(questions)} flagged questions." + Style.RESET_ALL)

    # Live k8s questions are handled separately by --cloud-mode
    live_k8s_qs = [q for q in questions if q.get('type') == 'live_k8s_edit']
    if live_k8s_qs:
        print(Fore.YELLOW + f"Found {len(live_k8s_qs)} live Kubernetes exercise(s). To run them, use the --module kubernetes flag." + Style.RESET_ALL)
        questions = [q for q in questions if q.get('type') != 'live_k8s_edit']
    
    # Shuffle and select the number of questions for the quiz
    random.shuffle(questions)
    
    if max_q == 0:
        max_q = len(questions)

    # Check if there are enough questions
    if len(questions) < max_q:
        max_q = len(questions)
        if max_q == 0:
            print("No questions found for the selected category.")
            return
        print(f"Not enough questions, setting quiz length to {max_q}")
    
    quiz_questions = questions[:max_q]
    
    # Per-category statistics tracking
    category_stats = {cat: {'asked': 0, 'correct': 0} for cat in all_categories}
    
    # Start the quiz
    start_time = datetime.now()
    print(f"\nStarting quiz with {max_q} questions... (press Ctrl+D to exit anytime)")
    
    correct = 0
    asked = 0
    for i, q in enumerate(quiz_questions):
        asked += 1
        cat = q['category']
        if cat:
            category_stats[cat]['asked'] += 1
        
        # Calculate remaining time estimate
        if i > 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            avg_time = elapsed / i
            remaining_q = max_q - i
            remaining_time = timedelta(seconds=int(avg_time * remaining_q))
            remaining_str = str(remaining_time)
        else:
            remaining_str = "..."
        
        print(Fore.CYAN + f"[{asked}/{max_q}] Remaining: {remaining_str} Category: {q['category']}" + Style.RESET_ALL)
        print(Fore.YELLOW + f"Q: {q['prompt']}" + Style.RESET_ALL)
        
        q_type = q.get('type', 'command')

        if q_type == 'yaml_edit':
            if not yaml:
                print(Fore.RED + "YAML questions require the 'PyYAML' package. Please install it." + Style.RESET_ALL)
                continue
            with tempfile.NamedTemporaryFile(mode='w+', suffix=".yaml", delete=False, encoding='utf-8') as tmp:
                tmp.write(q.get('starting_yaml', ''))
                tmp_path = tmp.name
            
            editor = os.environ.get('EDITOR', 'vim')
            print(f"Opening a temp file in '{editor}' for you to edit...")
            try:
                subprocess.run([editor, tmp_path], check=True)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(Fore.RED + f"Error opening editor '{editor}': {e}. Skipping question." + Style.RESET_ALL)
                os.remove(tmp_path)
                continue
            
            with open(tmp_path, 'r', encoding='utf-8') as f:
                user_yaml_str = f.read()
            os.remove(tmp_path)

            is_correct = False
            try:
                user_data = yaml.safe_load(user_yaml_str) or {}
                correct_data = yaml.safe_load(q.get('correct_yaml', ''))
                is_correct = (user_data == correct_data)
            except yaml.YAMLError as e:
                print(Fore.RED + f"Your response was not valid YAML: {e}" + Style.RESET_ALL)
                is_correct = False
            
            if is_correct:
                print(Fore.GREEN + 'Correct!' + Style.RESET_ALL + '\n')
                correct += 1
                if cat:
                    category_stats[cat]['correct'] += 1
                if q.get('explanation'):
                    print(Fore.GREEN + f"Explanation: {q['explanation']}" + Style.RESET_ALL + '\n')
            else:
                print(Fore.RED + "Incorrect." + Style.RESET_ALL + '\n')
                print(Fore.RED + "Correct YAML:" + Style.RESET_ALL)
                print(Fore.GREEN + q.get('correct_yaml', '') + Style.RESET_ALL)
                if q.get('explanation'):
                    print(Fore.RED + f"Explanation: {q['explanation']}" + Style.RESET_ALL + '\n')
            
            expected_answer = q.get('correct_yaml', '')
            log_user_answer = (user_yaml_str[:200] + '...') if len(user_yaml_str) > 200 else user_yaml_str
            log_expected_answer = (expected_answer[:200] + '...') if len(expected_answer) > 200 else expected_answer
            logger.info(f"Question {asked}/{max_q}: type={q_type} prompt=\"{q['prompt']}\" expected=\"{log_expected_answer}\" answer=\"{log_user_answer}\" result=\"{'correct' if is_correct else 'incorrect'}\"")

        else: # command-based question
            try:
                ans = input('Your answer: ').strip()
            except EOFError:
                print()  # newline
                break
            is_correct = commands_equivalent(ans, q['response'])
            if is_correct:
                # Correct answer feedback
                print(Fore.GREEN + 'Correct!' + Style.RESET_ALL + '\n')
                correct += 1
                # Update per-category correct count
                if cat:
                    category_stats[cat]['correct'] += 1
                # Show explanation if available
                if q.get('explanation'):
                    print(Fore.GREEN + f"Explanation: {q['explanation']}" + Style.RESET_ALL + '\n')
            else:
                # Incorrect answer feedback with highlighted correct command
                print(
                    Fore.RED + "Incorrect. Correct answer: " + Style.RESET_ALL
                    + Fore.GREEN + q['response'] + Style.RESET_ALL + '\n'
                )
                # Show explanation if available
                if q.get('explanation'):
                    print(Fore.RED + f"Explanation: {q['explanation']}" + Style.RESET_ALL + '\n')
            # Log question result
            logger.info(f"Question {asked}/{max_q}: prompt=\"{q['prompt']}\" expected=\"{q['response']}\" answer=\"{ans}\" result=\"{'correct' if is_correct else 'incorrect'}\"")
        
        # Ask to flag for review or un-flag
        try:
            if review_only:
                review = input("Un-flag this question? [y/N]: ").strip().lower()
                if review.startswith('y'):
                    unmark_question_for_review(data_file, q['category'], q['prompt'])
                    print(Fore.MAGENTA + "Question un-flagged." + Style.RESET_ALL + '\n')
                else:
                    print()  # newline
            else:
                review = input("Flag this question for review? [y/N]: ").strip().lower()
                if review.startswith('y'):
                    mark_question_for_review(data_file, q['category'], q['prompt'])
                    print(Fore.MAGENTA + "Question flagged for review." + Style.RESET_ALL + '\n')
                else:
                    print()  # newline
        except (EOFError, KeyboardInterrupt):
            print()
            break
    
    # Quiz summary
    end_time = datetime.now()
    duration = end_time - start_time
    duration_fmt = str(duration).split('.')[0]
    
    print('--- Quiz Finished ---')
    print(f'Score: {correct}/{asked}')
    if asked > 0:
        pct = (correct / asked) * 100
        print(f'Percentage: {pct:.1f}%')
    print(f'Time taken: {duration_fmt}')
    
    # Save history
    history_entry = {
        'timestamp': datetime.now().isoformat(),
        'num_questions': asked,
        'num_correct': correct,
        'duration': duration_fmt,
        'data_file': data_file,
        'category_filter': category_filter,
        'per_category': category_stats
    }
    
    try:
        history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
        history.append(history_entry)
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Error saving quiz history: {e}")



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
    parser.add_argument('--module', type=str,
                        help='Run exercises for a specific module (e.g., kubernetes, kustom)')
    parser.add_argument('--list-modules', action='store_true',
                        help='List available exercise modules and exit')
    parser.add_argument('-u', '--custom-file', type=str, dest='custom_file',
                        help='Path to custom quiz JSON file for kustom module')
    parser.add_argument('--exercises', type=str,
                        help='Path to custom exercises JSON file for a module')
    parser.add_argument('--cluster-context', type=str,
                        help='Kubernetes cluster context to use for a module')

    args = parser.parse_args()

    # If no arguments provided, run the default CLI quiz silently
    if len(sys.argv) == 1:
        print(Fore.CYAN + "Type 'kubelingo --help' for full options." + Style.RESET_ALL)
        run_quiz(args.file, args.num, args.category, review_only=args.review_only)
        return
    
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
        logger = logging.getLogger()
        session = load_session(args.module, logger)
        if session:
            session.initialize()
            exercises_file = args.custom_file or args.exercises
            session.run_exercises(exercises_file)
            session.cleanup()
        else:
            print(Fore.RED + f"Failed to load module '{args.module}'." + Style.RESET_ALL)
        return

    # Default action: run the classic command quiz if no other mode was triggered
    run_quiz(args.file, args.num, args.category, review_only=args.review_only)

# Alias for backward-compatibility
run_yaml_exercise_mode = run_yaml_editing_mode

if __name__ == '__main__':
    main()
