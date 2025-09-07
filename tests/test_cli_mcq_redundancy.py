import pytest
from unittest.mock import MagicMock, patch
import builtins
import json

import kubelingo.cli as cli
from InquirerPy import inquirer

class DummyPrompt:
    def __init__(self, value):
        self.value = value
    def execute(self):
        return self.value

@pytest.fixture(autouse=True)
def isolate_last_generated_q(monkeypatch):
    cli.last_generated_q = None
    yield
    cli.last_generated_q = None

@pytest.fixture
def mock_ai_chat_mcq_redundancy(monkeypatch):
    def _mock_ai_chat(system_prompt, user_prompt):
        return json.dumps({
            "question": "Which of the following is a Kubernetes networking utility?",
            "answer": "kubectl exec",
            "question_type": "multiple choice",
            "options": ["kubectl logs", "kubectl exec", "kubectl describe", "kubectl port-forward"],
            "explanation": "kubectl exec allows you to execute commands inside a running container, which is useful for troubleshooting network connectivity."
        })
    monkeypatch.setattr(cli, "ai_chat", _mock_ai_chat)

@pytest.fixture
def mock_inquirer_select(monkeypatch):
    mock_select = MagicMock()
    monkeypatch.setattr(inquirer, 'select', mock_select)
    return mock_select

@pytest.fixture
def mock_inquirer_text(monkeypatch):
    mock_text = MagicMock()
    monkeypatch.setattr(inquirer, 'text', mock_text)
    return mock_text

def test_mcq_correct_answer_no_redundant_suggested_answer(
    capsys, mock_ai_chat_mcq_redundancy, mock_inquirer_select, mock_inquirer_text, monkeypatch
):
    # Simulate user selecting 'Multiple Choice' and a topic
    mock_inquirer_select.side_effect = [
        DummyPrompt("Multiple Choice"),
        DummyPrompt("networking_utilities"),
        DummyPrompt("do not save question")
    ]
    # Simulate user answering correctly
    mock_inquirer_text.side_effect = [
        DummyPrompt("1"), # Number of questions
        DummyPrompt("kubectl exec") # User answer (correct)
    ]

    input_choices = iter([
        "a", # Answer the question
        "q"  # Quit the quiz session
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    cli.quiz_menu()

    captured = capsys.readouterr()

    # Assert that "Correct!" is displayed
    assert "Correct!" in captured.out

    # Assert that "Suggested Answer:" is NOT displayed when the user answers correctly
    # This is the core of the redundancy check
    assert "Suggested Answer:" not in captured.out

    assert "Your answer differs from the suggested answer." not in captured.out
