from unittest.mock import patch

import pytest
from scripts import kubelingo_tools


@pytest.fixture
def mock_questionary():
    """Fixture to mock the questionary library for interactive tests."""
    with patch('scripts.kubelingo_tools.questionary') as mock:
        yield mock


@patch('scripts.kubelingo_tools._generate_questions')
def test_main_loop_select_generate_and_exit(mock_generate_questions, mock_questionary):
    """Test that selecting 'Generate Questions' runs it and then user chooses to exit."""
    # Simulate user selecting 'Generate Questions', then saying 'no' to returning to menu.
    mock_questionary.select.return_value.ask.return_value = "Generate Questions"
    mock_questionary.confirm.return_value.ask.return_value = False
    
    kubelingo_tools.main()

    mock_questionary.select.assert_called_once()
    mock_generate_questions.assert_called_once()
    mock_questionary.confirm.assert_called_once()


@patch('scripts.kubelingo_tools._add_questions')
@patch('scripts.kubelingo_tools._generate_questions')
def test_main_loop_run_two_and_exit(mock_generate, mock_add, mock_questionary):
    """Test that user can run two tasks and then exit."""
    # First loop: select 'Generate Questions', say yes to continue.
    # Second loop: select 'Add Questions', say no to continue.
    mock_questionary.select.return_value.ask.side_effect = ["Generate Questions", "Add Questions"]
    mock_questionary.confirm.return_value.ask.side_effect = [True, False]

    kubelingo_tools.main()
    
    assert mock_questionary.select.call_count == 2
    mock_generate.assert_called_once()
    mock_add.assert_called_once()
    assert mock_questionary.confirm.call_count == 2


def test_main_loop_exit_immediately(mock_questionary):
    """Test that selecting 'Exit' stops the script immediately."""
    mock_questionary.select.return_value.ask.return_value = "Exit"
    
    # We need to patch one of the task functions to check it wasn't called.
    with patch('scripts.kubelingo_tools._generate_questions') as mock_task:
        kubelingo_tools.main()

        mock_questionary.select.assert_called_once()
        mock_task.assert_not_called()
        mock_questionary.confirm.assert_not_called()

# Test one of the sub-functions to ensure handlers are called.
@patch('scripts.kubelingo_tools.handle_from_pdf')
def test_generate_questions_from_pdf(mock_handler, mock_questionary):
    """Test the 'Generate Questions' -> 'From PDF' flow calls the correct handler."""
    # Main menu choice -> Sub-menu choice
    mock_questionary.select.return_value.ask.return_value = "From PDF"
    # User inputs for the handler
    mock_questionary.text.side_effect = ["test.pdf", "output.yaml", "5"]
    
    kubelingo_tools._generate_questions()

    mock_handler.assert_called_once()
    # Check that the mock args passed to the handler are correct
    args = mock_handler.call_args.args[0]
    assert args.pdf_path == "test.pdf"
    assert args.output_file == "output.yaml"
    assert args.num_questions_per_chunk == 5
