class StudySession:
    """Base class for a study session for a specific subject."""

    def __init__(self, logger):
        """
        Initializes the study session.
        :param logger: A logger instance for logging session activities.
        """
        self.logger = logger

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
