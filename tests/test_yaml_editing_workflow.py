import pytest
from unittest.mock import patch, Mock
from kubelingo.modules.kubernetes.session import VimYamlEditor

@pytest.fixture
def editor():
    """Provides a VimYamlEditor instance for tests."""
    return VimYamlEditor()

def test_yaml_editing_workflow_success_first_try(editor, capsys):
    """
    Tests the end-to-end workflow for a single YAML editing question
    where the user provides the correct answer on the first attempt.
    """
    question = {
        'prompt': 'Create a basic Nginx pod.',
        'starting_yaml': 'apiVersion: v1\nkind: Pod\nmetadata:\n  name: placeholder',
        'correct_yaml': 'apiVersion: v1\nkind: Pod\nmetadata:\n  name: nginx-pod'
    }

    # This mock simulates the user editing the file correctly.
    def simulate_vim_edit(cmd, check=True, timeout=None):
        tmp_file_path = cmd[1]
        with open(tmp_file_path, 'w', encoding='utf-8') as f:
            f.write(question['correct_yaml'])
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    # Mock all possible input prompts
    with patch('kubelingo.modules.kubernetes.session.subprocess.run', side_effect=simulate_vim_edit), \
         patch('builtins.input', return_value='n'):  # Don't retry on any prompts
        success = editor.run_yaml_edit_question(question, index=1)

    assert success is True

    captured = capsys.readouterr()
    # Check for prompt, validation, and success message
    assert "=== Exercise 1: Create a basic Nginx pod. ===" in captured.out
    assert "✅ Correct!" in captured.out
    assert "❌ YAML does not match expected output." not in captured.out

def test_yaml_editing_workflow_fail_and_retry_success(editor, capsys):
    """
    Tests the workflow where the user fails, retries, and then succeeds.
    """
    question = {
        'prompt': 'Fix the deployment replicas.',
        'starting_yaml': 'apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: my-app\nspec:\n  replicas: 1',
        'correct_yaml': 'apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: my-app\nspec:\n  replicas: 3'
    }

    # Simulate user first providing wrong yaml, then correct one.
    incorrect_yaml = 'apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: my-app\nspec:\n  replicas: 2'
    editor_outputs = [incorrect_yaml, question['correct_yaml']]

    def simulate_vim_edit_retry(cmd, check=True, timeout=None):
        tmp_file_path = cmd[1]
        output_to_write = editor_outputs.pop(0)
        with open(tmp_file_path, 'w', encoding='utf-8') as f:
            f.write(output_to_write)
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    # Mock user input: 'y' to retry, then 'n' to stop
    with patch('builtins.input', side_effect=['y', 'n']) as mock_input, \
         patch('kubelingo.modules.kubernetes.session.subprocess.run', side_effect=simulate_vim_edit_retry):
        success = editor.run_yaml_edit_question(question, index=2)

    assert success is True

    captured = capsys.readouterr()
    # First attempt should show mismatch and prompt for retry.
    assert "❌ YAML does not match expected output." in captured.out
    mock_input.assert_called_once_with("Try again? (y/N): ")
    # Second attempt should be correct.
    assert "✅ Correct!" in captured.out

def test_yaml_editing_workflow_fail_and_no_retry(editor, capsys):
    """
    Tests the workflow where the user fails and chooses not to retry,
    and verifies the correct solution is shown.
    """
    question = {
        'prompt': 'Add a label to the service.',
        'starting_yaml': 'apiVersion: v1\nkind: Service\nmetadata:\n  name: my-service',
        'correct_yaml': 'apiVersion: v1\nkind: Service\nmetadata:\n  name: my-service\n  labels:\n    app: my-app'
    }

    incorrect_yaml = 'apiVersion: v1\nkind: Service\nmetadata:\n  name: my-service\n  annotations:\n    some: annotation'

    def simulate_vim_edit_fail(cmd, check=True, timeout=None):
        tmp_file_path = cmd[1]
        with open(tmp_file_path, 'w', encoding='utf-8') as f:
            f.write(incorrect_yaml)
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    # Mock user input: 'n' to not retry.
    with patch('builtins.input', side_effect=['n', 'n']) as mock_input, \
         patch('kubelingo.modules.kubernetes.session.subprocess.run', side_effect=simulate_vim_edit_fail):
        success = editor.run_yaml_edit_question(question, index=3)

    assert success is False

    captured = capsys.readouterr()
    # Check for expected solution display
    assert "Expected solution:" in captured.out
    assert "labels:" in captured.out

def test_edit_yaml_with_vim_success(editor):
    """
    Tests that edit_yaml_with_vim successfully returns edited content.
    Mocks the subprocess call to avoid launching a real editor and simulates
    the user saving valid YAML.
    """
    initial_yaml_obj = {"key": "initial_value"}
    edited_yaml_str = "key: edited_value"

    def simulate_vim_edit(cmd, check=True, timeout=None):
        """Mock for subprocess.run that simulates a user editing a file."""
        tmp_file_path = cmd[1]
        with open(tmp_file_path, 'w', encoding='utf-8') as f:
            f.write(edited_yaml_str)
        # Return a proper CompletedProcess-like object
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    with patch('kubelingo.modules.kubernetes.session.subprocess.run', side_effect=simulate_vim_edit) as mock_run:
        result = editor.edit_yaml_with_vim(initial_yaml_obj)

    mock_run.assert_called_once()
    assert result == {"key": "edited_value"}, "The returned YAML object should match the edited content."

def test_edit_yaml_with_vim_editor_not_found(editor, capsys):
    """
    Tests that edit_yaml_with_vim handles the editor command not being found.
    """
    initial_yaml_obj = {"key": "value"}
    with patch('kubelingo.modules.kubernetes.session.subprocess.run', side_effect=FileNotFoundError("vim not found")) as mock_run:
        result = editor.edit_yaml_with_vim(initial_yaml_obj)

    mock_run.assert_called_once()
    assert result is None, "Function should return None when the editor fails to launch."
    captured = capsys.readouterr()
    # Check for the actual error message format
    assert ("Error: Editor" in captured.out or "Error launching editor" in captured.out), "An error message should be printed to the user."

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
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    with patch('kubelingo.modules.kubernetes.session.subprocess.run', side_effect=simulate_invalid_edit):
        result = editor.edit_yaml_with_vim(initial_yaml_obj)

    assert result is None, "Function should return None for invalid YAML."
    captured = capsys.readouterr()
    # Check for actual error message format
    assert ("Failed to parse YAML" in captured.out or "Failed to process YAML" in captured.out), "A parsing error message should be printed."
