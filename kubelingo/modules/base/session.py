"""
Base interface for study sessions.
"""
import abc

class StudySession(abc.ABC):
    """
    Abstract base class for a study session module.
    """
    @abc.abstractmethod
    def initialize(self):
        """Perform any setup or initialization steps."""
        pass

    @abc.abstractmethod
    def run_exercises(self):
        """Execute the exercises for this session."""
        pass

    @abc.abstractmethod
    def cleanup(self):
        """Cleanup any resources after the session completes."""
        pass