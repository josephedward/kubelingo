import os
import kubelingo.cli as cli
import pytest
from unittest.mock import MagicMock

def test_open_manifest_editor_returns_template(monkeypatch):
    # No editing: os.system is a no-op
    monkeypatch.setattr(os, 'system', lambda cmd: 0)
    content = cli._open_manifest_editor('initial-template')
    assert content == 'initial-template'

def test_open_manifest_editor_applies_system_edit(monkeypatch):
    # Simulate user editing by overwriting temp file in os.system
    def fake_system(cmd):
        # cmd is like 'EDITOR tmp_path'
        _, path = cmd.split(' ', 1)
        with open(path, 'w') as f:
            f.write('edited-content')
        return 0
    monkeypatch.setenv('EDITOR', 'nano')
    monkeypatch.setattr(os, 'system', fake_system)
    content = cli._open_manifest_editor('ignored-template')
    assert content == 'edited-content'

def test_open_manifest_editor_removes_file(monkeypatch):
    # Track removal of temp file and perform actual removal to avoid leakage
    orig_remove = os.remove
    removed = []
    def fake_remove(path):
        removed.append(path)
        orig_remove(path)
    monkeypatch.setattr(os, 'remove', fake_remove)
    monkeypatch.setattr(os, 'system', lambda cmd: 0)
    # Invoke editor
    cli._open_manifest_editor('to-remove')
    # Ensure remove was called with a .yaml file
    assert removed, "Temporary file was not removed"
    assert removed[0].endswith('.yaml')

@pytest.mark.parametrize("user_manifest, suggested_manifest, expect_correct", [
    ('apiVersion: v1\\nkind: Pod', 'apiVersion: v1\\nkind: Pod', True),
    ('apiVersion: v1', 'apiVersion: v1\\nkind: Pod', False),
])
def test_quiz_menu_manifest_question_flow(monkeypatch, capsys, user_manifest, suggested_manifest, expect_correct):
    # Stub quiz type selection
    fake_select = MagicMock()
    fake_select.execute.return_value = 'Declarative (Manifests)'
    monkeypatch.setattr(cli.inquirer, 'select', lambda *args, **kwargs: fake_select)
    # Stub subject matter selection
    monkeypatch.setattr(cli, 'select_topic', lambda: 'pods')
    # Stub number of questions input
    class FakeAnswer:
        def __init__(self, value): self._value = value
        def execute(self): return self._value
    monkeypatch.setattr(cli.inquirer, 'text', lambda *args, **kwargs: FakeAnswer('1'))
    # Stub QuestionGenerator to return one manifest question
    class DummyQG:
        def __init__(self): pass
        def generate_question_set(self, count, question_type, subject_matter):
            return [{'question': 'Test manifest question', 'suggested_answer': suggested_manifest}]
    monkeypatch.setattr(cli, 'QuestionGenerator', DummyQG)
    # Stub editor to return user_manifest
    monkeypatch.setattr(cli, '_open_manifest_editor', lambda template='': user_manifest)
    # Run the manifest quiz flow
    cli.quiz_menu()
    out = capsys.readouterr().out
    # Verify question prompt and answer handling
    assert 'Question: Test manifest question' in out
    assert 'Your answer:' in out
    assert user_manifest in out
    if expect_correct:
        assert 'Correct!' in out
    else:
        assert 'Suggested Answer:' in out
        assert suggested_manifest in out