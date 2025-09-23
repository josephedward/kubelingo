import os
import yaml
import webbrowser
from kubelingo.utils import USER_DATA_DIR, MISSED_QUESTIONS_FILE, ensure_user_data_dir, get_canonical_question_representation
from kubelingo.performance_tracker import save_performance_data
from kubelingo.source_manager import get_source_for_kind
from kubelingo.schema import write_question_file, normalize_question_dict

def mark_correct(session, question, performance_data, get_norm_fn):
    """Mark a question as correct and persist performance data."""
    session.update_performance(question, True, get_norm_fn)
    save_performance_data(performance_data)
    print("\n✔ Question marked correct and saved to performance data.")
    # Append to correct questions file
    ensure_user_data_dir()
    correct_questions = []
    if os.path.exists(CORRECT_QUESTIONS_FILE):
        try:
            with open(CORRECT_QUESTIONS_FILE, 'r') as f:
                correct_questions = yaml.safe_load(f) or []
        except Exception:
            correct_questions = []
    
    norm_q = normalize_question_dict(question)
    canonical_q = get_canonical_question_representation(norm_q)

    if not any(get_canonical_question_representation(q) == canonical_q for q in correct_questions):
        correct_questions.append(norm_q)
        with open(CORRECT_QUESTIONS_FILE, 'w') as f:
            yaml.dump(correct_questions, f, sort_keys=False)
        print("✔ Question added to correct questions file.")
    else:
        print("✔ Question already in correct questions file.")

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
    # Append to incorrect questions file
    ensure_user_data_dir()
    incorrect_questions = []
    if os.path.exists(INCORRECT_QUESTIONS_FILE):
        try:
            with open(INCORRECT_QUESTIONS_FILE, 'r') as f:
                incorrect_questions = yaml.safe_load(f) or []
        except Exception:
            incorrect_questions = []
    
    norm_q = normalize_question_dict(question, topic)
    canonical_q = get_canonical_question_representation(norm_q)

    if not any(get_canonical_question_representation(q) == canonical_q for q in incorrect_questions):
        incorrect_questions.append(norm_q)
        with open(INCORRECT_QUESTIONS_FILE, 'w') as f:
            yaml.dump(incorrect_questions, f, sort_keys=False)
        print("✖ Question added to incorrect questions file.")
    else:
        print("✖ Question already in incorrect questions file.")

## revisit removed per requirements

def mark_delete(question, topic):
    """Delete a question from the corpus entirely."""
    # Remove from topic file
    from .utils import remove_question_from_corpus
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
    # Deprecated in favor of show_post_answer_menu; kept for backward compatibility
    show_post_answer_menu()

def show_question_menu(manifest_capable: bool = False, is_trivia: bool = False):
    """Display the menu immediately after showing a question (pre-answer).

    Canonical options per requirements (with current key behavior):
      e)dit, n)ext, p)revious, v)iew answer, s)ource, q)uit
    """
    items = []
    if manifest_capable:
        items.append("e)dit (vim)")
    items.extend([
        "n)ext",
        "p)revious",
        "v)iew answer",
        "s)ource",
        "q)uit",
    ])
    if is_trivia:
        print("\n(Enter your answer directly, or choose an option below)")
    elif manifest_capable:
        print("\n(Press 'e' to edit/answer the manifest, or choose an option below)")
    else:
        print("\n(Enter your command, or choose an option below)")
    print("\n" + "\n".join(items))

def show_post_answer_menu():
    """Display the menu immediately after an answer is graded.

    Canonical options per requirements: r)etry, c)orrect, m)issed, d)elete question
    """
    menu = [
        "r) retry",
        "c) correct",
        "m) missed",
        "d) delete question",
    ]
    print("\n" + "\n".join(menu))
