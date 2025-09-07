import pytest
import kubelingo.cli as cli
from InquirerPy import inquirer


class FakeAnswer:
    """Mimics InquirerPy answer object for testing."""
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


