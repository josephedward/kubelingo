from unittest.mock import patch, MagicMock

import pytest

from kubelingo.sandbox import spawn_pty_shell, launch_container_sandbox


@patch('sys.stdout.isatty', return_value=True)
@patch('pty.spawn')
@patch('kubelingo.bridge.rust_bridge')
def test_spawn_pty_shell_python_fallback(mock_rust_bridge, mock_pty_spawn, mock_isatty):
    """Test that spawn_pty_shell uses Python's pty.spawn as a fallback."""
    mock_rust_bridge.is_available.return_value = True
    mock_rust_bridge.run_pty_shell.return_value = False  # Rust fails

    spawn_pty_shell()

    mock_rust_bridge.run_pty_shell.assert_called_once()
    # Ensure Python pty.spawn fallback is invoked with bash login and custom init-file
    mock_pty_spawn.assert_called_once()
    # Extract the command list passed to pty.spawn
    args, _ = mock_pty_spawn.call_args
    cmd = args[0]
    assert isinstance(cmd, list)
    # Must invoke bash with --login
    assert cmd[0] == 'bash'
    assert '--login' in cmd
    # Must include a custom init-file flag
    assert '--init-file' in cmd


@patch('shutil.which', return_value='/usr/bin/docker')
@patch('subprocess.run')
@patch('os.path.exists', return_value=True)
def test_launch_container_sandbox(mock_path_exists, mock_subprocess_run, mock_shutil_which):
    """Test that launch_container_sandbox calls Docker correctly."""
    # Mock docker info, image inspect, and docker run
    mock_subprocess_run.side_effect = [
        MagicMock(returncode=0),  # docker info
        MagicMock(returncode=0),  # docker image inspect
        MagicMock(returncode=0),  # docker run
    ]

    launch_container_sandbox()

    assert mock_subprocess_run.call_count == 3
    run_call = mock_subprocess_run.call_args_list[2]
    cmd_list = run_call.args[0]
    assert 'docker' in cmd_list
    assert 'run' in cmd_list
    assert '--rm' in cmd_list
    assert '-it' in cmd_list
    assert 'kubelingo/sandbox:latest' in cmd_list


@patch('shutil.which', return_value=None)
@patch('builtins.print')
def test_launch_container_sandbox_no_docker(mock_print, mock_shutil_which):
    """Test sandbox launch fails gracefully if docker is not installed."""
    launch_container_sandbox()
    mock_shutil_which.assert_called_once_with('docker')

    # Check that a message containing "Docker not found" was printed.
    # This avoids failing on exact string matches with ANSI color codes.
    found_message = False
    for call in mock_print.call_args_list:
        if "Docker not found" in call.args[0]:
            found_message = True
            break
    assert found_message, "Expected 'Docker not found' message was not printed."
