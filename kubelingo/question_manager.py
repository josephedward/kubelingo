import os
import yaml
import webbrowser
from kubelingo.utils import USER_DATA_DIR, MISSED_QUESTIONS_FILE, ensure_user_data_dir
from kubelingo.utils import PERFORMANCE_FILE
from kubelingo.performance_tracker import save_performance_data
import kubelingo.issue_manager as im
from kubelingo.source_manager import get_source_for_kind

def mark_correct(session, question, performance_data, get_norm_fn):
    """Mark a question as correct and persist performance data."""
    session.update_performance(question, True, get_norm_fn)
    save_performance_data(performance_data)
    print("\n✔ Question marked correct and saved to performance data.")

def mark_incorrect(question, topic):
    """Mark a question as incorrect, adding it to the missed questions list."""
    ensure_user_data_dir()
    # Append to missed questions
    missed = []
    if os.path.exists(MISSED_QUESTIONS_FILE):
        try:
            with open(MISSED_QUESTIONS_FILE) as f:
                missed = yaml.safe_load(f) or []
        except Exception:
            missed = []
    # Avoid duplicates
    norm_q = question.get('question','').strip().lower()
    if not any(q.get('question','').strip().lower() == norm_q for q in missed):
        new_q = question.copy()
        new_q['original_topic'] = topic
        missed.append(new_q)
        with open(MISSED_QUESTIONS_FILE, 'w') as f:
            yaml.dump(missed, f)
        print("\n✖ Question added to missed questions.")

def mark_revisit(question, topic):
    """Flag a question for revisit via issue_manager, without deleting it."""
    im.create_issue(question, topic)
    print("\n♻ Question flagged for revisit and recorded in issues.")

def mark_delete(question, topic):
    """Delete a question from the corpus entirely."""
    # Remove from topic file
    from kubelingo.kubelingo import remove_question_from_corpus
    remove_question_from_corpus(question, topic)
    print("\n🗑 Question deleted from corpus and will not appear again.")

def open_source(question):
    """Open the question's source URL in the default browser."""
    src = question.get('source') or get_source_for_kind(question.get('requirements',{}).get('kind',''))
    if src:
        print(f"\n🔗 Opening source: {src}")
        try:
            webbrowser.open(src)
        except Exception as e:
            print(f"Error opening browser: {e}")
    else:
        print("No source available for this question.")

def show_menu():
    """Display the vertical post-answer menu options."""
    menu = [
        "A) Again (add to retry)",
        "F) Forward (next question)",
        "B) Backward (previous question)",
        "C) Correct (mark as correct)",
        "I) Incorrect (mark as missed)",
        "R) Revisit (flag issue)",
        "D) Delete question", 
        "V) Visit source", 
        "S) Settings", 
        "Q) Quit app"
    ]
    print("\n" + "\n".join(menu))