import pytest
import kubelingo.cli as cli
import json
import kubelingo.llm_utils as llm_utils
from rich.console import Console

class FakeAnswer:
    """Fake answer for InquirerPy text prompt."""
    def __init__(self, value):
        self._value = value
    def execute(self):
        return self._value

class DummySelect:
    def __init__(self, value):
        self._value = value
    def execute(self):
        return self._value

# Helper to mock inquirer.text and inquirer.select
def mock_inquirer(monkeypatch, order_list, text_return_value="test_answer", select_return_value="retry"):
    def fake_text(message):
        order_list.append('text_prompt')
        return FakeAnswer(text_return_value)
    monkeypatch.setattr(cli.inquirer, 'text', fake_text)

    def fake_select(message, choices):
        order_list.append('select_prompt')
        return DummySelect(select_return_value)
    monkeypatch.setattr(cli.inquirer, 'select', fake_select)

# Helper to mock print_menu
def mock_print_menu(monkeypatch, order_list, menu_name):
    # cli.print_menu is no longer a direct function, it's part of quiz_session output
    # This mock is likely obsolete or needs significant refactoring.
    # For now, we'll just pass, as the test relies on console.print for order.
    pass

def test_quiz_menu_ai_question_order(monkeypatch, capsys):
    order = []

    # Mock inquirer.select for quiz type, topic, and difficulty
    select_choices = iter([
        "True/False",  # Quiz type
        "pods"        # Topic
    ])
    monkeypatch.setattr(cli.inquirer, 'select', lambda message, choices, default=None, style=None: DummySelect(next(select_choices)))

    # Mock inquirer.text for number of questions and user answer
    text_choices = iter([
        "1",           # Number of questions
        "true"         # User answer
    ])
    monkeypatch.setattr(cli.inquirer, 'text', lambda message: FakeAnswer(next(text_choices)))

    # Mock ai_chat to return a valid question
    def mock_ai_chat(system_prompt, user_prompt):
        order.append('ai_chat_call')
        return '{"question": "Is Kubernetes an open-source container orchestration system?", "expected_resources": ["None"], "success_criteria": ["Answer is true"], "hints": ["Think about its origin"]}'
    monkeypatch.setattr(llm_utils, "ai_chat", mock_ai_chat)

    # Mock QuestionGenerator._generate_question_id to return a fixed ID
    monkeypatch.setattr(cli.QuestionGenerator, "_generate_question_id", lambda: "test_id")

    # Mock console.print to track output order
    mock_console_instance = Console()
    original_console_print = mock_console_instance.print
    def mock_print(*args, **kwargs):
        if "Question:" in str(args[0]):
            order.append('question_display')
        elif "Suggested Answer:" in str(args[0]):
            order.append('suggested_answer_display')
        original_console_print(*args, **kwargs)
    monkeypatch.setattr(Console, 'print', mock_print)

    # Mock post_answer_menu to track its call
    original_post_answer_menu = cli.post_answer_menu
    def mock_post_answer_menu():
        order.append('post_answer_menu_call')
        return original_post_answer_menu()
    monkeypatch.setattr(cli, 'post_answer_menu', mock_post_answer_menu)

    # Run the quiz menu
    cli.quiz_menu()

    # Assert the order of operations
    expected_order = [
        'ai_chat_call',
        'question_display',
        'suggested_answer_display',
        'post_answer_menu_call'
    ]
    # Filter out any other prints that might occur
    filtered_order = [item for item in order if item in expected_order]
    assert filtered_order == expected_order

    # Assert that the question is displayed
    captured = capsys.readouterr().out
    assert "Question: Is Kubernetes an open-source container orchestration system?" in captured
