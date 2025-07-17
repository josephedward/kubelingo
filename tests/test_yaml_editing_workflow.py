import pytest
from unittest.mock import patch
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
    def simulate_vim_edit(cmd, check=True):
        tmp_file_path = cmd[1]
        with open(tmp_file_path, 'w', encoding='utf-8') as f:
            f.write(question['correct_yaml'])

    with patch('kubelingo.modules.kubernetes.session.subprocess.run', side_effect=simulate_vim_edit):
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

    def simulate_vim_edit_retry(cmd, check=True):
        tmp_file_path = cmd[1]
        output_to_write = editor_outputs.pop(0)
        with open(tmp_file_path, 'w', encoding='utf-8') as f:
            f.write(output_to_write)

    # Mock user input: 'y' to retry.
    with patch('builtins.input', side_effect=['y']) as mock_input, \
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

    def simulate_vim_edit_fail(cmd, check=True):
        tmp_file_path = cmd[1]
        with open(tmp_file_path, 'w', encoding='utf-8') as f:
            f.write(incorrect_yaml)

    # Mock user input: 'n' to not retry.
    with patch('builtins.input', side_effect=['n']) as mock_input, \
         patch('kubelingo.modules.kubernetes.session.subprocess.run', side_effect=simulate_vim_edit_fail):
        success = editor.run_yaml_edit_question(question, index=3)

    assert success is False

    captured = capsys.readouterr()
    assert "❌ YAML does not match expected output." in captured.out
    mock_input.assert_called_once_with("Try again? (y/N): ")
    assert "✅ Correct!" not in captured.out
    # Check if the expected solution is printed at the end
    assert "Expected solution:" in captured.out
    assert "labels:\n    app: my-app" in captured.out
