import pytest
import cli

class FakeAnswer:
    """Fake answer for InquirerPy text prompt."""
    def __init__(self, value):
        self._value = value
    def execute(self):
        return self._value

def test_print_question_menu_entries_only(monkeypatch):
    # Capture console.print outputs
    printed = []
    monkeypatch.setattr(cli.console, 'print', lambda x: printed.append(x))
    # Invoke the post-question menu print
    cli.print_question_menu()
    # Expect a single-line flattened menu
    expected = [cli.QUESTION_MENU_LINE]
    assert printed == expected

def test_generate_trivia_shows_menu_after_answer(monkeypatch):
    # Prevent actual console output and JSON printing
    monkeypatch.setattr(cli.console, 'print', lambda *args, **kwargs: None)
    monkeypatch.setattr(cli.console, 'print_json', lambda *args, **kwargs: None)

    # Mock ai_chat to return a valid question
    def mock_ai_chat(system_prompt, user_prompt):
        return '{"type": "tf", "question": "Test question", "answer": "true"}'
    monkeypatch.setattr(cli, "ai_chat", mock_ai_chat)

    # Record call order for text prompt and menu print
    order = []
    # Fake text prompt to simulate user entering 'true'
    def fake_text(message):
        order.append('text')
        return FakeAnswer('true')
    monkeypatch.setattr(cli.inquirer, 'text', fake_text)

    # Fake post-answer menu selection via inquirer.select
    def fake_select(message, choices):
        order.append('menu')
        class DummySelect:
            def execute(self):
                return 'retry'
        return DummySelect()
    monkeypatch.setattr(cli.inquirer, 'select', fake_select)

    # Run trivia generator with a known topic to skip topic selection
    cli.generate_trivia(topic='pods')

    # Ensure the answer prompt occurred before the menu was shown
    assert order[:2] == ['text', 'menu'], f"Expected text before menu, got {order}"