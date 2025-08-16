from kubelingo import get_user_input


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
