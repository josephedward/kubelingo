import pytest
from unittest.mock import MagicMock, patch
from InquirerPy import inquirer
import json
import builtins
import os
import yaml

import kubelingo.cli as cli

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
def mock_ai_chat_declarative(monkeypatch):
    def _mock_ai_chat(system_prompt, user_prompt):
        return json.dumps({
            "question": "Create a Pod named 'my-nginx' using the 'nginx' image.",
            "answer": "apiVersion: v1\nkind: Pod\nmetadata:\n  name: my-nginx\nspec:\n  containers:\n  - name: nginx\n    image: nginx",
            "type": "declarative",
            "topic": "pods",
            "suggested_answer": "apiVersion: v1\nkind: Pod\nmetadata:\n  name: my-nginx\nspec:\n  containers:\n  - name: nginx\n    image: nginx"
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

@pytest.fixture
def mock_open_manifest_editor(monkeypatch):
    mock_editor = MagicMock(return_value="") # Default to empty string
    monkeypatch.setattr(cli, "_open_manifest_editor", mock_editor)
    return mock_editor

# --- Test Cases for Manifest Vim Flow ---

def test_manifest_vim_correct_yaml(
    capsys,
    mock_ai_chat_declarative,
    mock_inquirer_select,
    mock_inquirer_text,
    mock_open_manifest_editor,
    monkeypatch
):
    # The expected correct manifest
    correct_manifest = (
        "apiVersion: v1\nkind: Pod\nmetadata:\n  name: my-nginx\n"\
        "spec:\n  containers:\n  - name: nginx\n    image: nginx"
    )
    mock_open_manifest_editor.return_value = correct_manifest

    # Simulate user selecting Declarative, topic, and then entering 'v' for vim
    mock_inquirer_select.side_effect = [
        DummyPrompt("Declarative (Manifests)"), # Quiz type selection
        DummyPrompt("pods"), # Topic selection
    ]
    mock_inquirer_text.side_effect = [
        DummyPrompt("1"), # Number of questions
    ]

    # Simulate user typing 'v' to open vim, then 'q' to quit the quiz session
    input_choices = iter([
        "v", # Open vim editor
        "q"  # Quit quiz session
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    cli.quiz_menu()

    captured = capsys.readouterr()

    # Assertions
    mock_open_manifest_editor.assert_called_once() # Ensure editor was opened
    assert "Question: Create a Pod named 'my-nginx' using the 'nginx' image." in captured.out
    assert "Your answer:" in captured.out
    assert correct_manifest in captured.out # Ensure the content from editor is printed
    assert "Correct!" in captured.out # Assert that it's graded as correct
    assert "Suggested Answer:" not in captured.out # Should not show suggested if correct

def test_manifest_vim_incorrect_yaml(
    capsys,
    mock_ai_chat_declarative,
    mock_inquirer_select,
    mock_inquirer_text,
    mock_open_manifest_editor,
    monkeypatch
):
    # User provides a different, but valid, manifest
    incorrect_manifest = (
        "apiVersion: v1\nkind: Deployment\nmetadata:\n  name: my-app\n"\
        "spec:\n  replicas: 1\n  selector:\n    matchLabels:\n      app: my-app\n"\
        "template:\n    metadata:\n      labels:\n        app: my-app\n"\
        "spec:\n      containers:\n      - name: my-app\n        image: busybox"
    )
    mock_open_manifest_editor.return_value = incorrect_manifest

    mock_inquirer_select.side_effect = [
        DummyPrompt("Declarative (Manifests)"),
        DummyPrompt("pods"),
    ]
    mock_inquirer_text.side_effect = [
        DummyPrompt("1"),
    ]

    input_choices = iter([
        "v",
        "q"
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    cli.quiz_menu()

    captured = capsys.readouterr()

    assert "Your answer:" in captured.out
    assert incorrect_manifest in captured.out
    assert "Correct!" not in captured.out # Should not be graded as correct
    assert "Suggested Answer:" in captured.out # Should show suggested answer

def test_manifest_vim_empty_yaml(
    capsys,
    mock_ai_chat_declarative,
    mock_inquirer_select,
    mock_inquirer_text,
    mock_open_manifest_editor,
    monkeypatch
):
    # User provides an empty manifest
    mock_open_manifest_editor.return_value = ""

    mock_inquirer_select.side_effect = [
        DummyPrompt("Declarative (Manifests)"),
        DummyPrompt("pods"),
    ]
    mock_inquirer_text.side_effect = [
        DummyPrompt("1"),
    ]

    input_choices = iter([
        "v",
        "q"
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    cli.quiz_menu()

    captured = capsys.readouterr()

    assert "Your answer:" in captured.out
    assert "Correct!" not in captured.out
    assert "Suggested Answer:" in captured.out

def test_manifest_vim_invalid_yaml(
    capsys,
    mock_ai_chat_declarative,
    mock_inquirer_select,
    mock_inquirer_text,
    mock_open_manifest_editor,
    monkeypatch
):
    # User provides invalid YAML content
    invalid_yaml = "this is not yaml: - invalid"
    mock_open_manifest_editor.return_value = invalid_yaml

    mock_inquirer_select.side_effect = [
        DummyPrompt("Declarative (Manifests)"),
        DummyPrompt("pods"),
    ]
    mock_inquirer_text.side_effect = [
        DummyPrompt("1"),
    ]

    input_choices = iter([
        "v",
        "q"
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    cli.quiz_menu()

    captured = capsys.readouterr()

    assert "Your answer:" in captured.out
    assert invalid_yaml in captured.out
    assert "Correct!" not in captured.out
    assert "Suggested Answer:" in captured.out

def test_manifest_vim_yaml_with_comments_and_formatting_differences(
    capsys,
    mock_ai_chat_declarative,
    mock_inquirer_select,
    mock_inquirer_text,
    mock_open_manifest_editor,
    monkeypatch
):
    # The expected correct manifest (from mock_ai_chat_declarative)
    expected_manifest = (
        "apiVersion: v1\nkind: Pod\nmetadata:\n  name: my-nginx\n"\
        "spec:\n  containers:\n  - name: nginx\n    image: nginx"
    )

    # User provides semantically equivalent YAML with comments and different formatting
    user_provided_manifest = (
        "# This is a test Pod manifest\n"\
        "apiVersion: v1 # API version\n"\
        "kind: Pod\n"\
        "metadata:\n  name: my-nginx # Pod name\n"\
        "spec:\n  containers:\n    - image: nginx # Container image\n"\
        "      name: nginx # Container name\n" # Different order and indentation
    )
    mock_open_manifest_editor.return_value = user_provided_manifest

    mock_inquirer_select.side_effect = [
        DummyPrompt("Declarative (Manifests)"),
        DummyPrompt("pods"),
    ]
    mock_inquirer_text.side_effect = [
        DummyPrompt("1"),
    ]

    input_choices = iter([
        "v",
        "q"
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    cli.quiz_menu()

    captured = capsys.readouterr()

    assert "Your answer:" in captured.out
    assert user_provided_manifest in captured.out
    # This assertion is expected to FAIL with the current grading logic
    # because it uses simple string comparison. This highlights the problem.
    assert "Correct!" in captured.out
    assert "Suggested Answer:" not in captured.out