import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add repo root to sys.path to allow importing kubelingo_tools from the scripts directory
repo_root = Path(__file__).resolve().parent.parent.parent
scripts_path = repo_root / 'scripts'
sys.path.insert(0, str(scripts_path))

import kubelingo_tools


@pytest.fixture
def mock_run_script():
    """Fixture to mock the _run_script helper function."""
    with patch('kubelingo_tools._run_script') as mock:
        yield mock


@pytest.fixture
def mock_questionary():
    """Fixture to mock the questionary library for interactive tests."""
    with patch('kubelingo_tools.questionary') as mock:
        yield mock


def test_main_loop_select_and_run(mock_questionary, mock_run_script):
    """Test that selecting a script runs it and then user chooses to exit."""
    # Simulate user selecting 'generator.py', then saying 'no' to running another script.
    mock_questionary.select.return_value.ask.return_value = "generator.py"
    mock_questionary.confirm.return_value.ask.return_value = False
    
    kubelingo_tools.main()

    mock_questionary.select.assert_called_once()
    mock_run_script.assert_called_once_with("generator.py")
    mock_questionary.confirm.assert_called_once()


def test_main_loop_run_two_and_exit(mock_questionary, mock_run_script):
    """Test that user can run two scripts and then exit."""
    # First loop: select yaml_manager, say yes to continue.
    # Second loop: select bug_ticket, say no to continue.
    mock_questionary.select.return_value.ask.side_effect = ["yaml_manager.py", "bug_ticket.py"]
    mock_questionary.confirm.return_value.ask.side_effect = [True, False]

    kubelingo_tools.main()
    
    assert mock_questionary.select.call_count == 2
    assert mock_run_script.call_count == 2
    mock_run_script.assert_any_call("yaml_manager.py")
    mock_run_script.assert_any_call("bug_ticket.py")
    assert mock_questionary.confirm.call_count == 2


def test_main_loop_exit_immediately(mock_questionary, mock_run_script):
    """Test that selecting 'Exit' stops the script immediately."""
    mock_questionary.select.return_value.ask.return_value = "Exit"
    
    kubelingo_tools.main()

    mock_questionary.select.assert_called_once()
    mock_run_script.assert_not_called()
    mock_questionary.confirm.assert_not_called()
