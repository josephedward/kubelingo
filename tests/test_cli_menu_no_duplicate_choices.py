import os
import pytest
import kubelingo.cli as cli

class DummyPrompt:
    """Dummy prompt to simulate InquirerPy.prompt.execute()"""
    def __init__(self, value):
        self._value = value
    def execute(self):
        return self._value

def test_main_menu_has_unique_choices(monkeypatch):
    recorded = []
    def fake_select(*args, **kwargs):
        # record choices argument
        recorded.append(kwargs.get('choices'))
        # choose Exit to trigger sys.exit
        return DummyPrompt('Exit')
    monkeypatch.setattr(cli.inquirer, 'select', fake_select)
    with pytest.raises(SystemExit):
        cli.main()
    assert recorded, "Main menu select was not called"
    choices = recorded[0]
    assert isinstance(choices, list), "Main menu choices should be a list"
    assert len(choices) == len(set(choices)), f"Duplicate entries in main menu choices: {choices}"

def test_import_menu_has_unique_choices(monkeypatch, tmp_path):
    # Ensure questions directory exists
    monkeypatch.setattr(os.path, 'isdir', lambda path: True)
    recorded = []
    def fake_select(*args, **kwargs):
        recorded.append(kwargs.get('choices'))
        return DummyPrompt('Back')
    monkeypatch.setattr(cli.inquirer, 'select', fake_select)
    # Call import_menu, should return immediately after selecting Back
    cli.import_menu()
    assert recorded, "Import menu select was not called"
    choices = recorded[0]
    assert isinstance(choices, list), "Import menu choices should be a list"
    assert len(choices) == len(set(choices)), f"Duplicate entries in import menu choices: {choices}"

def test_post_answer_menu_has_unique_choices(monkeypatch):
    recorded = []
    def fake_select(*args, **kwargs):
        recorded.append(kwargs.get('choices'))
        return DummyPrompt('retry')
    monkeypatch.setattr(cli.inquirer, 'select', fake_select)
    result = cli.post_answer_menu()
    assert result == 'retry', "post_answer_menu did not return expected value"
    assert recorded, "Post-answer menu select was not called"
    choices = recorded[0]
    assert isinstance(choices, list), "Post-answer menu choices should be a list"
    # ensure uniqueness by equality (handles unhashable items)
    seen = []
    for item in choices:
        assert item not in seen, f"Duplicate entry in post-answer menu choices: {item}"
        seen.append(item)

def test_quiz_menu_type_and_subject_choices_unique(monkeypatch):
    # Record the sequence of select calls: first for type, then subject, then exit
    calls = []
    def fake_select(message, **kwargs):
        # capture message and choices list
        calls.append((message, kwargs.get('choices')))
        # First call: type menu -> pick a valid type
        if len(calls) == 1:
            return DummyPrompt('True/False')
        # Second call: subject matters -> go back to type menu
        if len(calls) == 2:
            return DummyPrompt('Back')
        # Third call: type menu -> pick Back to exit
        return DummyPrompt('Back')
    monkeypatch.setattr(cli.inquirer, 'select', fake_select)
    # Run quiz_menu; it will exit after Back
    cli.quiz_menu()
    # Expect at least two calls: type menu, subject matters
    assert len(calls) >= 2, "Expected at least two select calls in quiz_menu"
    # Check type menu choices
    type_msg, type_choices = calls[0]
    assert isinstance(type_choices, list), "Quiz type menu choices should be a list"
    assert len(type_choices) == len(set(type_choices)), f"Duplicate entries in quiz type menu choices: {type_choices}"
    # Check subject matters choices
    subj_msg, subj_choices = calls[1]
    assert isinstance(subj_choices, list), "Subject matters menu choices should be a list"
    assert len(subj_choices) == len(set(subj_choices)), f"Duplicate entries in subject matters menu choices: {subj_choices}"