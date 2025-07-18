import pytest
from unittest.mock import patch
from kubelingo.modules.kubernetes.session import VimYamlEditor

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

import pytest
from unittest.mock import patch, MagicMock
import subprocess
import yaml

from kubelingo.modules.kubernetes.session import VimYamlEditor

@pytest.fixture
def editor():
    """Provides a VimYamlEditor instance for testing."""
    return VimYamlEditor()

@patch('kubelingo.modules.kubernetes.session.tempfile.NamedTemporaryFile')
@patch('kubelingo.modules.kubernetes.session.os.environ.get')
@patch('kubelingo.modules.kubernetes.session.subprocess.run')
@patch('kubelingo.modules.kubernetes.session.os.unlink')
@patch('builtins.open')
def test_edit_yaml_with_vim_success(mock_open, mock_unlink, mock_subprocess, mock_env_get, mock_tempfile, editor):
    """
    Tests successful editing of YAML content with Vim.
    """
    # Arrange
    mock_env_get.return_value = 'vim'
    mock_subprocess.return_value = MagicMock(returncode=0)
    
    mock_file_obj = MagicMock()
    mock_file_obj.name = "/tmp/fakefile.yaml"
    
    # Mock temp file context manager
    mock_temp_context = MagicMock()
    mock_temp_context.__enter__.return_value = mock_file_obj
    mock_tempfile.return_value = mock_temp_context

    initial_yaml_dict = {'key': 'value'}
    edited_yaml_str = "key: edited_value"

    # Simulate reading the file after editing.
    mock_read_file = MagicMock()
    mock_read_file.read.return_value = edited_yaml_str
    mock_read_file_context = MagicMock()
    mock_read_file_context.__enter__.return_value = mock_read_file
    mock_open.return_value = mock_read_file_context

    # Act
    result_dict = editor.edit_yaml_with_vim(initial_yaml_dict)

    # Assert
    mock_subprocess.assert_called_once_with(['vim', '/tmp/fakefile.yaml'], timeout=300)
    mock_open.assert_called_once_with('/tmp/fakefile.yaml', 'r', encoding='utf-8')
    assert result_dict == {'key': 'edited_value'}
    mock_unlink.assert_called_once_with("/tmp/fakefile.yaml")


@patch('kubelingo.modules.kubernetes.session.tempfile.NamedTemporaryFile')
@patch('kubelingo.modules.kubernetes.session.os.environ.get')
@patch('kubelingo.modules.kubernetes.session.subprocess.run')
def test_edit_yaml_with_vim_timeout(mock_subprocess, mock_env_get, mock_tempfile, editor, capsys):
    """
    Tests that the editor session correctly times out.
    """
    # Arrange
    mock_env_get.return_value = 'vim'
    mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd='vim', timeout=300)

    mock_file_obj = MagicMock()
    mock_file_obj.name = "/tmp/fakefile.yaml"
    mock_temp_context = MagicMock()
    mock_temp_context.__enter__.return_value = mock_file_obj
    mock_tempfile.return_value = mock_temp_context
    
    # Act
    result = editor.edit_yaml_with_vim("key: val")

    # Assert
    assert result is None
    captured = capsys.readouterr()
    assert "Editor session timed out" in captured.out


@patch('kubelingo.modules.kubernetes.session.tempfile.NamedTemporaryFile')
@patch('kubelingo.modules.kubernetes.session.os.environ.get')
@patch('kubelingo.modules.kubernetes.session.subprocess.run')
def test_edit_yaml_with_vim_editor_not_found(mock_subprocess, mock_env_get, mock_tempfile, editor, capsys):
    """
    Tests handling of FileNotFoundError when the editor is not found.
    """
    # Arrange
    mock_env_get.return_value = 'vim_not_installed'
    mock_subprocess.side_effect = FileNotFoundError

    mock_file_obj = MagicMock()
    mock_file_obj.name = "/tmp/fakefile.yaml"
    mock_temp_context = MagicMock()
    mock_temp_context.__enter__.return_value = mock_file_obj
    mock_tempfile.return_value = mock_temp_context
    
    # Act
    result = editor.edit_yaml_with_vim("key: val")

    # Assert
    assert result is None
    captured = capsys.readouterr()
    assert "Error: Editor 'vim_not_installed' not found." in captured.out
