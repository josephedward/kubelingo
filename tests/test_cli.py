import sys
from unittest.mock import patch, MagicMock

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
        with pytest.raises(SystemExit):
            main()
        # It should call show_modules and then exit
        mock_show_modules.assert_called_once()


@patch('kubelingo.cli.load_session')
def test_cli_k8s_module_argument(mock_load_session):
    """Test that `kubelingo --k8s` loads the kubernetes module."""
    mock_session = MagicMock()
    mock_session.initialize.return_value = True
    mock_load_session.return_value = mock_session

    with patch.object(sys, 'argv', ['kubelingo', '--k8s']):
        try:
            main()
        except SystemExit:
            pass

    # Check that 'kubernetes' was passed to load_session
    mock_load_session.assert_called_with('kubernetes', pytest.anything())
