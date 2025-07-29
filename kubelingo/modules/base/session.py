import json
import os

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
        new_history_entry = {
            'timestamp': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'num_questions': num_questions,
            'num_correct': num_correct,
            'duration': duration,
            'data_file': os.path.basename(getattr(args, 'file', None)) or "interactive_session",
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

    def mark_question_for_review(self, data_file, category, prompt_text):
        """Adds 'review': True to the matching question in the JSON data file."""
        try:
            with open(data_file, 'r') as f:
                data = json.load(f)
        except Exception as e:
            self.logger.error(f"Error opening data file for review flagging: {e}")
            print(Fore.RED + f"Error opening data file for review flagging: {e}" + Style.RESET_ALL)
            return
        changed = False
        for section in data:
            if section.get('category') == category:
                # Support both 'questions' and 'prompts' keys.
                qs = section.get('questions', []) or section.get('prompts', [])
                for item in qs:
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
            self.logger.error(f"Error writing data file when flagging for review: {e}")
            print(Fore.RED + f"Error writing data file when flagging for review: {e}" + Style.RESET_ALL)

    def unmark_question_for_review(self, data_file, category, prompt_text):
        """Removes 'review' flag from the matching question in the JSON data file."""
        try:
            with open(data_file, 'r') as f:
                data = json.load(f)
        except Exception as e:
            self.logger.error(f"Error opening data file for un-flagging: {e}")
            print(Fore.RED + f"Error opening data file for un-flagging: {e}" + Style.RESET_ALL)
            return
        changed = False
        for section in data:
            if section.get('category') == category:
                # Support both 'questions' and 'prompts' keys.
                qs = section.get('questions', []) or section.get('prompts', [])
                for item in qs:
                    if item.get('prompt') == prompt_text and item.get('review'):
                        del item['review']
                        changed = True
                        break
            if changed:
                break
        if not changed:
            print(Fore.RED + f"Warning: flagged question not found in {data_file} to un-flag." + Style.RESET_ALL)
            return
        try:
            with open(data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error writing data file when un-flagging: {e}")
            print(Fore.RED + f"Error writing data file when un-flagging: {e}" + Style.RESET_ALL)


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
