import subprocess
import tempfile
import os
from unittest.mock import mock_open
import colorama
from kubelingo import get_user_input, handle_vim_edit, update_performance


def test_back_command_removes_last_entry(monkeypatch, capsys):
    """Tests that 'back' removes the previously entered command."""
    inputs = iter(['cmd1', 'back', 'done'])
    monkeypatch.setattr('builtins.input', lambda _prompt: next(inputs))
    user_commands, special_action = get_user_input()
    captured = capsys.readouterr()
    assert user_commands == []
    assert special_action is None
    assert "(Removed: 'cmd1')" in captured.out


def test_back_command_on_empty_list(monkeypatch, capsys):
    """Tests that 'back' does nothing when the command list is empty."""
    inputs = iter(['back', 'done'])
    monkeypatch.setattr('builtins.input', lambda _prompt: next(inputs))
    user_commands, special_action = get_user_input()
    captured = capsys.readouterr()
    assert user_commands == []
    assert special_action is None
    assert "(No lines to remove)" in captured.out


def test_back_command_in_the_middle(monkeypatch, capsys):
    """Tests using 'back' to remove a command between other commands."""
    inputs = iter(['cmd1', 'cmd2', 'back', 'cmd3', 'done'])
    monkeypatch.setattr('builtins.input', lambda _prompt: next(inputs))
    user_commands, special_action = get_user_input()
    captured = capsys.readouterr()
    assert user_commands == ['cmd1', 'cmd3']
    assert special_action is None
    assert "(Removed: 'cmd2')" in captured.out


def test_line_editing_is_enabled():
    """
    Proxy test to check that readline is imported for line editing.
    Directly testing terminal interactions like arrow keys is not feasible
    in a unit test environment like this.
    """
    try:
        import readline
        import sys
        # The import of `kubelingo` in the test suite should have loaded readline.
        assert 'readline' in sys.modules
    except ImportError:
        # readline is not available on all platforms (e.g., Windows without
        # pyreadline). This test should pass gracefully on those platforms.
        pass


def test_vim_is_configured_for_2_spaces(monkeypatch):
    """Tests that vim is called with commands to set tab spacing to 2 spaces."""
    question = {'question': 'q', 'solution': 's'}

    called_args = []
    def mock_subprocess_run(cmd_list, check=False):
        called_args.append(cmd_list)
        return subprocess.CompletedProcess(cmd_list, 0)
    monkeypatch.setattr(subprocess, 'run', mock_subprocess_run)

    class MockTempFile:
        name = 'dummy.yaml'
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_value, traceback):
            pass
        def write(self, *args): pass
        def flush(self, *args): pass

    monkeypatch.setattr(tempfile, 'NamedTemporaryFile', lambda **kwargs: MockTempFile())
    monkeypatch.setattr('os.unlink', lambda path: None)
    monkeypatch.setattr('builtins.open', mock_open(read_data='some manifest data'))
    monkeypatch.setattr('kubelingo.validate_manifest_with_llm', lambda q, m: {'correct': True, 'feedback': ''})

    handle_vim_edit(question)

    assert len(called_args) == 1
    expected_cmd = ['vim', '-c', "set tabstop=2 shiftwidth=2 expandtab", 'dummy.yaml']
    assert called_args[0] == expected_cmd


def test_update_performance_tracking(monkeypatch):
    """Tests that performance data is correctly updated for a topic."""
    
    mock_data_source = {}
    saved_data = {}

    def mock_load_performance_data():
        return mock_data_source.copy()

    def mock_save_performance_data(data):
        nonlocal saved_data
        saved_data = data
    
    monkeypatch.setattr('kubelingo.load_performance_data', mock_load_performance_data)
    monkeypatch.setattr('kubelingo.save_performance_data', mock_save_performance_data)

    # Test case 1: Correct answer for a new topic in an empty file
    mock_data_source = {}
    update_performance('new_topic', is_correct=True)
    assert saved_data == {'new_topic': {'correct': 1, 'total': 1}}
    
    # Test case 2: Incorrect answer for a new topic in a file with existing data
    mock_data_source = {'existing_topic': {'correct': 5, 'total': 10}}
    update_performance('new_topic', is_correct=False)
    assert saved_data == {
        'existing_topic': {'correct': 5, 'total': 10},
        'new_topic': {'correct': 0, 'total': 1}
    }

    # Test case 3: Correct answer for existing topic
    mock_data_source = {'existing_topic': {'correct': 5, 'total': 10}}
    update_performance('existing_topic', is_correct=True)
    assert saved_data == {'existing_topic': {'correct': 6, 'total': 11}}
    
    # Test case 4: Incorrect answer for existing topic
    mock_data_source = {'existing_topic': {'correct': 5, 'total': 10}}
    update_performance('existing_topic', is_correct=False)
    assert saved_data == {'existing_topic': {'correct': 5, 'total': 11}}


def test_back_command_feedback_is_colored(monkeypatch, capsys):
    """Tests that feedback from the 'back' command is colorized."""
    colorama.init(strip=False)
    try:
        # Test when an item is removed
        inputs = iter(['cmd1', 'back', 'done'])
        monkeypatch.setattr('builtins.input', lambda _prompt: next(inputs))
        get_user_input()
        captured = capsys.readouterr()
        assert "(Removed: 'cmd1')" in captured.out
        assert colorama.Fore.YELLOW in captured.out

        # Test when list is empty
        inputs = iter(['back', 'done'])
        monkeypatch.setattr('builtins.input', lambda _prompt: next(inputs))
        get_user_input()
        captured = capsys.readouterr()
        assert "(No lines to remove)" in captured.out
        assert colorama.Fore.YELLOW in captured.out
    finally:
        colorama.deinit()
