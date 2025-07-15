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
    from vim_yaml_editor import VimYamlEditor, vim_commands_quiz
except ImportError:
    print("Warning: vim_yaml_editor.py not found. YAML/Vim exercises will not be available.")
    VimYamlEditor = None
    vim_commands_quiz = None

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
    
    # If no yaml_edit questions found, use built-in samples
    if not yaml_questions:
        print("No YAML editing questions found in data file. Using built-in examples.")
        yaml_questions = create_yaml_edit_questions()
    
    if not yaml_questions:
        print("No YAML editing questions available.")
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
                        help='Path to quiz data JSON file')
    parser.add_argument('-n', '--num', type=int, default=0,
                        help='Number of questions to ask (default: all)')
    parser.add_argument('-c', '--category', type=str,
                        help='Limit quiz to a specific category')
    parser.add_argument('--list-categories', action='store_true',
                        help='List available categories and exit')
    parser.add_argument('--history', action='store_true',
                        help='Show quiz history and statistics')
    parser.add_argument('--yaml-edit', action='store_true',
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
    
    if args.yaml_edit:
        run_yaml_editing_mode(args.file)
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
    if len(sys.argv) >= 2 and sys.argv[1] in ('edit', 'run'):
        if len(sys.argv) < 3:
            print("Usage: cli_quiz.py edit <question_id>")
            sys.exit(1)
        run_edit_question(sys.argv[2])
    else:
        main()
