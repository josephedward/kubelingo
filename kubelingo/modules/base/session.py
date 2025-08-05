import json
import os
import os.path
try:
    import yaml
except ImportError:
    yaml = None

from kubelingo.utils.config import HISTORY_FILE, FLAGGED_QUESTIONS_FILE
from kubelingo.utils.ui import Fore, Style


class SessionManager:
    """Manages session state like history and review flags."""

    def __init__(self, logger):
        self.logger = logger
        # Initialize flagged question ID store
        self.flagged_file = FLAGGED_QUESTIONS_FILE
        try:
            with open(self.flagged_file, 'r') as f:
                data = json.load(f)
                self.flagged_ids = set(data) if isinstance(data, list) else set()
        except Exception:
            self.flagged_ids = set()

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

    def _update_review_status(self, question_id: str, review: bool):
        """Sets or removes the review flag for a given question ID in its source YAML."""
        if yaml is None:
            self.logger.error("Cannot update review status: PyYAML not installed")
            return

        try:
            module, _ = question_id.split('::', 1)
        except (ValueError, IndexError):
            self.logger.error(f"Invalid question ID format for review flagging: {question_id}")
            return

        # Derive the expected path in question-data/yaml
        data_file = os.path.join(DATA_DIR, 'yaml', f"{module}.yaml")

        if not os.path.exists(data_file):
            self.logger.error(f"Could not find source file for question {question_id}: {data_file}")
            return

        try:
            with open(data_file, 'r') as f:
                questions = yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"Error opening YAML file for review flagging: {e}")
            return

        if not isinstance(questions, list):
            self.logger.error(f"Invalid format in {data_file}: expected a list of questions.")
            return

        question_found = False
        changed = False
        for item in questions:
            if isinstance(item, dict) and item.get('id') == question_id:
                question_found = True
                if review:
                    if not item.get('review'):
                        item['review'] = True
                        changed = True
                else:  # unflag
                    if 'review' in item:
                        del item['review']
                        changed = True
                break
        
        if not question_found:
            self.logger.error(f"Question with ID {question_id} not found in {data_file}")
            return

        if not changed:
            return

        try:
            with open(data_file, 'w') as f:
                yaml.safe_dump(questions, f, sort_keys=False)
        except Exception as e:
            self.logger.error(f"Error writing YAML file when updating review status: {e}")

    def mark_question_for_review(self, question_id: str):
        """Adds 'review': True to the matching question in its source YAML file."""
        self._update_review_status(question_id, review=True)

    def unmark_question_for_review(self, question_id: str):
        """Removes 'review' flag from the matching question in its source YAML file."""
        self._update_review_status(question_id, review=False)

    # New id-based flagging logic (overrides legacy file-based methods)
    def mark_question_for_review(self, question_id):
        """Record a question ID for review."""
        self.flagged_ids.add(question_id)
        self._save_flagged_file()

    def unmark_question_for_review(self, question_id):
        """Remove a question ID from review flags."""
        if question_id in self.flagged_ids:
            self.flagged_ids.remove(question_id)
            self._save_flagged_file()

    def _save_flagged_file(self):
        """Persist the current set of flagged question IDs to disk."""
        try:
            os.makedirs(os.path.dirname(self.flagged_file), exist_ok=True)
            with open(self.flagged_file, 'w') as f:
                json.dump(sorted(self.flagged_ids), f, indent=2)
        except Exception as e:
            print(Fore.RED + f"Error saving review flags: {e}" + Style.RESET_ALL)
    
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
