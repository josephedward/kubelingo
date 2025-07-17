import pytest
from unittest.mock import patch
from kubelingo.modules.kubernetes.session import VimYamlEditor, vim_commands_quiz

# Fixture to provide a VimYamlEditor instance for tests
@pytest.fixture
def editor():
    """Provides a VimYamlEditor instance."""
    return VimYamlEditor()

# --- Tests for VimYamlEditor class ---

def test_edit_yaml_with_vim_success(editor):
    """
    Tests that edit_yaml_with_vim successfully returns edited content.
    Mocks the subprocess call to avoid launching a real editor and simulates
    the user saving valid YAML.
    """
    initial_yaml_obj = {"key": "initial_value"}
    edited_yaml_str = "key: edited_value"

    def simulate_vim_edit(cmd, check=True):
        """Mock for subprocess.run that simulates a user editing a file."""
        tmp_file_path = cmd[1]
        with open(tmp_file_path, 'w', encoding='utf-8') as f:
            f.write(edited_yaml_str)

    with patch('subprocess.run', side_effect=simulate_vim_edit) as mock_run:
        result = editor.edit_yaml_with_vim(initial_yaml_obj)

    mock_run.assert_called_once()
    assert result == {"key": "edited_value"}, "The returned YAML object should match the edited content."

def test_edit_yaml_with_vim_editor_not_found(editor, capsys):
    """
    Tests that edit_yaml_with_vim handles the editor command not being found.
    """
    initial_yaml_obj = {"key": "value"}
    with patch('subprocess.run', side_effect=FileNotFoundError("vim not found")) as mock_run:
        result = editor.edit_yaml_with_vim(initial_yaml_obj)

    mock_run.assert_called_once()
    assert result is None, "Function should return None when the editor fails to launch."
    captured = capsys.readouterr()
    assert "Error launching editor" in captured.out, "An error message should be printed to the user."

def test_edit_yaml_with_vim_invalid_yaml_after_edit(editor, capsys):
    """
    Tests that edit_yaml_with_vim handles a user saving invalid YAML syntax.
    """
    initial_yaml_obj = {"key": "initial_value"}
    invalid_yaml_str = "key: value\nthis: is: not: valid: yaml"

    def simulate_invalid_edit(cmd, check=True):
        """Mock that simulates a user saving a syntactically incorrect YAML file."""
        tmp_file_path = cmd[1]
        with open(tmp_file_path, 'w', encoding='utf-8') as f:
            f.write(invalid_yaml_str)

    with patch('subprocess.run', side_effect=simulate_invalid_edit):
        result = editor.edit_yaml_with_vim(initial_yaml_obj)

    assert result is None, "Function should return None for invalid YAML."
    captured = capsys.readouterr()
    assert "Failed to parse YAML" in captured.out, "A parsing error message should be printed."

# --- Tests for standalone vim_commands_quiz function ---

def test_vim_commands_quiz_flow(capsys):
    """
    Tests the basic flow of the vim_commands_quiz, simulating user input.
    """
    user_inputs = [
        "i",         # Correct
        "A",         # Incorrect
        "o",         # Correct
        ":wq",       # Correct
        ":q!",       # Correct
        "w",         # Incorrect
        "dd",        # Correct
        "Y",         # Incorrect
        "p",         # Correct
        "u",         # Correct
        "/pattern",  # Correct
        "n",         # Correct
        "gg",        # Correct
        "G",         # Correct
        "10G",       # Incorrect
    ]
    
    expected_score = 11.0 / 15.0
    
    with patch('builtins.input', side_effect=user_inputs):
        final_score = vim_commands_quiz()

    assert final_score == pytest.approx(expected_score)
    captured = capsys.readouterr()
    assert "Quiz Complete!" in captured.out
    assert "Your Score: 11/15" in captured.out
