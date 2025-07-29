"""
BaseLoader defines the interface for question-data loaders.
"""
from abc import ABC, abstractmethod
from typing import List
from kubelingo.question import Question

class BaseLoader(ABC):
    @abstractmethod
    def discover(self) -> List[str]:
        """Return a list of file paths this loader can load."""
        pass

    @abstractmethod
    def load_file(self, path: str) -> List[Question]:
        """Parse the file at `path` and return a list of Question objects."""
        pass