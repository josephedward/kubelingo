import pytest
import os
import shutil
import tempfile
from unittest.mock import patch, MagicMock
import subprocess
import yaml

from kubelingo.modules.kubernetes.session import VimYamlEditor

@pytest.fixture
def editor():
    """Fixture to provide a VimYamlEditor instance."""
    return VimYamlEditor()

# 1. Unit tests for command-line construction
@pytest.mark.parametrize("vim_args, expected_flags, expected_scripts_count", [
    ([], [], 0),
    (["-es"], ["-es"], 0),
    (["/tmp/script1.vim"], [], 1),
    (["-es", "/tmp/script2.vim"], ["-es"], 1),
    (["-es", "/tmp/s1.vim", "/tmp/s2.vim"], ["-es"], 2)
])
@patch('subprocess.run')
def test_vim_command_construction(mock_run, editor, vim_args, expected_flags, expected_scripts_count, tmp_path):
    """Tests that vim command and arguments are constructed correctly."""
    script_paths = []
    processed_vim_args = []
    # Create fake script files and update paths
    for arg in vim_args:
        if arg.startswith('/tmp/'):
            script_file = tmp_path / os.path.basename(arg)
            script_file.touch()
            script_paths.append(str(script_file))
            processed_vim_args.append(str(script_file))
        else:
            processed_vim_args.append(arg)

    mock_run.return_value = MagicMock(returncode=0)
    editor.edit_yaml_with_vim("key: val", _vim_args=processed_vim_args)

    assert mock_run.called
    cmd = mock_run.call_args.args[0]

    assert cmd[0] == 'vim'
    # Check flags
    temp_file_index = 1 + len(expected_flags)
    assert cmd[1:temp_file_index] == expected_flags
    # Check temp file
    assert cmd[temp_file_index].endswith('.yaml')
    # Check script arguments
    script_args = cmd[temp_file_index+1:]
    assert len(script_args) == 2 * expected_scripts_count
    if expected_scripts_count > 0:
        assert all(script_args[i] == '-S' for i in range(0, len(script_args), 2))
        found_scripts = [script_args[i] for i in range(1, len(script_args), 2)]
        assert sorted(found_scripts) == sorted(script_paths)

# 2. Unit tests for failure branches
@patch('subprocess.run', side_effect=FileNotFoundError("editor not found"))
@patch('builtins.print')
def test_edit_yaml_editor_not_found(mock_print, mock_run, editor):
    """Tests behavior when the editor command is not found."""
    result = editor.edit_yaml_with_vim("foo: bar")
    assert result is None
    mock_print.assert_any_call("\x1b[31mError launching editor 'vim': editor not found\x1b[0m")

@patch('subprocess.run', side_effect=subprocess.TimeoutExpired(cmd="vim", timeout=1))
@patch('builtins.print')
def test_edit_yaml_editor_timeout(mock_print, mock_run, editor):
    """Tests behavior on editor timeout."""
    result = editor.edit_yaml_with_vim("foo: bar", _timeout=1)
    assert result is None
    mock_print.assert_any_call("\x1b[31mEditor session timed out after 1 seconds.\x1b[0m")

@patch('subprocess.run', side_effect=KeyboardInterrupt)
@patch('builtins.print')
def test_edit_yaml_editor_interrupt(mock_print, mock_run, editor):
    """Tests behavior on KeyboardInterrupt."""
    result = editor.edit_yaml_with_vim("foo: bar")
    assert result is None
    mock_print.assert_any_call("\x1b[33mEditor session interrupted by user.\x1b[0m")

@patch('subprocess.run')
@patch('yaml.safe_load', side_effect=yaml.YAMLError("bad yaml"))
@patch('builtins.print')
def test_edit_yaml_parsing_error(mock_print, mock_safe_load, mock_run, editor):
    """Tests behavior on YAML parsing error."""
    mock_run.return_value = MagicMock(returncode=0)
    result = editor.edit_yaml_with_vim("this is not yaml")
    assert result is None
    mock_print.assert_any_call("\x1b[31mFailed to parse YAML: bad yaml\x1b[0m")

# 3. Unit tests for the timeout-fallback logic
@patch('builtins.print')
def test_timeout_fallback_logic(mock_print, editor):
    """Tests fallback when subprocess.run doesn't support timeout."""
    call_count = 0
    def run_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if 'timeout' in kwargs and call_count == 1:
            raise TypeError("timeout is not supported")
        return MagicMock(returncode=0)

    with patch('subprocess.run', side_effect=run_side_effect) as mock_run:
        result = editor.edit_yaml_with_vim("key: val", _timeout=10)

        assert mock_run.call_count == 2
        assert 'timeout' in mock_run.call_args_list[0].kwargs
        assert 'timeout' not in mock_run.call_args_list[1].kwargs
        assert result == {"key": "val"}
        assert not mock_print.called

# 5. Edge-case tests
@patch.dict(os.environ, {"EDITOR": "my-fake-editor"})
@patch('subprocess.run')
def test_edit_yaml_respects_editor_env_var(mock_run, editor):
    """Ensures that the EDITOR environment variable is respected."""
    mock_run.return_value = MagicMock(returncode=0)
    editor.edit_yaml_with_vim("test: content")
    
    assert mock_run.called
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "my-fake-editor"

@patch.dict(os.environ, clear=True)
@patch('subprocess.run')
def test_edit_yaml_uses_default_vim_when_editor_unset(mock_run, editor):
    """Ensures that 'vim' is used when EDITOR is not set."""
    mock_run.return_value = MagicMock(returncode=0)
    editor.edit_yaml_with_vim("test: content")

    assert mock_run.called
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "vim"
