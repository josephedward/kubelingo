import pytest
from unittest.mock import MagicMock, patch
from cli import generate_trivia

@patch('cli.ai_chat')
@patch('cli.console.print')
@patch('cli.inquirer.select')
@patch('cli.inquirer.text')
@patch('cli.print_question_menu')
@patch('cli.print_post_answer_menu')
def test_generate_trivia_gemini_e2e(
    mock_print_post_answer_menu,
    mock_print_question_menu,
    mock_inquirer_text,
    mock_inquirer_select,
    mock_console_print,
    mock_ai_chat,
    monkeypatch
):
    """
    Tests the end-to-end flow of generate_trivia with a successful Gemini AI response.
    """
    # Arrange
    # Mock AI response for a trivia question
    mock_ai_chat.return_value = """
    {
        "question": "What is the purpose of an Ingress resource in Kubernetes?",
        "type": "vocab",
        "options": [],
        "answer": "An API object that manages external access to the services in a cluster, typically HTTP."
    }
    """

    # Mock inquirer selections
    mock_inquirer_select.side_effect = [
        MagicMock(execute=lambda: "ingress"),  # Select topic
    ]
    mock_inquirer_text.side_effect = [
        MagicMock(execute=lambda: "An API object that manages external access to the services in a cluster, typically HTTP."), # User provides correct answer
    ]

    # Act
    generate_trivia()

    # Assert
    # Verify question is printed
    mock_console_print.assert_any_call("[bold cyan]What is the purpose of an Ingress resource in Kubernetes?[/bold cyan]")

    # Verify correct answer is printed
    mock_console_print.assert_any_call("[bold green]Correct![/bold green]")

    # Verify menus are printed
    mock_print_question_menu.assert_called_once()
    mock_print_post_answer_menu.assert_called_once()

    # Verify ai_chat was called with correct system and user prompts
    mock_ai_chat.assert_called_once_with(
        "You are a trivia question generator. Generate exactly one trivia question on the given topic. You may choose True/False, multiple-choice with 4 options, or vocabulary. Provide output as a JSON object only, with keys: question (string), type (\"tf\", \"mcq\", \"vocab\"), options (array of 4 strings, only for mcq), and answer (string: 'true'/'false' for tf, full text for vocab, exact option for mcq).",
        "Topic: ingress"
    )
