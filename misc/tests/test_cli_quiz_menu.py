import pytest
from InquirerPy import inquirer
import webbrowser

import cli


class FakeAnswer:
    """Mimics InquirerPy answer object."""
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


def setup_inquirer(monkeypatch, select_vals, text_vals):
    """Monkeypatch inquirer.select and inquirer.text with predefined values."""
    selects = list(select_vals)
    texts = list(text_vals)

    def fake_select(message, *args, **kwargs):
        if not selects:
            pytest.fail(f"No more select responses for prompt: {message}")
        return FakeAnswer(selects.pop(0))

    def fake_text(message, *args, **kwargs):
        if not texts:
            pytest.fail(f"No more text responses for prompt: {message}")
        return FakeAnswer(texts.pop(0))

    monkeypatch.setattr(cli.inquirer, 'select', fake_select)
    monkeypatch.setattr(cli.inquirer, 'text', fake_text)


@pytest.mark.parametrize('quiz_type, topic, text_vals, select_vals', [
    ('Trivia', 'pods', ['pods', 'quit'], ['Trivia', 'pods', 'Correct']),
    ('Command', 'pods', ['kubectl run p --image=i', 'quit'], ['Command', 'pods']),
])
def test_quiz_menu_post_question_menu(monkeypatch, capsys, quiz_type, topic, text_vals, select_vals):
    """Test that the unified Post Question Menu appears in Trivia and Command quizzes."""
    # For Command, stub QuestionGenerator to avoid external logic
    if quiz_type == 'Command':
        class DummyGen:
            def generate_question(self, topic, include_context=True):
                return {
                    'id': 'test-id',
                    'topic': topic,
                    'question': 'Dummy question',
                    'documentation_link': None,
                    'context_variables': {
                        'pod_name': 'p', 'image': 'i',
                        'port': None, 'env_var': None, 'env_value': None,
                        'cpu_limit': None, 'memory_limit': None, 'sidecar_image': None,
                    }
                }
        monkeypatch.setattr(cli, 'QuestionGenerator', lambda: DummyGen())
    # Setup inquirer responses: quiz type, topic
    setup_inquirer(monkeypatch, select_vals=select_vals, text_vals=text_vals)
    # Prevent actual browser opens
    monkeypatch.setattr(webbrowser, 'open', lambda url: None)
    # Run quiz menu
    cli.quiz_menu()
    out = capsys.readouterr().out
    # Header is removed; ensure post-question menu entries are printed
    key, label, desc = cli.MENU_DEFINITIONS['post_question']['entries'][0]
    entry_line = f"{key}) {label:<9}- {desc}"
    assert entry_line in out, f"Expected menu entry '{entry_line}' in output:\n{out}"
    assert 'v) vim      - opens vim for manifest-based questions' in out
    assert 'b) backward - previous question' in out
    assert 'f) forward  - next question' in out
    assert 'a) answer   - shows solution' in out
    assert 's) visit    - source (opens browser at source)' in out
    assert 'q) quit     - back to main menu' in out

def test_quiz_menu_manifest_post_question_menu(monkeypatch, capsys):
    """Test that the unified Post Question Menu appears in Manifest quizzes."""
    # Stub generate_question (alias to answer_question) to skip manifest editor
    def fake_answer_question(topic=None, gen=None):
        # Simulate printing a manifest question
        print(f"Question: Dummy manifest question for {topic}")
    monkeypatch.setattr(cli, 'generate_question', fake_answer_question)
    # Setup inquirer responses: quiz type, topic, post-question command
    setup_inquirer(monkeypatch, select_vals=['Manifest', 'ingress'], text_vals=['quit'])
    # Prevent actual browser opens
    monkeypatch.setattr(webbrowser, 'open', lambda url: None)
    # Run quiz menu
    cli.quiz_menu()
    out = capsys.readouterr().out
    # Header is removed; ensure post-question menu entries are printed
    key, label, desc = cli.MENU_DEFINITIONS['post_question']['entries'][0]
    entry_line = f"{key}) {label:<9}- {desc}"
    assert entry_line in out, f"Expected menu entry '{entry_line}' in output:\n{out}"
    assert 'v) vim      - opens vim for manifest-based questions' in out
    assert 'b) backward - previous question' in out
    assert 'f) forward  - next question' in out
    assert 'a) answer   - shows solution' in out
    assert 's) visit    - source (opens browser at source)' in out
    assert 'q) quit     - back to main menu' in out
