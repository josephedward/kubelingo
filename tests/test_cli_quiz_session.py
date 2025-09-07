import os
import json
import pytest
import cli
from InquirerPy import inquirer

@pytest.fixture(autouse=True)
def use_tmp_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    yield

def test_quiz_session_no_dir(capsys):
    # No questions/foo directory
    cli.quiz_session('foo')
    out, _ = capsys.readouterr()
    assert "No foo questions found." in out

def test_quiz_session_malformed_json(capsys, monkeypatch):
    # Create questions/foo with a malformed JSON file
    os.makedirs(os.path.join('questions', 'foo'), exist_ok=True)
    path = os.path.join('questions', 'foo', 'bad.json')
    with open(path, 'w') as f:
        json.dump([{'x': 1}, {'y': 2}], f)
    # Patch select to quit immediately
    monkeypatch.setattr(inquirer, 'select', lambda message, choices: type('C', (), {'execute': lambda self: 'Quit Quiz'})())
    cli.quiz_session('foo')
    out, _ = capsys.readouterr()
    assert "Skipping malformed question file" in out
    assert "bad.json" in out
    assert "No foo questions found." in out
    # cleanup done by fixture

def test_quiz_session_valid_file(capsys, monkeypatch):
    # Create questions/foo with a valid JSON file
    os.makedirs(os.path.join('questions', 'foo'), exist_ok=True)
    data = {'id': '1234', 'question': 'Q'}
    path = os.path.join('questions', 'foo', 'good.json')
    with open(path, 'w') as f:
        json.dump(data, f)
    # Patch select to quit
    monkeypatch.setattr(inquirer, 'select', lambda message, choices: type('C', (), {'execute': lambda self: 'Quit Quiz'})())
    cli.quiz_session('foo')
    out, _ = capsys.readouterr()
    # Valid file: should not print skip or no questions message
    assert "Skipping malformed" not in out
    assert "No foo questions found." not in out
    # cleanup done by fixture