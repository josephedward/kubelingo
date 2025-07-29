from unittest.mock import patch, MagicMock

from kubelingo.bridge import RustBridge


@patch('pathlib.Path.exists')
def test_find_rust_binary_success(mock_exists):
    """Test that the Rust binary is found when it exists."""
    # The first path tried will "exist"
    mock_exists.side_effect = [True, False, False]

    bridge = RustBridge()

    assert bridge.is_available() is True
    assert "target/release/kubelingo" in bridge.rust_binary


@patch('pathlib.Path.exists', return_value=False)
def test_find_rust_binary_failure(mock_exists):
    """Test that is_available() returns False when no binary is found."""
    bridge = RustBridge()
    assert bridge.is_available() is False
    assert bridge.rust_binary is None


@patch('subprocess.run')
def test_run_pty_shell_success(mock_subprocess_run):
    """Test that run_pty_shell calls the Rust binary correctly."""
    mock_subprocess_run.return_value = MagicMock(returncode=0)

    with patch('pathlib.Path.exists', return_value=True):
        bridge = RustBridge()
        assert bridge.is_available() is True

        result = bridge.run_pty_shell()

        assert result is True
        mock_subprocess_run.assert_called_once_with([bridge.rust_binary, "pty"])


@patch('subprocess.run')
def test_run_pty_shell_failure(mock_subprocess_run):
    """Test that run_pty_shell returns False if the binary fails."""
    mock_subprocess_run.return_value = MagicMock(returncode=1)

    with patch('pathlib.Path.exists', return_value=True):
        bridge = RustBridge()
        result = bridge.run_pty_shell()

        assert result is False
        mock_subprocess_run.assert_called_once_with([bridge.rust_binary, "pty"])


@patch('subprocess.run', side_effect=Exception("Binary not found"))
def test_run_pty_shell_exception(mock_subprocess_run):
    """Test that run_pty_shell returns False on an exception."""
    with patch('pathlib.Path.exists', return_value=True):
        bridge = RustBridge()
        result = bridge.run_pty_shell()

        assert result is False
