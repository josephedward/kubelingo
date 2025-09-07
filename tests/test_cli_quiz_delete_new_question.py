import pytest
from InquirerPy import inquirer

import kubelingo.cli as cli
import builtins

class DummyPrompt:
    """Mimics InquirerPy prompt responses."""
    def __init__(self, value):
        self._value = value
    def execute(self):
        return self._value

@pytest.fixture
def mock_ai_chat(monkeypatch):
    """Stub ai_chat to return two distinct True/False questions in sequence."""
    responses = [
        '{"type":"tf","question":"Q1 question?","answer":"true"}',
        '{"type":"tf","question":"Q2 question?","answer":"true"}'
    ]
    def _mock_ai(system_prompt, user_prompt=None):
        return responses.pop(0)
    monkeypatch.setattr(cli, 'ai_chat', _mock_ai)
    return _mock_ai

def test_delete_generates_new_question(monkeypatch, capsys, mock_ai_chat):
    """Deleting a question should trigger a new, different AI-generated question."""
    # Sequence of select inputs: quiz type, topic, difficulty, count, post-answer action (delete)
    selects = iter([
        'Quiz',        # Main Menu: Quiz
        'True/False',  # Quiz type
        'pods',        # Topic
        'beginner',    # Difficulty
        'delete'       # Post-answer menu action
    ])
    monkeypatch.setattr(inquirer, 'select', lambda message, choices, default=None, style=None: DummyPrompt(next(selects)))
    # Sequence of text inputs: number of questions, user answer, then quit to end session
    texts = iter([
        '1',           # Number of questions
        'wrong',       # User answer
        'quit'         # Quit quiz session
    ])
    monkeypatch.setattr(inquirer, 'text', lambda message: DummyPrompt(next(texts)))
    input_choices = iter([
        'a', # Answer the question
        'q'  # Quit the quiz session
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))
    # Mock QuestionGenerator._generate_question_id to return a fixed ID
    monkeypatch.setattr(cli.QuestionGenerator, "_generate_question_id", lambda self: "test_id")
    # Run the quiz session
    cli.quiz_menu()
    out = capsys.readouterr().out
    # Both generated questions should appear in output
    assert 'Q1 question?' in out, "First question was not presented"
    assert 'Q2 question?' in out, "Second question (after delete) was not presented"