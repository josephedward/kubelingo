import pytest
from InquirerPy import inquirer

import cli

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
    """Deleting a question should trigger a new, different trivia question."""
    # Sequence of select inputs: quiz type, topic, post-answer action (delete)
    selects = ['Trivia', 'pods', 'delete']
    monkeypatch.setattr(inquirer, 'select', lambda *args, **kwargs: DummyPrompt(selects.pop(0)))
    # Sequence of text inputs: first answer, then quit to end session
    texts = ['wrong', 'quit']
    monkeypatch.setattr(inquirer, 'text', lambda *args, **kwargs: DummyPrompt(texts.pop(0)))
    # Run the quiz session
    cli.quiz_menu()
    out = capsys.readouterr().out
    # Both generated questions should appear in output
    assert 'Q1 question?' in out, "First question was not presented"
    assert 'Q2 question?' in out, "Second question (after delete) was not presented"