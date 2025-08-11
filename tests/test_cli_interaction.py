import pytest
from pathlib import Path
from unittest.mock import patch

from kubelingo.database import init_db, add_question, get_db_connection
from kubelingo.cli import main

# A sample question for testing
TEST_QUESTION = {
    "id": "test-q1",
    "prompt": "How do you list all pods in all namespaces?",
    "response": "kubectl get pods --all-namespaces",
    "category": "Test CLI Quiz",
    "schema_category": "command",
    "source_file": "test_data.yaml",
}

@pytest.fixture
def setup_test_db(tmp_path: Path, monkeypatch):
    """
    Sets up a temporary database with a single question for testing.
    """
    db_path = tmp_path / "test_kubelingo.db"

    # Patch get_live_db_path to use the temporary database for the CLI session
    monkeypatch.setattr("kubelingo.utils.config.get_live_db_path", lambda: str(db_path))
    # Also patch in database module scope in case of direct import
    monkeypatch.setattr("kubelingo.database.get_live_db_path", lambda: str(db_path), raising=False)

    init_db(clear=True, db_path=str(db_path))

    conn = get_db_connection(db_path=str(db_path))
    try:
        add_question(conn=conn, **TEST_QUESTION)
    finally:
        conn.close()

    return str(db_path)

@patch('builtins.input')
@patch('kubelingo.cli.inquirer')
def test_cli_full_interaction(mock_inquirer, mock_input, setup_test_db, capsys):
    """
    Tests a full user interaction: selecting a quiz, answering a question, and seeing the result.

    This test makes some assumptions about the CLI's implementation:
    1. It uses `inquirer` for menus, and the prompt's name is 'menu_choice'.
    2. After selecting a quiz, it uses `builtins.input()` to get the user's answer.
    3. The main CLI function has a main loop and is exited via a menu choice that raises SystemExit.
    """
    # Mock sequence:
    # 1. User selects the quiz from the main menu.
    # 2. User provides the correct answer to the question.
    # 3. User chooses to exit the application from the main menu.
    mock_inquirer.prompt.side_effect = [
        {'menu_choice': 'Test CLI Quiz'},  # Select the quiz
        {'menu_choice': 'Exit App'},       # Exit after quiz
    ]
    mock_input.return_value = TEST_QUESTION["response"]

    # Run the CLI main function. We expect it to be inside a loop
    # that we exit, causing a SystemExit.
    with pytest.raises(SystemExit):
        main()

    # Verify the output
    captured = capsys.readouterr()

    # Check that the question prompt was displayed
    assert TEST_QUESTION["prompt"] in captured.out

    # Check that the "Correct!" message was displayed
    assert "Correct!" in captured.out

    # Check that our mocks were used
    assert mock_inquirer.prompt.called
    assert mock_input.called
