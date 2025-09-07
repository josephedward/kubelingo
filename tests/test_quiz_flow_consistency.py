import pytest
from unittest.mock import MagicMock, patch
from InquirerPy import inquirer
import json
import builtins

import kubelingo.cli as cli

class DummyPrompt:
    def __init__(self, value):
        self.value = value
    def execute(self):
        return self.value

@pytest.fixture(autouse=True)
def isolate_last_generated_q(monkeypatch):
    # Ensure last_generated_q is reset before each test
    cli.last_generated_q = None
    yield
    cli.last_generated_q = None

@pytest.fixture
def mock_inquirer_select(monkeypatch):
    # Mock inquirer.select for topic selection and post-answer menu
    mock_select = MagicMock()
    monkeypatch.setattr(inquirer, 'select', mock_select)
    return mock_select

@pytest.fixture
def mock_inquirer_text(monkeypatch):
    # Mock inquirer.text for user answers
    mock_text = MagicMock()
    monkeypatch.setattr(inquirer, 'text', mock_text)
    return mock_text

@pytest.fixture
def mock_ai_chat_generic(monkeypatch):
    # Generic mock for ai_chat that returns different question types
    def _mock_ai_chat(system_prompt, user_prompt):
        if "true/false" in system_prompt:
            return json.dumps({
                "question": "True or False: Kubernetes is open source.",
                "answer": "true",
                "question_type": "true/false",
                "topic": "general",
                "suggested_answer": "true"
            })
        elif "vocabulary" in system_prompt:
            return json.dumps({
                "question": "What is a Pod?",
                "answer": "Smallest deployable unit in Kubernetes.",
                "question_type": "vocabulary",
                "topic": "pods",
                "suggested_answer": "Smallest deployable unit in Kubernetes."
            })
        elif "multiple choice" in system_prompt:
            return json.dumps({
                "question": "Which of the following is NOT a core Kubernetes object?",
                "options": ["Pod", "Service", "Deployment", "Virtual Machine"],
                "answer": "Virtual Machine",
                "question_type": "multiple choice",
                "topic": "general",
                "suggested_answer": "Virtual Machine"
            })
        elif "command" in system_prompt:
            return json.dumps({
                "question": "How do you get all pods in the 'default' namespace?",
                "answer": "kubectl get pods",
                "question_type": "imperative",
                "topic": "pods",
                "suggested_answer": "kubectl get pods"
            })
        elif "manifest" in system_prompt:
            return json.dumps({
                "question": "Create a Pod named 'my-nginx' using the 'nginx' image.",
                "answer": "apiVersion: v1\nkind: Pod\nmetadata:\n  name: my-nginx\nspec:\n  containers:\n  - name: nginx\n    image: nginx",
                "question_type": "declarative",
                "topic": "pods",
                "suggested_answer": "apiVersion: v1\nkind: Pod\nmetadata:\n  name: my-nginx\nspec:\n  containers:\n  - name: nginx\n    image: nginx"
            })
        # Default case for general questions (if any)
        return json.dumps({
            "question": "What is Kubernetes?",
            "answer": "An open-source container-orchestration system.",
            "question_type": "general",
            "topic": "general",
            "suggested_answer": "An open-source container-orchestration system."
        })
    monkeypatch.setattr(cli, "ai_chat", _mock_ai_chat)

@pytest.mark.parametrize("quiz_type, user_answer, expected_question_text", [
    ("True/False", "True", "True or False: Kubernetes is open source."),
    ("Vocab", "Smallest deployable unit in Kubernetes.", "What is a Pod?"),
    ("Multiple Choice", "Virtual Machine", "Which of the following is NOT a core Kubernetes object?"),
    ("Imperative (Commands)", "kubectl get pods", "How do you get all pods in the 'default' namespace?"),
    ("Declarative (Manifests)", "apiVersion: v1\nkind: Pod\nmetadata:\n  name: my-nginx\nspec:\n  containers:\n  - name: nginx\n    image: nginx", "Create a Pod named 'my-nginx' using the 'nginx' image."),
])
def test_quiz_flow_correct_answer_consistency(
    capsys,
    mock_inquirer_select,
    mock_inquirer_text,
    monkeypatch,
    mock_ai_chat_generic, # Use the generic mock for ai_chat
    quiz_type,
    user_answer,
    expected_question_text
):
    # Simulate user selecting quiz type, topic, answering correctly, and quitting
    mock_inquirer_select.side_effect = [
        DummyPrompt(quiz_type), # Quiz type selection
        DummyPrompt("pods"),    # Subject matter selection (can be generic)
        DummyPrompt("do not save question") # Post-answer menu action
    ]
    mock_inquirer_text.side_effect = [
        DummyPrompt("1"),       # Number of questions
        DummyPrompt(user_answer) # User's correct answer
    ]

    input_choices = iter([
        "a", # Answer the question
        "q"  # Quit the quiz session
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    cli.quiz_menu()

    captured = capsys.readouterr()

    # Assert that the correct question text is displayed
    assert expected_question_text in captured.out
    # Assert that "Correct!" message is displayed
    assert "Correct!" in captured.out
    # Assert that the post-answer menu is displayed
    assert "r)etry" in captured.out
    assert "c)orrect" in captured.out
    assert "m)issed" in captured.out
    assert "s)ource" in captured.out
    assert "d)elete question" in captured.out
    # Assert that the "Your answer differs" message is NOT displayed for correct answers
    assert "(Your answer differs from the suggested answer.)" not in captured.out