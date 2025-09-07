import os
import pytest
from InquirerPy import inquirer
import kubelingo.cli as cli


def get_quiz_menu_spec():
    """Read requirements.md and extract the Quiz Menu header and choices."""
    # Locate requirements.md relative to this file
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    req_file = os.path.join(root, 'requirements.md')
    if not os.path.exists(req_file):
        pytest.skip("requirements.md not found")
    header = None
    choices = []
    with open(req_file, 'r') as f:
        for line in f:
            stripped = line.strip()
            if header is None:
                if stripped == '- Quiz Menu':
                    header = stripped
            else:
                if stripped.startswith('+'):
                    # extract choice text after '+'
                    choices.append(stripped[1:].strip())
                else:
                    break
    if header is None or not choices:
        pytest.skip("Quiz Menu spec not found in requirements.md")
    return header, choices


def test_quiz_menu_invokes_inquirer_with_spec(monkeypatch):
    # Extract expected header and choices from requirements.md
    header, expected_choices = get_quiz_menu_spec()
    captured = {}

    def fake_select(message, choices, *args, **kwargs):
        captured['message'] = message
        captured['choices'] = choices
        class Dummy:
            def execute(self):  # simulate user choosing Back
                return 'Back'
        return Dummy()

    # Monkeypatch inquirer.select to our fake implementation
    monkeypatch.setattr(cli.inquirer, 'select', fake_select)

    # Run the quiz menu (should invoke our fake_select)
    cli.quiz_menu()

    # Assert that the message matches the spec header
    assert captured.get('message') == header
    # Assert that choices match spec, with 'Back' appended at the end
    assert captured.get('choices') == expected_choices + ['Back']