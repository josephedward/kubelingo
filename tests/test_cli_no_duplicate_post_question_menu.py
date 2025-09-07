import pytest
import kubelingo.cli as cli


class DummyAnswer:
    """Simple dummy prompt for InquirerPy-like interface."""
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


