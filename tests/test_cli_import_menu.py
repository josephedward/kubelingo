import os
import pytest
import kubelingo.cli as cli
from InquirerPy import inquirer

@pytest.fixture(autouse=True)
def no_questions_dir(tmp_path, monkeypatch):
    # Ensure cwd is clean and has no 'questions' directory by default
    monkeypatch.chdir(tmp_path)
    yield

def test_import_menu_no_questions_dir(capsys):
    # Call import_menu() in cwd without questions/ directory
    cli.import_menu()
    out, _ = capsys.readouterr()
    assert "No questions directory found." in out

def test_import_menu_back(monkeypatch, capsys):
    # Create empty questions directory
    os.makedirs('questions', exist_ok=True)
    # Patch select to choose Back
    monkeypatch.setattr(inquirer, 'select', lambda message, choices: type('X', (), {'execute': lambda self: 'Back'})())
    cli.import_menu()
    out, _ = capsys.readouterr()
    # Should not print any importing message
    assert out.strip() == ''
