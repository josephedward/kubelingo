import sys
from unittest.mock import patch, MagicMock, ANY

import pytest

from kubelingo.cli import main


@patch('kubelingo.cli.show_history')
def test_cli_history_argument(mock_show_history):
    """Test that `kubelingo --history` calls show_history()."""
    with patch.object(sys, 'argv', ['kubelingo', '--history']):
        # main() contains a loop, so we expect it to break after this command.
        try:
            main()
        except SystemExit:
            pass
        mock_show_history.assert_called_once()


@patch('kubelingo.cli.show_modules')
def test_cli_list_modules_argument(mock_show_modules):
    """Test that `kubelingo --list-modules` calls show_modules()."""
    with patch.object(sys, 'argv', ['kubelingo', '--list-modules']):
        main()
        # It should call show_modules and then exit the loop
        mock_show_modules.assert_called_once()


@patch('questionary.select', autospec=True)
@patch('kubelingo.cli.load_session')
def test_cli_k8s_module_argument(mock_load_session, mock_select):
    """Test that `kubelingo --k8s` loads the kubernetes module."""
    mock_session = MagicMock()
    mock_session.initialize.return_value = True
    mock_load_session.return_value = mock_session

    with patch.object(sys, 'argv', ['kubelingo', '--k8s']):
        main()

    # Check that 'kubernetes' was passed to load_session
    mock_load_session.assert_called_with('kubernetes', ANY)


@patch('kubelingo.sandbox.spawn_pty_shell')
def test_cli_sandbox_pty(mock_spawn_pty_shell):
    """Test that `kubelingo sandbox pty` calls spawn_pty_shell()."""
    with patch.object(sys, 'argv', ['kubelingo', 'sandbox', 'pty']):
        main()
    mock_spawn_pty_shell.assert_called_once()


@patch('kubelingo.sandbox.launch_container_sandbox')
def test_cli_sandbox_docker(mock_launch_container_sandbox):
    """Test that `kubelingo sandbox docker` calls launch_container_sandbox()."""
    with patch.object(sys, 'argv', ['kubelingo', 'sandbox', 'docker']):
        main()
    mock_launch_container_sandbox.assert_called_once()


@patch('kubelingo.sandbox.spawn_pty_shell')
def test_cli_sandbox_default_is_pty(mock_spawn_pty_shell):
    """Test that `kubelingo sandbox` defaults to pty."""
    with patch.object(sys, 'argv', ['kubelingo', 'sandbox']):
        main()
    mock_spawn_pty_shell.assert_called_once()


@patch('kubelingo.sandbox.spawn_pty_shell')
def test_cli_legacy_pty_flag(mock_spawn_pty_shell, capsys):
    """Test that `kubelingo --pty` calls spawn_pty_shell() and warns."""
    with patch.object(sys, 'argv', ['kubelingo', '--pty']):
        main()
    mock_spawn_pty_shell.assert_called_once()
    captured = capsys.readouterr()
    assert "deprecated" in captured.err.lower()


@patch('kubelingo.sandbox.launch_container_sandbox')
def test_cli_legacy_docker_flag(mock_launch_container_sandbox, capsys):
    """Test that `kubelingo --docker` calls launch_container_sandbox() and warns."""
    with patch.object(sys, 'argv', ['kubelingo', '--docker']):
        main()
    mock_launch_container_sandbox.assert_called_once()
    captured = capsys.readouterr()
    assert "deprecated" in captured.err.lower()


@patch('kubelingo.database.get_db_connection')
@patch('kubelingo.modules.kubernetes.session.load_questions', return_value=[])
@patch('kubelingo.bridge.rust_bridge')
def test_cli_k8s_quiz_rust_bridge_success(mock_rust_bridge, mock_load_questions, mock_get_db_connection):
    """Test that if Rust bridge succeeds, Python quiz does not run."""
    mock_rust_bridge.is_available.return_value = True
    mock_rust_bridge.run_command_quiz.return_value = True

    with patch.object(sys, 'argv', ['kubelingo', '--k8s', '-n', '1']):
        main()

    mock_rust_bridge.run_command_quiz.assert_called_once()
    mock_load_questions.assert_not_called()


@patch('kubelingo.database.get_db_connection')
@patch('kubelingo.modules.kubernetes.session.load_questions', return_value=[])
@patch('kubelingo.bridge.rust_bridge')
def test_cli_k8s_quiz_rust_bridge_fail_fallback(mock_rust_bridge, mock_load_questions, mock_get_db_connection, capsys):
    """Test that if Rust bridge fails, Python quiz runs as a fallback."""
    mock_rust_bridge.is_available.return_value = True
    mock_rust_bridge.run_command_quiz.return_value = False

    with patch.object(sys, 'argv', ['kubelingo', '--k8s', '-n', '1']):
        main()

    mock_rust_bridge.run_command_quiz.assert_called_once()
    mock_load_questions.assert_called_once()
    captured = capsys.readouterr()
    assert "Rust command quiz execution failed" in captured.out


@patch('kubelingo.database.get_db_connection')
@patch('kubelingo.modules.kubernetes.session.load_questions', return_value=[])
@patch('kubelingo.bridge.rust_bridge')
def test_cli_k8s_quiz_rust_bridge_unavailable_fallback(mock_rust_bridge, mock_load_questions, mock_get_db_connection, capsys):
    """Test that if Rust bridge is unavailable, Python quiz runs."""
    mock_rust_bridge.is_available.return_value = False

    with patch.object(sys, 'argv', ['kubelingo', '--k8s', '-n', '1']):
        main()

    mock_rust_bridge.run_command_quiz.assert_not_called()
    mock_load_questions.assert_called_once()
    captured = capsys.readouterr()
    assert "Rust command quiz execution failed" not in captured.out
