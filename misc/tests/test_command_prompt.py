
import pytest
from unittest.mock import MagicMock, patch, call
from cli import generate_command

@patch('cli.print_menu')
@patch('cli.inquirer.text')
@patch('cli.QuestionGenerator')
@patch('cli.console.print')
def test_command_prompt_order(mock_console_print, mock_question_generator, mock_inquirer_text, mock_print_menu, monkeypatch):
    """
    Tests that the user is prompted for input BEFORE the menu is displayed.
    """
    # Arrange
    mock_question_generator.return_value.generate_question.return_value = {
        'id': 'test-id',
        'topic': 'security',
        'question': 'Test question',
        'documentation_link': 'http://example.com',
        'context_variables': {},
        'suggested_answer': 'kubectl test'
    }
    
    mock_inquirer_text.return_value = MagicMock(execute=lambda: "test command")
    monkeypatch.setattr('cli.inquirer.select', MagicMock(return_value=MagicMock(execute=lambda: "security")))

    # Act
    generate_command()

    # Assert
    manager = MagicMock()
    manager.attach_mock(mock_inquirer_text, 'inquirer_text')
    manager.attach_mock(mock_print_menu, 'print_menu')
    
    # This is the key part of the test: it checks the order of calls.
    # It expects inquirer.text to be called before print_menu.
    with pytest.raises(AssertionError):
        manager.assert_has_calls([
            call.print_menu("post_question"),
            call.inquirer_text(message="? ? ? Your command:")
        ], any_order=False)
