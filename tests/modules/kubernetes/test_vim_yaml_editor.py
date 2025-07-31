import pytest
import os
from unittest.mock import patch, MagicMock
import subprocess
import yaml

from kubelingo.modules.kubernetes.vim_yaml_editor import VimYamlEditor

pytestmark = pytest.mark.skip(reason="YAML functionality not yet implemented")

# --- Fixtures ---

@pytest.fixture
def editor():
    """Provides a VimYamlEditor instance for testing."""
    return VimYamlEditor()

# --- Unit Tests: Success and Core Logic ---

@patch('kubelingo.modules.kubernetes.vim_yaml_editor.subprocess.run')
def test_edit_yaml_with_vim_success(mock_run, editor):
    """Tests successful editing of YAML content."""
    # Arrange
    initial_yaml_dict = {'key': 'value'}
    edited_yaml_str = "key: edited_value"
    
    # Simulate the editor writing to the temp file
    def side_effect(cmd, **kwargs):
        # The editor command includes the path to the temp file
        temp_file_path = next((arg for arg in cmd if arg.endswith('.yaml')), None)
        assert temp_file_path, "Temp file path not found in command"
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            f.write(edited_yaml_str)
        return MagicMock(returncode=0)
    
    mock_run.side_effect = side_effect

    # Act
    result_dict = editor.edit_yaml_with_vim(initial_yaml_dict)

    # Assert
    mock_run.assert_called_once()
    assert result_dict == {'key': 'edited_value'}

@patch('kubelingo.modules.kubernetes.vim_yaml_editor.subprocess.run')
@patch('builtins.input')
def test_edit_yaml_with_vim_includes_prompt(mock_input, mock_run, editor):
    """
    Tests that edit_yaml_with_vim prepends the prompt as commented lines.
    """
    # Arrange
    initial_yaml_str = "a: 1\nb: 2\n"
    prompt_text = "Test Prompt"
    written_content = []

    def side_effect(cmd, **kwargs):
        temp_file_path = next((arg for arg in cmd if arg.endswith('.yaml')), None)
        assert temp_file_path, "Temp file path not found in command"
        with open(temp_file_path, 'r', encoding='utf-8') as f:
            nonlocal written_content
            written_content = f.readlines()
        return MagicMock(returncode=0)

    mock_run.side_effect = side_effect

    # Act
    editor.edit_yaml_with_vim(initial_yaml_str, prompt=prompt_text)

    # Assert
    assert written_content[0] == f"# {prompt_text}\n"
    assert written_content[1] == "\n"
    assert written_content[2] == "a: 1\n"


# --- Unit Tests: Failure Scenarios ---

@patch('kubelingo.modules.kubernetes.vim_yaml_editor.subprocess.run', side_effect=FileNotFoundError("editor not found"))
@patch('builtins.print')
def test_edit_yaml_editor_not_found(mock_print, mock_run, editor):
    """Tests behavior when the editor command is not found."""
    result = editor.edit_yaml_with_vim("foo: bar")
    assert result is None
    mock_print.assert_any_call("\x1b[31mError launching editor 'vim': editor not found\x1b[0m")

@patch('kubelingo.modules.kubernetes.vim_yaml_editor.subprocess.run', side_effect=subprocess.TimeoutExpired(cmd="vim", timeout=1))
@patch('builtins.print')
def test_edit_yaml_editor_timeout(mock_print, mock_run, editor):
    """Tests behavior on editor timeout."""
    result = editor.edit_yaml_with_vim("foo: bar", _timeout=1)
    assert result is None
    mock_print.assert_any_call("\x1b[31mEditor session timed out after 1 seconds.\x1b[0m")

@patch('kubelingo.modules.kubernetes.vim_yaml_editor.subprocess.run', side_effect=KeyboardInterrupt)
@patch('builtins.print')
def test_edit_yaml_editor_interrupt(mock_print, mock_run, editor):
    """Tests behavior on KeyboardInterrupt."""
    result = editor.edit_yaml_with_vim("foo: bar")
    assert result is None
    mock_print.assert_any_call("\x1b[33mEditor session interrupted by user.\x1b[0m")

@patch('kubelingo.modules.kubernetes.vim_yaml_editor.subprocess.run')
@patch('kubelingo.modules.kubernetes.vim_yaml_editor.yaml.safe_load', side_effect=yaml.YAMLError("bad yaml"))
@patch('builtins.print')
def test_edit_yaml_parsing_error(mock_print, mock_safe_load, mock_run, editor):
    """Tests behavior on YAML parsing error."""
    mock_run.return_value = MagicMock(returncode=0)
    result = editor.edit_yaml_with_vim("this is not yaml")
    assert result is None
    mock_print.assert_any_call("\x1b[31mFailed to parse YAML: bad yaml\x1b[0m")

# --- Unit Tests: Advanced Logic ---

@pytest.mark.parametrize("vim_args, expected_flags, expected_scripts_count", [
    ([], [], 0),
    (["-es"], ["-es"], 0),
    (["/tmp/script1.vim"], [], 1),
    (["-es", "/tmp/script2.vim"], ["-es"], 1),
    (["-es", "/tmp/s1.vim", "/tmp/s2.vim"], ["-es"], 2)
])
@patch('kubelingo.modules.kubernetes.vim_yaml_editor.subprocess.run')
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
    # Patch the safe_load to avoid parsing errors with dummy content
    with patch('kubelingo.modules.kubernetes.vim_yaml_editor.yaml.safe_load'):
        editor.edit_yaml_with_vim("key: val", _vim_args=processed_vim_args)

    assert mock_run.called
    cmd = mock_run.call_args.args[0]

    assert cmd[0] == 'vim'

    # Check that a temp yaml file is in the command
    assert any(c.endswith('.yaml') for c in cmd), "No .yaml file found in command"

    # Check that script files are correctly passed with -S
    found_scripts = []
    for i, c in enumerate(cmd):
        if c == '-S' and i + 1 < len(cmd):
            found_scripts.append(cmd[i+1])
    assert len(found_scripts) == expected_scripts_count, "Incorrect number of script arguments"
    assert sorted(found_scripts) == sorted(script_paths), "Script paths do not match"

    # Check that non-script flags from _vim_args are present
    for flag in expected_flags:
        assert flag in cmd, f"Flag '{flag}' not found in command"


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

    with patch('kubelingo.modules.kubernetes.vim_yaml_editor.subprocess.run', side_effect=run_side_effect) as mock_run:
        result = editor.edit_yaml_with_vim("key: val", _timeout=10)

        assert mock_run.call_count == 2
        assert 'timeout' in mock_run.call_args_list[0].kwargs
        assert 'timeout' not in mock_run.call_args_list[1].kwargs
        assert result == {"key": "val"}
        assert not mock_print.called

@patch.dict(os.environ, {"EDITOR": "my-fake-editor"})
@patch('kubelingo.modules.kubernetes.vim_yaml_editor.subprocess.run')
def test_edit_yaml_respects_editor_env_var(mock_run, editor):
    """Ensures that the EDITOR environment variable is respected."""
    mock_run.return_value = MagicMock(returncode=0)
    with patch('kubelingo.modules.kubernetes.vim_yaml_editor.yaml.safe_load'):
        editor.edit_yaml_with_vim("test: content")
    
    assert mock_run.called
    cmd = mock_run.call_args.args[0]
    assert cmd[0] == "my-fake-editor"

@patch.dict(os.environ, clear=True)
@patch('kubelingo.modules.kubernetes.vim_yaml_editor.subprocess.run')
def test_edit_yaml_uses_default_vim_when_editor_unset(mock_run, editor):
    """Ensures that 'vim' is used when EDITOR is not set."""
    mock_run.return_value = MagicMock(returncode=0)
    with patch('kubelingo.modules.kubernetes.vim_yaml_editor.yaml.safe_load'):
        editor.edit_yaml_with_vim("test: content")

    assert mock_run.called
    cmd = mock_run.call_args.args[0]
    assert cmd[0] == "vim"
