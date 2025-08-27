import os
import time
import yaml
from colorama import Fore, Style

# Assuming USER_DATA_DIR and ISSUES_FILE are defined elsewhere or passed in
# For now, let's define them here, but they might need to be imported from utils or kubelingo.py
USER_DATA_DIR = "user_data"
ISSUES_FILE = os.path.join(USER_DATA_DIR, "issues.yaml")
MISSED_QUESTIONS_FILE = os.path.join(USER_DATA_DIR, "missed_questions.yaml")
QUESTIONS_DIR = "questions"

def ensure_user_data_dir():
    """Ensures the user_data directory exists."""
    os.makedirs(USER_DATA_DIR, exist_ok=True)

def get_normalized_question_text(question_dict):
    return question_dict.get('question', '').strip().lower()

def remove_question_from_list(list_file, question):
    """Removes a question from a specified list file."""
    ensure_user_data_dir()
    questions = []
    if os.path.exists(list_file):
        with open(list_file, 'r') as f:
            try:
                questions = yaml.safe_load(f) or []
            except yaml.YAMLError:
                questions = []

    normalized_question_to_remove = get_normalized_question_text(question)
    updated_questions = [q for q in questions if get_normalized_question_text(q) != normalized_question_to_remove]

    with open(list_file, 'w') as f:
        yaml.dump(updated_questions, f)

def create_issue(question_dict, topic):
    """Prompts user for an issue and saves it to a file."""
    ensure_user_data_dir()
    # Dynamically determine issues file based on current user data directory
    issues_file = os.path.join(USER_DATA_DIR, "issues.yaml")
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
            with open(issues_file, 'r') as f:
                try:
                    issues = yaml.safe_load(f) or []
                except yaml.YAMLError:
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
