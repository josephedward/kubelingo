import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from unittest.mock import patch, MagicMock
import logging

from kubelingo.modules.kubernetes.session import NewSession
from kubelingo.config import DEFAULT_DATA_FILE


@patch('kubelingo.modules.kubernetes.session.load_questions')
@patch('kubelingo.bridge.rust_bridge')
def test_command_quiz_rust_fallback(mock_rust_bridge, mock_load_questions):
    """Test that command quiz falls back to Python when Rust bridge is used but fails."""
    logger = logging.getLogger('test_logger')
    session = NewSession(logger)
    session.session_manager = MagicMock()

    args = MagicMock()
    args.review_only = False
    args.live = False
    args.file = DEFAULT_DATA_FILE
    args.category = "somecat"  # This makes it non-interactive
    args.num = 5

    mock_rust_bridge.is_available.return_value = True
    mock_rust_bridge.run_command_quiz.return_value = False  # Rust bridge fails

    # We don't want to run the whole quiz, just check the fallback happened.
    # So we'll let load_questions be called, but return no questions to stop execution.
    mock_load_questions.return_value = []

    with patch('builtins.print'):  # Silence the fallback warning message
        session._run_command_quiz(args)

    mock_rust_bridge.run_command_quiz.assert_called_once_with(args)
    mock_load_questions.assert_called_once_with(args.file)


@patch('kubelingo.modules.kubernetes.session.load_questions')
@patch('kubelingo.bridge.rust_bridge')
def test_command_quiz_rust_success(mock_rust_bridge, mock_load_questions):
    """Test that command quiz does NOT fall back to Python when Rust bridge succeeds."""
    logger = logging.getLogger('test_logger')
    session = NewSession(logger)
    session.session_manager = MagicMock()

    args = MagicMock()
    args.review_only = False
    args.live = False
    args.file = DEFAULT_DATA_FILE
    args.category = "somecat"
    args.num = 5

    mock_rust_bridge.is_available.return_value = True
    mock_rust_bridge.run_command_quiz.return_value = True  # Rust bridge succeeds

    session._run_command_quiz(args)

    mock_rust_bridge.run_command_quiz.assert_called_once_with(args)
    mock_load_questions.assert_not_called()
