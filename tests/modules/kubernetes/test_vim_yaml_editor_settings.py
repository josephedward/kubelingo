import tempfile
from pathlib import Path
import pytest

from kubelingo.modules.kubernetes.vim_yaml_editor import VimYamlEditor

@pytest.fixture(autouse=True)
def disable_actual_editor(monkeypatch):
    # Ensure EDITOR defaults to vim to trigger vimrc logic
    monkeypatch.setenv('EDITOR', 'vim')
    yield

def test_vimrc_contains_two_space_settings(tmp_path, monkeypatch):
    editor = VimYamlEditor()
    # Simple YAML content for editing
    yaml_content = "key: value"
    # Prepare exercise file path (Vim will open this, though fake_run ignores it)
    exercise_file = tmp_path / "exercise.yaml"
    # Capture arguments passed to subprocess.run
    captured = {}

    def fake_run(cmd, timeout=None, **kwargs):
        # Save the command invocation for inspection
        captured['cmd'] = cmd
        # Ensure vimrc flag is present
        assert '-u' in cmd
        uidx = cmd.index('-u')
        vimrc_file = cmd[uidx + 1]
        # Read the generated vimrc content
        content = Path(vimrc_file).read_text(encoding='utf-8')
        captured['vimrc_content'] = content
        # Simulate successful editor exit
        class Result:
            returncode = 0

        return Result()

    # Patch subprocess.run in vim_yaml_editor to our fake
    monkeypatch.setattr(
        'kubelingo.modules.kubernetes.vim_yaml_editor.subprocess.run',
        fake_run
    )
    # Patch input to skip prompts
    monkeypatch.setattr('builtins.input', lambda prompt='': '')

    # Invoke the editor; prompt arg is optional
    result = editor.edit_yaml_with_vim(yaml_content, filename=str(exercise_file), prompt=None)
    # Should parse YAML correctly
    assert isinstance(result, dict)
    assert result.get('key') == 'value'

    # Verify vimrc settings were written
    vimrc = captured.get('vimrc_content', '')
    assert 'set expandtab' in vimrc
    assert 'set tabstop=2' in vimrc
    assert 'set shiftwidth=2' in vimrc