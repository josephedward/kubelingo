import pytest
import cli


class DummyAnswer:
    """Simple dummy prompt for InquirerPy-like interface."""
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


@pytest.mark.parametrize('quiz_type,topic', [
    ('Trivia', 'pods'),
    ('Command', 'pods'),
    ('Manifest', 'pods'),
])
def test_quiz_menu_post_question_menu_not_duplicated(monkeypatch, capsys, quiz_type, topic):
    """Ensure the Post Question Menu is printed only once per quiz session."""
    # Setup inquirer.select and inquirer.text to simulate user choices
    selects = [quiz_type, topic]
    # Provide two quit responses: one for generate_trivia (if applicable), one for quiz_menu
    texts = ['q', 'q']

    def fake_select(message, *args, **kwargs):
        if not selects:
            pytest.fail(f"No more select responses for prompt: {message}")
        return DummyAnswer(selects.pop(0))

    def fake_text(message, *args, **kwargs):
        if not texts:
            pytest.fail(f"No more text responses for prompt: {message}")
        return DummyAnswer(texts.pop(0))

    monkeypatch.setattr(cli.inquirer, 'select', fake_select)
    monkeypatch.setattr(cli.inquirer, 'text', fake_text)

    # Stub generation functions to control menu printing
    if quiz_type == 'Command':
        monkeypatch.setattr(cli, 'generate_command', lambda topic=None, gen=None: None)
    elif quiz_type == 'Manifest':
        monkeypatch.setattr(cli, 'generate_question', lambda topic=None, gen=None: None)
    # For Trivia, use actual generate_trivia to test duplicate behavior

    # Run the quiz menu
    cli.quiz_menu()
    out = capsys.readouterr().out
    # Count occurrences of the first post-question menu entry (header is removed)
    # Use the first defined entry to check duplication
    key, label, desc = cli.MENU_DEFINITIONS['post_question']['entries'][0]
    entry_line = f"{key}) {label:<9}- {desc}"
    occurrences = out.count(entry_line)
    # Trivia mode handles its own menus and does not show post-question entries here
    # Expect the Post Question Menu to appear exactly once for all quiz types
    expected = 1
    assert occurrences == expected, (
        f"For quiz type '{quiz_type}', found {occurrences} occurrences of post-question menu entry '{entry_line}', "
        f"expected {expected}.\nOutput:\n{out}"
    )