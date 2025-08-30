import os
import time
import yaml
from colorama import Fore, Style

from kubelingo.utils import USER_DATA_DIR, ISSUES_FILE, MISSED_QUESTIONS_FILE, QUESTIONS_DIR, ensure_user_data_dir

def get_normalized_question_text(question_dict):
    return question_dict.get('question', '').strip().lower()

def remove_question_from_list(list_file, question):
    """Removes a question from a specified list file."""
    ensure_user_data_dir()
    questions = []
    # Attempt to load existing questions, but ignore file errors or invalid YAML
    try:
        if os.path.exists(list_file):
            with open(list_file, 'r') as f:
                try:
                    data = yaml.safe_load(f)
                except yaml.YAMLError:
                    data = []
            # Only accept a list; otherwise reset to empty
            if isinstance(data, list):
                questions = data
            else:
                questions = []
    except (OSError, IOError):
        questions = []

    normalized_question_to_remove = get_normalized_question_text(question)
    updated_questions = [q for q in questions if get_normalized_question_text(q) != normalized_question_to_remove]

    with open(list_file, 'w') as f:
        yaml.dump(updated_questions, f)

def create_issue(question_dict, topic):
    """Prompts user for an issue and saves it to a file."""
    # Directory creation not required for issue reporting
    # Use configured issues file path
    issues_file = ISSUES_FILE
    print("\nPlease describe the issue with the question.")
    issue_desc = input("Description: ")
    if issue_desc.strip():
        new_issue = question_dict.copy()
        new_issue['issue'] = issue_desc.strip()
        new_issue['timestamp'] = time.asctime()
        # Include topic in issue record
        new_issue['topic'] = topic

        issues = []
        if os.path.exists(issues_file):
            try:
                with open(issues_file, 'r') as f:
                    raw = yaml.safe_load(f)
            except (yaml.YAMLError, OSError, IOError):
                raw = []
            # Only accept a list; otherwise reset
            if isinstance(raw, list):
                issues = raw
            else:
                issues = []
        issues.append(new_issue)

        with open(issues_file, 'w') as f:
            yaml.dump(issues, f)
        
        # Remove the question from the topic file in QUESTIONS_DIR
        topic_file = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
        try:
            from pathlib import Path
            if Path(topic_file).exists():
                with open(topic_file, 'r') as f:
                    data = yaml.safe_load(f) or {'questions': []}
                if 'questions' in data:
                    data['questions'] = [q for q in data['questions'] if get_normalized_question_text(q) != get_normalized_question_text(question_dict)]
                with open(topic_file, 'w') as f:
                    yaml.dump(data, f)
        except Exception:
            pass

        # If a question is flagged with an issue, remove it from the missed questions list
        remove_question_from_list(MISSED_QUESTIONS_FILE, question_dict)

        print("\nIssue reported. Thank you!")
    else:
        print("\nIssue reporting cancelled.")
