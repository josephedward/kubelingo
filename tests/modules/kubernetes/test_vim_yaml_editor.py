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
    assert "Error launching editor 'vim_not_installed'" in captured.out
    
@patch('kubelingo.modules.kubernetes.session.tempfile.NamedTemporaryFile')
@patch('kubelingo.modules.kubernetes.session.os.environ.get')
@patch('kubelingo.modules.kubernetes.session.subprocess.run')
def test_edit_yaml_with_vim_interrupt(mock_subprocess, mock_env_get, mock_tempfile, editor, capsys):
    """
    Tests handling of KeyboardInterrupt during the editor session.
    """
    # Arrange
    mock_env_get.return_value = 'vim'
    def simulate_interrupt(cmd, timeout=None):
        raise KeyboardInterrupt
    mock_subprocess.side_effect = simulate_interrupt

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
    assert "Editor session interrupted" in captured.out
