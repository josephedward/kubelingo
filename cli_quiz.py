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

# Import from local modules
try:
    from modules.vim_yaml_editor import VimYamlEditor, vim_commands_quiz
except ImportError:
    print("Warning: modules/vim_yaml_editor.py not found. YAML/Vim exercises will not be available.")
    VimYamlEditor = None  # YAML editing disabled
    vim_commands_quiz = None  # Vim quiz disabled

# Colored terminal output (optional)
try:
    import colorama
    from colorama import Fore, Style
    colorama.init(autoreset=True)
except ImportError:
    class _DummyFore:
        CYAN = MAGENTA = YELLOW = GREEN = RED = ''
    class _DummyStyle:
        RESET_ALL = ''
    Fore = _DummyFore()
    Style = _DummyStyle()

# Default quiz data file path
DEFAULT_DATA_FILE = os.path.join(os.path.dirname(__file__), 'data', 'ckad_quiz_data.json')
# YAML editing questions data file
YAML_QUESTIONS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'yaml_edit_questions.json')
# History file for storing past quiz performance
HISTORY_FILE = os.path.join(os.path.expanduser('~'), '.cli_quiz_history.json')

def check_dependencies(*commands):
    """Check if all command-line tools in `commands` are available."""
    missing = []
    for cmd in commands:
        if not shutil.which(cmd):
            missing.append(cmd)
    return missing

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
            question_type = item.get('type', 'command')
            question = {
                'category': category,
                'prompt': item.get('prompt', ''),
                'explanation': item.get('explanation', ''),
                'type': question_type
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

def handle_live_k8s_question(q, logger):
    """Handles a live Kubernetes question with a temporary kind cluster."""
    is_correct = False
    # Check for dependencies
    deps = check_dependencies('docker', 'kind', 'kubectl')
    if deps:
        print(Fore.RED + f"Missing dependencies for live questions: {', '.join(deps)}. Skipping." + Style.RESET_ALL)
        return False, ''

    cluster_name = f"kubelingo-quiz-{random.randint(1000, 9999)}"
    kubeconfig_path = os.path.join(tempfile.gettempdir(), f"{cluster_name}.kubeconfig")
    user_yaml_str = ''
    
    try:
        print(Fore.YELLOW + f"Creating temporary cluster '{cluster_name}'... (this may take a minute)" + Style.RESET_ALL)
        subprocess.run(['kind', 'create', 'cluster', '--name', cluster_name], check=True, capture_output=True)
        
        # Set KUBECONFIG for this session
        os.environ['KUBECONFIG'] = kubeconfig_path
        subprocess.run(['kind', 'get', 'kubeconfig', '--name', cluster_name], stdout=open(kubeconfig_path, 'w'), check=True)

        editor = os.environ.get('EDITOR', 'vim')
        
        while True:
            with tempfile.NamedTemporaryFile(mode='w+', suffix=".yaml", delete=False, encoding='utf-8') as tmp_yaml:
                tmp_yaml.write(q.get('starting_yaml', ''))
                tmp_yaml_path = tmp_yaml.name

            print(f"Opening a temp file in '{editor}' for you to edit...")
            try:
                subprocess.run([editor, tmp_yaml_path], check=True)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(Fore.RED + f"Error opening editor '{editor}': {e}. Skipping question." + Style.RESET_ALL)
                break 

            with open(tmp_yaml_path, 'r', encoding='utf-8') as f:
                user_yaml_str = f.read()
            os.remove(tmp_yaml_path)

            print("Applying your YAML to the cluster...")
            apply_proc = subprocess.run(
                ['kubectl', 'apply', '-f', '-'],
                input=user_yaml_str, text=True, capture_output=True
            )
            if apply_proc.returncode != 0:
                print(Fore.RED + "Error applying YAML:" + Style.RESET_ALL)
                print(apply_proc.stderr)
            else:
                print("Running validation script...")
                with tempfile.NamedTemporaryFile(mode='w+', suffix=".sh", delete=False, encoding='utf-8') as tmp_assert:
                    tmp_assert.write(q.get('assert_script', 'exit 1'))
                    tmp_assert_path = tmp_assert.name
                
                os.chmod(tmp_assert_path, 0o755)
                assert_proc = subprocess.run(['bash', tmp_assert_path], capture_output=True, text=True)
                os.remove(tmp_assert_path)

                if assert_proc.returncode == 0:
                    print(Fore.GREEN + "Correct!" + Style.RESET_ALL)
                    print(assert_proc.stdout)
                    is_correct = True
                    break
                else:
                    print(Fore.RED + "Incorrect. Validation failed:" + Style.RESET_ALL)
                    print(assert_proc.stdout or assert_proc.stderr)

            try:
                retry = input("Reopen editor to try again? [Y/n]: ").strip().lower()
            except EOFError:
                retry = 'n'
            if retry.startswith('n'):
                break
    
    finally:
        print(Fore.YELLOW + f"Deleting temporary cluster '{cluster_name}'..." + Style.RESET_ALL)
        subprocess.run(['kind', 'delete', 'cluster', '--name', cluster_name], check=True, capture_output=True)
        if os.path.exists(kubeconfig_path):
            os.remove(kubeconfig_path)
        if 'KUBECONFIG' in os.environ:
            del os.environ['KUBECONFIG']
        
    return is_correct, user_yaml_str

def run_quiz(data_file, max_q, category_filter=None):
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

        if q_type == 'live_k8s_edit':
            is_correct, user_yaml_str = handle_live_k8s_question(q, logger)
            if is_correct:
                correct += 1
                if cat:
                    category_stats[cat]['correct'] += 1
            if q.get('explanation'):
                level = Fore.GREEN if is_correct else Fore.RED
                print(level + f"Explanation: {q['explanation']}" + Style.RESET_ALL + '\n')
            
            expected_answer = q.get('assert_script', '')
            log_user_answer = (user_yaml_str[:200] + '...') if len(user_yaml_str) > 200 else user_yaml_str
            log_expected_answer = (expected_answer[:200] + '...') if len(expected_answer) > 200 else expected_answer
            logger.info(f"Question {asked}/{max_q}: type={q_type} prompt=\"{q['prompt']}\" expected=\"{log_expected_answer}\" answer=\"{log_user_answer}\" result=\"{'correct' if is_correct else 'incorrect'}\"")

        elif q_type == 'yaml_edit':
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
            is_correct = ans == q['response']
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
        
        # Ask to flag for review
        try:
            review = input("Flag this question for review? [y/N]: ").strip().lower()
            if review.startswith('y'):
                mark_question_for_review(data_file, q['category'], q['prompt'])
                print(Fore.MAGENTA + "Question flagged for review." + Style.RESET_ALL + '\n')
            else:
                print() # newline
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
    """Run YAML editing questions with semantic validation"""
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading data: {e}")
        return
    
    editor = VimYamlEditor()
    
    # Filter for yaml_edit questions
    yaml_questions = []
    for section in data:
        for item in section.get('prompts', []):
            if item.get('question_type') == 'yaml_edit':
                yaml_questions.append(item)
    
    if not yaml_questions:
        print("No YAML editing questions available in data file.")
        return
    
    print(f"\n{Fore.CYAN}=== Kubelingo YAML Editing Mode ==={Style.RESET_ALL}")
    print(f"Found {len(yaml_questions)} YAML editing exercises")
    print(f"Editor: {os.environ.get('EDITOR', 'vim')}")
    
    correct_count = 0
    
    for i, question in enumerate(yaml_questions, 1):
        print(f"\n{Fore.YELLOW}=== Exercise {i}/{len(yaml_questions)} ==={Style.RESET_ALL}")
        print(f"Category: {question.get('category', 'General')}")
        
        success = editor.run_yaml_edit_question(question, i)
        if success:
            correct_count += 1
        
        if i < len(yaml_questions):
            if input(f"\n{Fore.CYAN}Continue to next exercise? (y/n): {Style.RESET_ALL}").lower() != 'y':
                break
    
    # Show final results
    print(f"\n{Fore.CYAN}=== YAML Editing Session Complete ==={Style.RESET_ALL}")
    print(f"Completed: {correct_count}/{i} exercises")
    percentage = (correct_count / i * 100) if i > 0 else 0
    print(f"Success rate: {percentage:.1f}%")

def main():
    parser = argparse.ArgumentParser(description='Kubelingo: Interactive kubectl and YAML quiz tool')
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
    parser.add_argument('--yaml-exercises', '--yaml-edit', dest='yaml_exercises', action='store_true',
                        help='Run YAML editing exercises with semantic validation')
    parser.add_argument('--vim-quiz', action='store_true',
                        help='Run Vim commands quiz')
    
    args = parser.parse_args()
    
    # Handle special modes first
    if args.history:
        show_history()
        sys.exit(0)
    
    if args.vim_quiz:
        from modules.vim_yaml_editor import vim_commands_quiz
        score = vim_commands_quiz()
        print(f"\nVim Quiz completed with {score:.1%} accuracy")
        sys.exit(0)
    
    if getattr(args, 'yaml_exercises', False):
        # Run YAML editing exercises from dedicated data file
        run_yaml_editing_mode(YAML_QUESTIONS_FILE)
        sys.exit(0)
    
    # Continue with existing quiz logic...
    questions = load_questions(args.file)
    
    if args.list_categories:
        cats = sorted({q['category'] for q in questions})
        for cat in cats:
            print(cat)
        sys.exit(0)
    
    # Rest of existing main() function continues unchanged... (omitted for brevity)

if __name__ == '__main__':
    main()
