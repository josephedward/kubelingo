import pytest
from unittest.mock import patch
import cli


class DummySelect:
    def __init__(self, *args, **kwargs):
        pass
    def execute(self):
        return 'retry'


def test_post_answer_menu_display(monkeypatch):
    # Stub the inquirer.select to avoid waiting for user input
    monkeypatch.setattr(cli.inquirer, 'select', lambda *args, **kwargs: DummySelect())
    # Capture console.print output
    printed = []
    monkeypatch.setattr(cli.console, 'print', lambda *args, **kwargs: printed.append(' '.join(str(a) for a in args)))
    # Call post_answer_menu with dummy question
    q = {'topic': 'testtopic'}
    filepath = 'questions/uncategorized/test.json'
    idx = 1
    total = 3
    result = cli.post_answer_menu(q, filepath, idx, total)
    # On 'retry', index should be returned unchanged
    assert result == idx
    # First line should be the prompt header
    expected = ['? ? Choose an action:']
    # Subsequent lines should match MENU_DEFINITIONS['post_answer'] entries
    for key, label, desc in cli.MENU_DEFINITIONS['post_answer']['entries']:
        expected.append(f"{key}) {label:<9}- {desc}")
    assert printed == expected


def test_post_answer_menu_inquirer_choices(monkeypatch):
    # Capture the choices passed to inquirer.select
    captured = {}
    def fake_select(message, choices):
        captured['message'] = message
        captured['choices'] = choices
        class Dummy:
            def execute(self):
                return 'correct'
        return Dummy()
    monkeypatch.setattr(cli.inquirer, 'select', fake_select)
    # Stub shutil.move to prevent filesystem changes
    monkeypatch.setattr(cli.shutil, 'move', lambda src, dst: None)
    # Call post_answer_menu and assert behavior for 'correct'
    q = {'topic': 'foo'}
    filepath = 'questions/uncategorized/foo.json'
    # 'correct' should return None
    result = cli.post_answer_menu(q, filepath, 2, 5)
    assert result is None
    # The select message should prompt user
    assert captured['message'] == 'Select an action:'
    # Choices should be the labels from MENU_DEFINITIONS['post_answer']
    expected_labels = [label for _, label, _ in cli.MENU_DEFINITIONS['post_answer']['entries']]
    assert captured['choices'] == expected_labels