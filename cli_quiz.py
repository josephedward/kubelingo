#!/usr/bin/env python3
"""
cli_quiz.py: A simple CLI tool to quiz commands (or other strings) based on supplied JSON data.
"""
import json
import random
import argparse
import sys

# Default quiz data file path
DEFAULT_DATA_FILE = 'ckad_quiz_data.json'

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
            })
    return questions

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
    args = parser.parse_args()

    # Prompt user for quiz data JSON file path (override -f/--file)
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
    for q in questions[:max_q]:
        asked += 1
        print(f"[{asked}/{max_q}] Category: {q['category']}\nQ: {q['prompt']}")
        try:
            ans = input('Your answer: ').strip()
        except EOFError:
            print()  # newline
            break
        if ans == q['response']:
            print('Correct!\n')
            correct += 1
        else:
            print(f"Incorrect. Correct answer: {q['response']}\n")
    if asked:
        print(f"Quiz complete. Score: {correct}/{asked} ({correct/asked*100:.1f}%)")
    else:
        print('No questions answered.')

if __name__ == '__main__':
    main()