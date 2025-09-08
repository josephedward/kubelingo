import json
import os
import shutil
import glob
import pytest
pytest.skip("Skipping static quiz tests after removing static option", allow_module_level=True)
import random

import kubelingo.cli as cli

class FakePrompt:
    """Simple dummy to simulate InquirerPy prompt execution."""
    def __init__(self, value):
        self.value = value
    def execute(self):
        return self.value

def setup_inquirer(monkeypatch, select_vals, text_vals):
    """Monkeypatch inquirer.select and inquirer.text to return predetermined values."""
    selects = list(select_vals)
    texts = list(text_vals)

    def fake_select(message, *args, **kwargs):
        if not selects:
            pytest.fail(f"No more select responses for prompt: {message}")
        # Pop next select value
        return FakePrompt(selects.pop(0))

    def fake_text(message, *args, **kwargs):
        if not texts:
            pytest.fail(f"No more text responses for prompt: {message}")
        return FakePrompt(texts.pop(0))

    monkeypatch.setattr(cli.inquirer, 'select', fake_select)
    monkeypatch.setattr(cli.inquirer, 'text', fake_text)


@pytest.mark.parametrize('action, expected_dir', [
    ('Correct', 'correct'),
    ('Missed', 'missed'),
    ('Remove Question', 'triage'),
])
def test_static_quiz_moves_file(tmp_path, monkeypatch, capsys, action, expected_dir):
    # Create temporary questions directory with one uncategorized question
    base = tmp_path / 'questions'
    uncategorized = base / 'uncategorized'
    uncategorized.mkdir(parents=True)
    # Write a sample question file
    qid = 'testq'
    qpath = uncategorized / f"{qid}.json"
    data = {
        'id': qid,
        'question': 'Label pod x with y',
        'suggestions': ['kubectl label pod x y'],
        'source': ''
    }
    qpath.write_text(json.dumps(data))
    # Change cwd to tmp_path
    monkeypatch.chdir(tmp_path)
    # Stub inquirer to select Static mode, provide a dummy answer, then the post-answer action
    setup_inquirer(monkeypatch,
                   select_vals=['Static', action],
                   text_vals=['whatever'])
    # Run the CLI quiz menu
    cli.quiz_menu()
    # After run, expect the file moved to questions/{expected_dir}/uncategorized
    dest_dir = base / expected_dir / 'uncategorized'
    # Capture output if needed
    out = capsys.readouterr().out
    # Verify destination directory exists and contains the moved file
    assert dest_dir.exists(), f"Expected directory {dest_dir} to exist"
    files = list(dest_dir.glob('*.json'))
    assert len(files) == 1, f"Expected one file in {dest_dir}, got {files}"
    # Ensure original uncategorized folder is now empty or nonexistent
    remaining = list(uncategorized.glob('*.json'))
    assert not remaining, f"Expected no files left in uncategorized, but found {remaining}"

@pytest.mark.parametrize('cmd', ['q', 'quit'])
def test_static_quiz_quit_no_move(tmp_path, monkeypatch, capsys, cmd):
    # Setup single static question
    base = tmp_path / 'questions'
    uncategorized = base / 'uncategorized'
    uncategorized.mkdir(parents=True)
    qid = 'testq'
    qpath = uncategorized / f"{qid}.json"
    data = {'id': qid, 'question': 'Test?', 'suggestions': ['ans'], 'source': ''}
    qpath.write_text(json.dumps(data))
    monkeypatch.chdir(tmp_path)
    # Disable random shuffle for predictability
    monkeypatch.setattr(random, 'shuffle', lambda x: None)
    # Stub inquirer: choose Static, then quit command
    setup_inquirer(monkeypatch,
                   select_vals=['Static'],
                   text_vals=[cmd])
    # Run quiz menu
    cli.quiz_menu()
    # File should remain in uncategorized
    remaining = list((base / 'uncategorized').glob('*.json'))
    assert remaining, "Expected question to remain after quit"

@pytest.mark.parametrize('action, expected_dir', [
    ('Correct', 'correct'),
    ('Missed', 'missed'),
    ('Remove Question', 'triage'),
])
def test_static_quiz_solution_moves_file(tmp_path, monkeypatch, capsys, action, expected_dir):
    # Setup single static question
    base = tmp_path / 'questions'
    uncategorized = base / 'uncategorized'
    uncategorized.mkdir(parents=True)
    qid = 'testq'
    qpath = uncategorized / f"{qid}.json"
    data = {'id': qid, 'question': 'Test?', 'suggestions': ['ans'], 'source': ''}
    qpath.write_text(json.dumps(data))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(random, 'shuffle', lambda x: None)
    # Stub inquirer: select Static, input 's' for solution, then action
    setup_inquirer(monkeypatch,
                   select_vals=['Static', action],
                   text_vals=['s'])
    # Run quiz menu
    cli.quiz_menu()
    # After run, expect the file moved to questions/{expected_dir}/uncategorized
    dest_dir = base / expected_dir / 'uncategorized'
    assert dest_dir.exists(), f"Expected directory {dest_dir} to exist"
    files = list(dest_dir.glob('*.json'))
    assert len(files) == 1, f"Expected one file in {dest_dir}, got {files}"
    # Original uncategorized folder should be empty
    remaining = list(uncategorized.glob('*.json'))
    assert not remaining, f"Expected no files left in uncategorized, but found {remaining}"

def test_static_quiz_visit_opens_source_and_quit(tmp_path, monkeypatch, capsys):
    # Setup static question with source link
    import webbrowser
    base = tmp_path / 'questions'
    uncategorized = base / 'uncategorized'
    uncategorized.mkdir(parents=True)
    qid = 'testq'
    qpath = uncategorized / f"{qid}.json"
    link = 'http://example.com'
    data = {'id': qid, 'question': 'Test?', 'suggestions': ['ans'], 'source': link}
    qpath.write_text(json.dumps(data))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(random, 'shuffle', lambda x: None)
    opened = []
    monkeypatch.setattr(webbrowser, 'open', lambda url: opened.append(url))
    # Stub inquirer: select Static, input 'i' to visit, then 'q' to quit
    setup_inquirer(monkeypatch,
                   select_vals=['Static'],
                   text_vals=['i', 'q'])
    # Run quiz menu
    cli.quiz_menu()
    # Expect the source link opened
    assert opened == [link], f"Expected to open {link}, got {opened}"

def test_static_quiz_vim_opens_editor(tmp_path, monkeypatch, capsys):
    # Setup static question
    import subprocess
    base = tmp_path / 'questions'
    uncategorized = base / 'uncategorized'
    uncategorized.mkdir(parents=True)
    qid = 'testq'
    qpath = uncategorized / f"{qid}.json"
    data = {'id': qid, 'question': 'Test?', 'suggestions': ['ans'], 'source': ''}
    qpath.write_text(json.dumps(data))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('EDITOR', 'myeditor')
    monkeypatch.setattr(random, 'shuffle', lambda x: None)
    calls = []
    monkeypatch.setattr(subprocess, 'run', lambda cmd: calls.append(cmd))
    # Stub inquirer: select Static, input 'v' to open vim, then 'q' to quit
    setup_inquirer(monkeypatch,
                   select_vals=['Static'],
                   text_vals=['v', 'q'])
    # Run quiz menu
    cli.quiz_menu()
    # Verify editor called with correct arguments
    assert calls, "Expected subprocess.run to be called"
    # Should open editor with path to question file
    cmd = calls[0]
    assert cmd[0] == 'myeditor'
    assert cmd[1].endswith(os.path.join('questions', 'uncategorized', f"{qid}.json"))