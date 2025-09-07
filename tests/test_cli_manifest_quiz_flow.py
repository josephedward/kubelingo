import pytest
import webbrowser
import kubelingo.cli as cli
from rich.console import Console
from unittest.mock import MagicMock, call, patch
import builtins
import os

class FakeAnswer:
    """Fake answer for InquirerPy prompts."""
    def __init__(self, value):
        self._value = value
    def execute(self):
        return self._value

def test_manifest_editor_flow(monkeypatch, capsys):
    # Mock QuestionGenerator.generate_question_set (though not directly used in this flow, it's good practice to mock)
    original_manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: my-pod
spec:
  containers:
  - name: my-container
    image: nginx:latest"""
    
    modified_manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: my-pod-modified
spec:
  containers:
  - name: my-container
    image: nginx:1.20"""

    def mock_generate_question_set(self, count, question_type, subject_matter):
        return [{
            'id': 'test-manifest-id',
            'topic': subject_matter,
            'question_type': question_type,
            'question': "Edit the following manifest to change the pod name and image version:",
            'suggested_answer': original_manifest
        }]
    monkeypatch.setattr(cli.QuestionGenerator, 'generate_question_set', mock_generate_question_set)
    
    # Prevent actual browser opens
    monkeypatch.setattr(webbrowser, 'open', lambda url: None)

    # Mock _open_manifest_editor to allow assertions on its calls, while still executing its original logic
    original_open_manifest_editor = cli._open_manifest_editor
    mock_open_manifest_editor = MagicMock(side_effect=original_open_manifest_editor)
    monkeypatch.setattr(cli, '_open_manifest_editor', mock_open_manifest_editor)

    # Mock os.system to prevent actual editor from opening and to simulate writing to the temp file
    def mock_os_system(command):
        # Extract the temporary file path from the command
        parts = command.split()
        temp_file_path = parts[-1] # Assuming the last part is the file path
        
        # Simulate the editor writing the modified content to the temp file
        with open(temp_file_path, 'w') as f:
            f.write(modified_manifest)
    
    monkeypatch.setattr(os, 'system', mock_os_system)
    
    # Mock tempfile.NamedTemporaryFile to control the temporary file path and ensure it's cleaned up
    mock_tmp_file = MagicMock()
    mock_tmp_file.name = "/tmp/test_manifest.yaml" # A dummy path for testing
    mock_tmp_file.__enter__.return_value = mock_tmp_file
    mock_tmp_file.__exit__.return_value = None # Ensure __exit__ is called
    monkeypatch.setattr(cli.tempfile, 'NamedTemporaryFile', MagicMock(return_value=mock_tmp_file))
    
    # Mock os.remove to prevent actual file deletion during test cleanup
    monkeypatch.setattr(os, 'remove', MagicMock())
    
    # Mock ai_chat (though not directly used in this flow, it's good practice to mock)
    mock_ai_chat = MagicMock(return_value="AI feedback: Good changes!")
    monkeypatch.setattr(cli, 'ai_chat', mock_ai_chat)
    monkeypatch.setattr(cli._llm_utils, 'ai_chat', mock_ai_chat) # Also mock the internal usage

    # Prepare inquirer responses:
    # 1. Main Menu: Quiz
    # 2. Quiz Type: Declarative (Manifests)
    # 3. Subject Matter: pods
    mock_inquirer_select = MagicMock(side_effect=[
        FakeAnswer('Quiz'),                    # Main Menu: Quiz
        FakeAnswer('Declarative (Manifests)'), # Quiz type
        FakeAnswer('pods'),                    # Topic
    ])
    monkeypatch.setattr(cli.inquirer, 'select', mock_inquirer_select)
    
    # No inquirer.text for number of questions in this flow
    # No builtins.input for post-answer menu in this flow

    # Capture console.print outputs
    printed = []
    mock_console_instance = Console()
    monkeypatch.setattr(mock_console_instance, 'print', lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)))

    # Run the quiz menu for manifest flow
    cli.quiz_menu()

    # Assertions
    # Verify that _open_manifest_editor was called
    mock_open_manifest_editor.assert_called_once_with(template="")
    
    # Verify that os.system was called with the editor command
    mock_os_system.assert_called_once()
    args, kwargs = mock_os_system.call_args
    assert args[0].startswith(os.environ.get('EDITOR', 'vim'))
    assert args[0].endswith(mock_tmp_file.name)

    # Verify output
    captured = capsys.readouterr()
    combined_output = captured.out + "\n".join(printed)
    assert "Manifest edited:" in combined_output
    assert modified_manifest in combined_output

    # AI chat should NOT be called in this flow, as it exits after manifest editing
    mock_ai_chat.assert_not_called()

    # The quiz session finished message should NOT be present in this flow
    assert "Quiz session finished." not in combined_output
