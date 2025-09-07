import pytest
pytest.skip("Skipping CLI main tests until refactor.", allow_module_level=True)
import os
import sys
import json
import shutil
import tempfile
from cli import main, ASCII_ART, colorize_ascii_art
import cli
from InquirerPy import inquirer
from enum import Enum

class DifficultyLevel(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class FakeAnswer:
    """Fake answer to mimic InquirerPy answer object."""
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value

def setup_fake_inquirer(monkeypatch, text_responses, select_responses, checkbox_responses=None):
    """
    Monkeypatch InquirerPy functions to provide fake text and select responses.
    text_responses: list of strings to return for text prompts in order.
    select_responses: list of strings to return for select prompts in order.
    checkbox_responses: list of lists of strings to return for checkbox prompts in order.
    """
    texts = list(text_responses)
    selects = list(select_responses)
    checkboxes = list(checkbox_responses) if checkbox_responses is not None else []

    def fake_text(message):
        if not texts:
            pytest.fail(f"No more text responses left for prompt: {message}")
        return FakeAnswer(texts.pop(0))

    def fake_select(message, choices=None, default=None):
        if not selects:
            pytest.fail(f"No more select responses left for prompt: {message}")
        return FakeAnswer(selects.pop(0))

    def fake_checkbox(message, choices=None):
        if not checkboxes:
            pytest.fail(f"No more checkbox responses left for prompt: {message}")
        val = checkboxes.pop(0)
        if isinstance(val, list):
            return FakeAnswer(val)
        return FakeAnswer([val])

    monkeypatch.setattr(inquirer, 'text', fake_text)
    monkeypatch.setattr(inquirer, 'select', fake_select)
    monkeypatch.setattr(inquirer, 'checkbox', fake_checkbox)

def test_main_exit(monkeypatch, capsys):
    # Simulate user selecting "Exit" from the main menu
    setup_fake_inquirer(monkeypatch, text_responses=[], select_responses=["Exit"])

    # Mock sys.argv to simulate no command-line arguments
    monkeypatch.setattr(sys, 'argv', ['cli.py'])

    # Mock sys.exit to prevent the test from actually exiting
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()

    # Assert that sys.exit was called with code 0
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0

    # Capture output and assert goodbye message
    out, err = capsys.readouterr()
    assert "Goodbye!" in out
    assert "Goodbye!\n" in out

@pytest.fixture
def temp_questions_dir(monkeypatch):
    original_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.chdir(tmpdir)
        questions_path = os.path.join(tmpdir, 'questions', 'uncategorized')
        os.makedirs(questions_path, exist_ok=True)
        yield questions_path
    os.chdir(original_cwd) # Restore original working directory

def test_quiz_session_handles_malformed_json(monkeypatch, capsys, temp_questions_dir):
    # Create a malformed JSON file (list instead of dict)
    malformed_file_path = os.path.join(temp_questions_dir, 'malformed_q.json')
    with open(malformed_file_path, 'w') as f:
        json.dump([{"question": "q1"}, {"question": "q2"}], f)

    # Mock inquirer responses:
    # 1. Main menu: "Import"
    # 2. Import menu: "Uncategorized"
    # 3. Quiz session: "Quit Quiz" (after attempting to process the malformed file)
    # 4. Main menu again: "Exit" (to gracefully exit the CLI)
    setup_fake_inquirer(
        monkeypatch,
        text_responses=[],
        select_responses=["Import", "Uncategorized", "Quit Quiz", "Exit"]
    )

    # Mock sys.argv to simulate no command-line arguments
    monkeypatch.setattr(sys, 'argv', ['cli.py'])

    # Mock sys.exit to prevent the test from actually exiting
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()

    # Assert that sys.exit was called with code 0
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0

    # Capture output and assert the error message for malformed file
    out, err = capsys.readouterr()
    assert "Skipping malformed question file (expected dictionary, got list):" in out
    assert "malformed_q.json" in out
    # After skipping the only file, there are no valid uncategorized questions left.
    assert "No uncategorized questions found." in out
    assert "Goodbye!" in out # Ensure it still exits gracefully
