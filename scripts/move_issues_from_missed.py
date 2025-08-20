
import os
import yaml

USER_DATA_DIR = "/Users/user/Documents/GitHub/kubelingo/user_data"
ISSUES_FILE = os.path.join(USER_DATA_DIR, "issues.yaml")
MISSED_QUESTIONS_FILE = os.path.join(USER_DATA_DIR, "missed_questions.yaml")

def ensure_user_data_dir():
    os.makedirs(USER_DATA_DIR, exist_ok=True)

def get_normalized_question_text(question_dict):
    return question_dict.get('question', '').strip().lower()

def load_questions_from_list(list_file):
    if not os.path.exists(list_file):
        return []
    with open(list_file, 'r') as file:
        try:
            return yaml.safe_load(file) or []
        except yaml.YAMLError:
            return []

def save_questions_to_list(list_file, questions):
    ensure_user_data_dir()
    with open(list_file, 'w') as f:
        yaml.dump(questions, f)

def move_issues_from_missed():
    print("Loading issues from issues.yaml...")
    issues = load_questions_from_list(ISSUES_FILE)
    print(f"Found {len(issues)} issues.")

    print("Loading missed questions from missed_questions.yaml...")
    missed_questions = load_questions_from_list(MISSED_QUESTIONS_FILE)
    print(f"Found {len(missed_questions)} missed questions.")

    initial_missed_count = len(missed_questions)
    questions_removed_count = 0
    updated_missed_questions = []

    issue_question_texts = {get_normalized_question_text(issue) for issue in issues}

    for mq in missed_questions:
        if get_normalized_question_text(mq) in issue_question_texts:
            print(f"Removing missed question (flagged as issue): {mq.get('question')[:50]}...")
            questions_removed_count += 1
        else:
            updated_missed_questions.append(mq)

    if questions_removed_count > 0:
        print(f"Removed {questions_removed_count} questions from missed_questions.yaml.")
        save_questions_to_list(MISSED_QUESTIONS_FILE, updated_missed_questions)
        print("Updated missed_questions.yaml saved.")
    else:
        print("No questions flagged as issues found in missed questions. No changes made to missed_questions.yaml.")

    print("Process complete.")

if __name__ == "__main__":
    move_issues_from_missed()
