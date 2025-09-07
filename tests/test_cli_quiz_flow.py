import pytest
from unittest.mock import MagicMock, patch
from InquirerPy import inquirer
import json

import kubelingo.cli as cli
import builtins

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
def mock_ai_chat_tf(monkeypatch):
    # Mock ai_chat to return a True/False question
    def _mock_ai_chat(system_prompt, user_prompt):
        return json.dumps({
            "question": "True or False: Kubernetes is open source.",
            "answer": "true",
            "type": "tf",
            "topic": "general",
            "difficulty": "beginner",
            "expected_resources": [],
            "success_criteria": ["Answer is true"],
            "hints": []
        })
    monkeypatch.setattr(cli._llm_utils, "ai_chat", _mock_ai_chat)

@pytest.fixture
def mock_ai_chat_vocab(monkeypatch):
    # Mock ai_chat to return a vocab question
    def _mock_ai_chat(system_prompt, user_prompt):
        return json.dumps({
            "question": "What is a Pod?",
            "answer": "Smallest deployable unit in Kubernetes.",
            "type": "vocab",
            "topic": "pods",
            "difficulty": "beginner",
            "expected_resources": ["Pod"],
            "success_criteria": ["Definition is accurate"],
            "hints": []
        })
    monkeypatch.setattr(cli._llm_utils, "ai_chat", _mock_ai_chat)

@pytest.fixture
def mock_ai_chat_mcq(monkeypatch):
    # Mock ai_chat to return a Multiple Choice question
    def _mock_ai_chat(system_prompt, user_prompt):
        return json.dumps({
            "question": "Which of the following is NOT a core Kubernetes object?",
            "answer": "Virtual Machine",
            "type": "mcq",
            "topic": "general",
            "difficulty": "intermediate",
            "choices": ["Pod", "Service", "Deployment", "Virtual Machine"],
            "expected_resources": [],
            "success_criteria": ["Correct option is selected"],
            "hints": []
        })
    monkeypatch.setattr(cli._llm_utils, "ai_chat", _mock_ai_chat)

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



def test_trivia_flow_correct_answer_and_quit(
    capsys, mock_ai_chat_tf, mock_inquirer_select, mock_inquirer_text, monkeypatch
):

    # Simulate user selecting 'Trivia' and 'pods'
    mock_inquirer_select.side_effect = [
        DummyPrompt("True/False"), # Quiz type selection
        DummyPrompt("pods"),        # Subject matter selection
        DummyPrompt("do not save question") # Post-answer menu action (label for 'd')
    ]
    mock_inquirer_text.side_effect = [
        DummyPrompt("1"), # Number of questions
        DummyPrompt("True") # User answer
    ]

    input_choices = iter([
        "a", # Answer the question
        "q"  # Quit the quiz session
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    # Run the quiz menu (which calls generate_trivia)
    cli.quiz_menu()

    captured = capsys.readouterr()

    # Assert correct message and post-answer menu options are displayed
    assert "(Your answer differs from the suggested answer.)" not in captured.out
    assert "r)etry" in captured.out
    assert "c)orrect" in captured.out
    assert "m)issed" in captured.out
    assert "s)ource" in captured.out
    assert "d)elete question" in captured.out

    # Assert last_generated_q is recorded (correctness tracked via output)
    assert cli.last_generated_q is not None

def test_trivia_flow_incorrect_answer_and_retry(
    capsys, mock_ai_chat_tf, mock_inquirer_select, mock_inquirer_text, monkeypatch
):

    # Simulate user selecting 'Trivia' and 'pods'
    # Then answering 'False' (incorrect)
    # Then selecting 'retry' from post-answer menu
    # Then answering 'True' (correct)
    # Then selecting 'do not save question' to exit
    mock_inquirer_select.side_effect = [
        DummyPrompt("True/False"), # Quiz type selection
        DummyPrompt("pods"), # Topic selection
        DummyPrompt("retry"), # Post-answer menu action
        DummyPrompt("do not save question") # Post-answer menu action to quit
    ]
    mock_inquirer_text.side_effect = [
        DummyPrompt("1"), # Number of questions
        DummyPrompt("False"), # First answer (incorrect)
        DummyPrompt("True")   # Second answer (correct, after retry)
    ]

    input_choices = iter([
        "a", # Answer the question
        "a", # Answer the question again after retry
        "q"  # Quit the quiz session
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    cli.quiz_menu()

    captured = capsys.readouterr()

    # Assert incorrect message
    assert "(Your answer differs from the suggested answer.)" in captured.out
    # Assert correct message after retry
    assert "(Your answer differs from the suggested answer.)" not in captured.out

    # Assert last_generated_q is recorded for the final correct answer
    assert cli.last_generated_q is not None

def test_trivia_flow_question_menu_before_answer_and_help(
    capsys, mock_ai_chat_tf, mock_inquirer_select, mock_inquirer_text, monkeypatch
):

    # Simulate user selecting 'Trivia' and 'pods'
    mock_inquirer_select.side_effect = [
        DummyPrompt("True/False"), # Quiz type selection
        DummyPrompt("pods"), # Topic selection
        DummyPrompt("do not save question") # Post-answer menu action
    ]
    mock_inquirer_text.side_effect = [
        DummyPrompt("1"),    # Number of questions
        DummyPrompt("?"),    # Request help
        DummyPrompt("True")  # Actual answer
    ]

    input_choices = iter([
        "?", # Request help
        "a", # Answer the question
        "q"  # Quit the quiz session
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    cli.quiz_menu()

    captured = capsys.readouterr()

    # Verify question menu options are in output (from initial display and '?' command)
    assert "v) vim" in captured.out
    assert "b) backward" in captured.out
    assert "f) forward" in captured.out
    assert "a) answer" in captured.out
    assert "s) visit" in captured.out
    assert "q) quit" in captured.out

    # Assert correct message
    assert "(Your answer differs from the suggested answer.)" not in captured.out

def test_trivia_flow_no_question_menu_after_answer(
    capsys, mock_ai_chat_tf, mock_inquirer_select, mock_inquirer_text, monkeypatch
):

    # Simulate user selecting 'Trivia' and 'pods'
    mock_inquirer_select.side_effect = [
        DummyPrompt("True/False"), # Quiz type selection
        DummyPrompt("pods"), # Topic selection
        DummyPrompt("do not save question") # Post-answer menu action
    ]
    mock_inquirer_text.return_value = DummyPrompt("1") # Number of questions
    mock_inquirer_text.side_effect = [
        DummyPrompt("1"), # Number of questions
        DummyPrompt("True") # User answer
    ]

    input_choices = iter([
        "a", # Answer the question
        "q"  # Quit the quiz session
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    cli.quiz_menu()

    captured = capsys.readouterr()

    # Check that the question menu header/options do not appear after the answer
    # This is a bit indirect, but we can check the order of calls and content
    # The 'Correct!' message should appear before the post-answer menu, and no question menu in between.
    correct_idx = captured.out.find("Suggested Answer:")
    post_answer_menu_idx = captured.out.find("r) retry") # First option of post-answer menu

    assert correct_idx != -1 # Ensure Suggested Answer is found
    assert post_answer_menu_idx != -1 # Ensure post-answer menu is found
    assert correct_idx < post_answer_menu_idx # Ensure order

    # Ensure no question menu options appear between 'Correct!' and 'r) retry'
    segment = captured.out[correct_idx:post_answer_menu_idx]
    assert "v) vim" not in segment
    assert "b) backward" not in segment
    assert "f) forward" not in segment
    assert "a) answer" not in segment
    assert "s) visit" not in segment
    assert "q) quit" not in segment
    assert "(Your answer differs from the suggested answer.)" not in segment

@patch('kubelingo.cli._open_manifest_editor')
def test_manifest_quiz_vim_editor(
    mock_open_manifest_editor, capsys, mock_inquirer_select, mock_inquirer_text
):
    # Mock _open_manifest_editor to return some content
    mock_open_manifest_editor.return_value = "apiVersion: v1\nkind: Pod"

    # Simulate user selecting 'Manifest' quiz type, 'deployments' topic,
    # then typing 'v' for vim, and 'quit' to exit the quiz loop.
    mock_inquirer_select.side_effect = [
        DummyPrompt("Manifest"), # Quiz type selection
        DummyPrompt("deployment") # Topic selection
    ]
    mock_inquirer_text.side_effect = [
        DummyPrompt("v"), # User types 'v' for vim
        DummyPrompt("quit") # User types 'quit' to exit the quiz loop
    ]

    cli.quiz_menu()

    captured = capsys.readouterr()

    # Assert that _open_manifest_editor was called once
    mock_open_manifest_editor.assert_called_once()

    # Assert that the "Manifest edited:" message is printed
    assert "Manifest edited:" in captured.out
    assert "apiVersion: v1\nkind: Pod" in captured.out # Verify content from mock is printed
    assert "No manifest to edit in this mode." not in captured.out # Ensure old message is gone

def test_vocab_quiz_flow_correct_answer(
    capsys, mock_ai_chat_vocab, mock_inquirer_select, mock_inquirer_text, monkeypatch
):

    # Simulate user selecting 'Vocab' and 'pods'
    mock_inquirer_select.side_effect = [
        DummyPrompt("Vocab"), # Quiz type selection
        DummyPrompt("pods"), # Topic selection
        DummyPrompt("do not save question") # Post-answer menu action
    ]
    # Simulate user answering 'Smallest deployable unit in Kubernetes.'
    mock_inquirer_text.side_effect = [
        DummyPrompt("1"), # Number of questions
        DummyPrompt("Smallest deployable unit in Kubernetes.") # User answer
    ]

    input_choices = iter([
        "a", # Answer the question
        "q"  # Quit the quiz session
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    cli.quiz_menu()

    captured = capsys.readouterr()

    assert "Question: What is a Pod?" in captured.out
    assert "(Your answer differs from the suggested answer.)" not in captured.out

def test_mcq_quiz_flow_correct_answer(
    capsys, mock_ai_chat_mcq, mock_inquirer_select, mock_inquirer_text, monkeypatch
):

    # Simulate user selecting 'Multiple Choice' and 'general'
    mock_inquirer_select.side_effect = [
        DummyPrompt("Multiple Choice"), # Quiz type selection
        DummyPrompt("pods"), # Topic selection (can be any, as mock_ai_chat_mcq is generic)
        DummyPrompt("do not save question") # Post-answer menu action
    ]
    # Simulate user answering 'Virtual Machine' (which is the correct answer in the mock)
    mock_inquirer_text.side_effect = [
        DummyPrompt("1"), # Number of questions
        DummyPrompt("Virtual Machine") # User answer
    ]

    input_choices = iter([
        "a", # Answer the question
        "q"  # Quit the quiz session
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    cli.quiz_menu()

    captured = capsys.readouterr()

    assert "Question: Which of the following is NOT a core Kubernetes object?" in captured.out
    assert "(Your answer differs from the suggested answer.)" not in captured.out


@pytest.fixture
def mock_ai_chat_imperative(monkeypatch):
    # Mock ai_chat to return an Imperative (command) question
    def _mock_ai_chat(system_prompt, user_prompt):
        return json.dumps({
            "question": "How do you get all pods in the 'default' namespace?",
            "answer": "kubectl get pods",
            "type": "imperative",
            "topic": "pods",
            "difficulty": "easy",
            "explanation": "This command lists all pods in the default namespace."
        })
    monkeypatch.setattr(cli._llm_utils, "ai_chat", _mock_ai_chat)

@pytest.fixture
def mock_ai_chat_declarative(monkeypatch):
    # Mock ai_chat to return a Declarative (manifest) question
    def _mock_ai_chat(system_prompt, user_prompt):
        return json.dumps({
            "question": "Create a Pod named 'my-nginx' using the 'nginx' image.",
            "answer": "apiVersion: v1\nkind: Pod\nmetadata:\n  name: my-nginx\nspec:\n  containers:\n  - name: nginx\n    image: nginx",
            "type": "declarative",
            "topic": "pods",
            "difficulty": "medium",
            "explanation": "This manifest defines a simple Pod."
        })
    monkeypatch.setattr(cli._llm_utils, "ai_chat", _mock_ai_chat)


def test_imperative_quiz_flow_correct_answer(
    capsys,
    mock_ai_chat_imperative,
    mock_inquirer_select,
    mock_inquirer_text,
    monkeypatch
):
    # Simulate user selecting 'Imperative (Commands)' and 'pods'
    mock_inquirer_select.side_effect = [
        DummyPrompt("Imperative (Commands)"), # Quiz type selection
        DummyPrompt("pods"), # Topic selection
        DummyPrompt("do not save question") # Post-answer menu action
    ]
    # Simulate user answering 'kubectl get pods'
    mock_inquirer_text.side_effect = [
        DummyPrompt("1"), # Number of questions
        DummyPrompt("kubectl get pods") # User answer
    ]

    input_choices = iter([
        "a", # Answer the question
        "q"  # Quit the quiz session
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    cli.quiz_menu()

    captured = capsys.readouterr()

    assert "Question: How do you get all pods in the 'default' namespace?" in captured.out
    assert "(Your answer differs from the suggested answer.)" not in captured.out


def test_declarative_quiz_flow_correct_answer(
    capsys,
    mock_ai_chat_declarative,
    mock_inquirer_select,
    mock_inquirer_text,
    monkeypatch
):
    # Simulate user selecting 'Declarative (Manifests)' and 'pods'
    mock_inquirer_select.side_effect = [
        DummyPrompt("Declarative (Manifests)"), # Quiz type selection
        DummyPrompt("pods"), # Topic selection
        DummyPrompt("do not save question") # Post-answer menu action
    ]
    # Simulate user answering the correct manifest
    mock_inquirer_text.side_effect = [
        DummyPrompt("1"), # Number of questions
        DummyPrompt("apiVersion: v1\nkind: Pod\nmetadata:\n  name: my-nginx\nspec:\n  containers:\n  - name: nginx\n    image: nginx") # User answer
    ]

    input_choices = iter([
        "a", # Answer the question
        "q"  # Quit the quiz session
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    cli.quiz_menu()

    captured = capsys.readouterr()

    assert "Question: Create a Pod named 'my-nginx' using the 'nginx' image." in captured.out
    assert "(Your answer differs from the suggested answer.)" not in captured.out



    