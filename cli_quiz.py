#!/usr/bin/env python3
"""
cli_quiz.py: A simple CLI tool to quiz commands (or other strings) based on supplied JSON data.
"""
import json
import random
import argparse
import sys
import datetime
# OS utilities
import os
import shutil
import subprocess
import logging
from datetime import datetime

# Interactive prompts library (optional for arrow-key selection)
try:
    import questionary
except ImportError:
    questionary = None

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
DEFAULT_DATA_FILE = 'ckad_quiz_data.json'
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
            questions.append({
                'category': category,
                'prompt': item.get('prompt', ''),
                'response': item.get('response', ''),
                'explanation': item.get('explanation', '')
            })
    return questions

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
        data_file = entry.get('data_file', '')
        filt = entry.get('category_filter') or 'ALL'
        print(f"{ts}: {nc}/{nq} ({pct:.1f}%), File: {data_file}, Category: {filt}")
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

def main():
    parser = argparse.ArgumentParser(description='kubectl quiz tool')
    parser.add_argument('-f', '--file', type=str, default=DEFAULT_DATA_FILE,
                        help='Path to quiz data JSON file')
    parser.add_argument('-n', '--num', type=int, default=0,
                        help='Number of questions to ask (default: all)')
    parser.add_argument('-c', '--category', type=str,
                        help='Limit quiz to a specific category')
    parser.add_argument('--list-categories', action='store_true',
                        help='List available categories and exit')
    parser.add_argument('--history', action='store_true',
                        help='Show quiz history and statistics')
    args = parser.parse_args()
    # If history flag is set, display history and exit
    if args.history:
        show_history()
        sys.exit(0)

    # Select quiz data JSON file (via arrow-key UI if available)
    if questionary:
        json_files = sorted([f for f in os.listdir('.') if f.lower().endswith('.json')])
        if json_files:
            choices = json_files + ["Enter custom path"]
            default_choice = args.file if args.file in json_files else None
            selected = questionary.select("Select quiz data file:", choices=choices, default=default_choice).ask()
            if selected is None:
                sys.exit(0)
            if selected == "Enter custom path":
                path = questionary.text(
                    f"Enter JSON quiz data file path (default: {args.file})", default=args.file
                ).ask()
                args.file = path.strip() if path and path.strip() else args.file
            else:
                args.file = selected
        else:
            # No JSON files found, prompt for path
            path = questionary.text(
                f"Enter JSON quiz data file path (default: {args.file})", default=args.file
            ).ask()
            args.file = path.strip() if path and path.strip() else args.file
    else:
        # Fallback to manual input if questionary unavailable
        try:
            user_input = input(f"Enter path to JSON quiz data file (default: {args.file}): ").strip()
        except EOFError:
            print()  # newline on EOF
            user_input = ''
        if user_input:
            args.file = user_input

    questions = load_questions(args.file)
    if args.list_categories:
        cats = sorted({q['category'] for q in questions})
        for cat in cats:
            print(cat)
        sys.exit(0)

    if args.category:
        questions = [q for q in questions if q['category'] == args.category]
        if not questions:
            print(f"No questions found for category '{args.category}'")
            sys.exit(1)

    total = len(questions)
    if total == 0:
        print('No questions available.')
        sys.exit(1)

    random.shuffle(questions)
    max_q = args.num if args.num > 0 else total
    correct = 0
    asked = 0
    # Track per-category performance for this session
    category_stats = {}
    # Setup session logging
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = os.path.join(log_dir, f'quiz_{timestamp}.log')
    logger = logging.getLogger('quiz_logger')
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_path)
    fh.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    logger.addHandler(fh)
    logger.info(f"Session start: data_file={args.file}, num_questions={max_q}, category={args.category}")
    # Check OpenAI API key and prompt for it if not set
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        try:
            key_input = input(
                Fore.YELLOW +
                "OpenAI API key not set. Enter your OpenAI API key now "
                "(or press Enter to skip and proceed without LLM support): " +
                Style.RESET_ALL
            ).strip()
        except EOFError:
            print()  # newline on EOF
            key_input = ''
        if key_input:
            os.environ['OPENAI_API_KEY'] = key_input
            api_key = key_input
        else:
            print(Fore.YELLOW +
                  "Warning: OPENAI_API_KEY not set; LLM queries disabled." +
                  Style.RESET_ALL)
    # Determine LLM availability for detailed explanations
    if api_key:
        if shutil.which('llm'):
            llm_enabled = True
        else:
            print(Fore.YELLOW +
                  "Warning: LLM CLI 'llm' not found; intelligent explanations disabled." +
                  Style.RESET_ALL)
            llm_enabled = False
    else:
        llm_enabled = False
    for q in questions[:max_q]:
        asked += 1
        # Update per-category stats
        cat = q.get('category', '')
        stats = category_stats.setdefault(cat, {'asked': 0, 'correct': 0})
        stats['asked'] += 1
        print(f"[{asked}/{max_q}] Category: {q['category']}\nQ: {q['prompt']}")
        try:
            ans = input('Your answer: ').strip()
        except EOFError:
            print()  # newline
            break
        if ans == q['response']:
            # Correct answer feedback
            print(Fore.GREEN + 'Correct!' + Style.RESET_ALL + '\n')
            correct += 1
            # Update per-category correct count
            stats['correct'] += 1
            # Show explanation if available
            if q.get('explanation'):
                print(Fore.GREEN + f"Explanation: {q['explanation']}" + Style.RESET_ALL + '\n')
        else:
            # Incorrect answer feedback
            print(Fore.RED + f"Incorrect. Correct answer: {q['response']}" + Style.RESET_ALL + '\n')
            # Show explanation if available
            if q.get('explanation'):
                print(Fore.RED + f"Explanation: {q['explanation']}" + Style.RESET_ALL + '\n')
        # Log question result
        logger.info(f"Question {asked}/{max_q}: prompt=\"{q['prompt']}\" expected=\"{q['response']}\" answer=\"{ans}\" result=\"{'correct' if ans == q['response'] else 'incorrect'}\"")
        # Offer optional LLM query for further explanation
        if llm_enabled:
            try:
                ans_llm = input(Fore.CYAN + "Show detailed LLM explanation? [y/N]: " + Style.RESET_ALL).strip().lower()
            except EOFError:
                ans_llm = ''
            if ans_llm == 'y':
                # Construct a focused LLM prompt explaining the answer relative to the question
                llm_prompt = (
                    f"Explain why the command \"{q['response']}\" is the correct solution "
                    f"to the question: \"{q['prompt']}\"."
                )
                try:
                    result = subprocess.run(
                        ["llm", llm_prompt], capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        print(Fore.MAGENTA + result.stdout + Style.RESET_ALL)
                    else:
                        print(Fore.RED + f"LLM call failed (exit {result.returncode}): {result.stderr}" + Style.RESET_ALL)
                except FileNotFoundError:
                    print(Fore.RED + "LLM CLI tool 'llm' not found. Please install to use this feature." + Style.RESET_ALL)
        # End of question loop actions
    if asked:
        print(f"Quiz complete. Score: {correct}/{asked} ({correct/asked*100:.1f}%)")
        # Show performance by subject area for this session
        print("Performance by category:")
        for cat, stats in category_stats.items():
            c_asked = stats.get('asked', 0)
            c_correct = stats.get('correct', 0)
            pct = (c_correct / c_asked * 100) if c_asked else 0
            print(f"  {cat}: {c_correct}/{c_asked} ({pct:.1f}%)")
        # Record session history
        try:
            # Load existing history
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r') as f_hist:
                    history = json.load(f_hist)
            else:
                history = []
            # Append new entry
            entry = {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'data_file': args.file,
                'category_filter': args.category,
                'num_questions': asked,
                'num_correct': correct,
                'per_category': category_stats
            }
            history.append(entry)
            with open(HISTORY_FILE, 'w') as f_hist:
                json.dump(history, f_hist, indent=2)
        except Exception as e:
            print(f"Warning: could not record quiz history: {e}")
    else:
        print('No questions answered.')

if __name__ == '__main__':
    main()