import json
import os
import os.path
try:
    import yaml
except ImportError:
    yaml = None

try:
    import questionary
except ImportError:
    questionary = None

from kubelingo.modules.kubernetes.study_mode import KubernetesStudyMode
from kubelingo.utils.config import HISTORY_FILE, FLAGGED_QUESTIONS_FILE, DATA_DIR
from kubelingo.utils.ui import Fore, Style


class SessionManager:
    """Manages session state like history and review flags."""

    def __init__(self, logger):
        self.logger = logger

    def get_history(self):
        """Retrieves quiz history."""
        if not os.path.exists(HISTORY_FILE):
            return None
        try:
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
            if not isinstance(history, list):
                return []
            return history
        except Exception:
            return None

    def save_history(self, start_time, num_questions, num_correct, duration, args, per_category_stats):
        """Saves a quiz session's results to the history file."""
        data_file = getattr(args, 'file', None)
        new_history_entry = {
            'timestamp': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'num_questions': num_questions,
            'num_correct': num_correct,
            'duration': duration,
            'data_file': os.path.basename(data_file) if data_file else "interactive_session",
            'category_filter': getattr(args, 'category', None),
            'per_category': per_category_stats
        }

        history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    history_data = json.load(f)
                    if isinstance(history_data, list):
                        history = history_data
            except (json.JSONDecodeError, IOError):
                pass  # Start with fresh history if file is corrupt or unreadable

        history.insert(0, new_history_entry)

        try:
            with open(HISTORY_FILE, 'w') as f:
                json.dump(history, f, indent=2)
        except IOError as e:
            print(Fore.RED + f"Error saving quiz history: {e}" + Style.RESET_ALL)

    def _update_review_status(self, question_id: str, review: bool):
        """Updates the 'review' flag for a question in the SQLite database."""
        try:
            from kubelingo.database import update_review_status
            update_review_status(question_id, review)
        except Exception as e:
            self.logger.error(f"Failed to update review status in DB for QID {question_id}: {e}")

    def mark_question_for_review(self, question_id: str):
        """Adds 'review': True to the matching question in its source YAML file."""
        self._update_review_status(question_id, review=True)

    def unmark_question_for_review(self, question_id: str):
        """Removes 'review' flag from the matching question in its source YAML file."""
        self._update_review_status(question_id, review=False)

    def _update_triage_status(self, question_id: str, triage: bool):
        """Updates the 'triage' flag for a question in the SQLite database."""
        try:
            from kubelingo.database import update_triage_status
            update_triage_status(question_id, triage)
        except Exception as e:
            self.logger.error(f"Failed to update triage status in DB for QID {question_id}: {e}")

    def triage_question(self, question_id: str):
        """Marks a question for triage."""
        self._update_triage_status(question_id, triage=True)


class StudySession:
    """Base class for a study session for a specific subject."""

    def __init__(self, logger):
        """
        Initializes the study session.
        :param logger: A logger instance for logging session activities.
        """
        self.logger = logger
        self.session_manager = SessionManager(logger)

    def initialize(self):
        """
        Prepare the environment for exercises.
        This could involve setting up temporary infrastructure, credentials, etc.
        :return: True on success, False on failure.
        """
        raise NotImplementedError("Subclasses must implement initialize().")

    def run_exercises(self, exercises):
        """
        Run a list of exercises.
        :param exercises: A list of question/exercise objects.
        """
        raise NotImplementedError("Subclasses must implement run_exercises().")

    def cleanup(self):
        """
        Clean up any resources created during the session.
        This method should be idempotent.
        """
        raise NotImplementedError("Subclasses must implement cleanup().")


class KubernetesSession(StudySession):
    """A study session for all Kubernetes-related quizzes."""

    def __init__(self, logger):
        """Initializes the session with a logger."""
        super().__init__(logger)

    def initialize(self):
        """Initializes the Kubernetes session."""
        return True

    def run_exercises(self, exercises):
        """Runs an interactive study session."""
        if not os.getenv("GEMINI_API_KEY"):
            print("\nStudy Mode requires a Gemini API key.")
            print("Set the GEMINI_API_KEY environment variable to enable it.")
            print(
                "You can generate an API key in your Gemini account settings under 'API Keys'."
            )
            return

        if questionary is None:
            print(
                "\nThis feature requires the 'questionary' library for an interactive experience."
            )
            print("Please install it by running: pip install questionary")
            return

        try:
            # Delegate the entire interactive session to KubernetesStudyMode
            study_session = KubernetesStudyMode()
            study_session.main_menu()
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def cleanup(self):
        """Cleans up any session-related resources."""
        pass
