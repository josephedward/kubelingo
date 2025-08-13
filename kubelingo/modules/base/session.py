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

from kubelingo.utils.config import HISTORY_FILE
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

    def run_exercises(self, args):
        """
        Runs a quiz session based on the provided arguments.
        This has been refactored to accept a list of pre-loaded Question objects.
        """
        questions = getattr(args, 'exercises', [])
        if not questions:
            print(f"{Fore.YELLOW}No questions to run for this session.{Style.RESET_ALL}")
            return
        
        # This is where the quiz loop logic would go.
        # It would iterate through `questions`, present them to the user,
        # check answers, and track stats.
        # For now, as a placeholder to show the data flow is working,
        # we will just print the questions that were passed in.
        print(f"\n{Fore.CYAN}--- Starting Quiz Session ---{Style.RESET_ALL}")
        print(f"Found {len(questions)} question(s) to ask.")
        
        for i, q in enumerate(questions, 1):
            print(f"\n{i}. ID: {q.id} (from: {os.path.basename(q.source_file)})")
            print(f"   Prompt: {q.prompt}")
        
        print(f"\n{Fore.GREEN}--- Quiz Session Finished ---{Style.RESET_ALL}")
        print("(Note: Full interactive quiz logic is not yet implemented in this refactoring.)")


    def cleanup(self):
        """Cleans up any session-related resources."""
        pass
