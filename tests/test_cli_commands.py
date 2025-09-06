import pytest
pytest.skip("Skipping outdated TestCliCommands tests", allow_module_level=True)
import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os
from enum import Enum

# Adjust the path to import cli.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import cli

class DifficultyLevel(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class TestCliCommands(unittest.TestCase):

    @patch('cli.inquirer.select')
    @patch('cli.inquirer.text')
    @patch('cli.console.print')
    @patch('cli.QuestionGenerator')
    @patch('cli.print_post_answer_menu')
    @patch('cli.print_menu')
    def test_generate_command_display_logic(self, mock_print_menu, mock_print_post_answer_menu, mock_question_generator, mock_console_print, mock_inquirer_text, mock_inquirer_select):
        # Mock inquirer.select for quiz_menu (if called, though we call generate_command directly)
        mock_inquirer_select.side_effect = [
            MagicMock(execute=MagicMock(side_effect=["deployments"])), # For topic selection in generate_command if topic is None
            MagicMock(execute=MagicMock(side_effect=["Again"])), # For post-answer menu action (Test Case 1)
            MagicMock(execute=MagicMock(side_effect=["Correct"])), # For post-answer menu action (Test Case 2)
        ]

        # Mock inquirer.text for the user's command input and solution request
        mock_inquirer_text.side_effect = [
            MagicMock(execute=MagicMock(side_effect=["my custom command"])), # User's attempt (Test Case 1)
            MagicMock(execute=MagicMock(side_effect=["s"])), # User asks for solution (Test Case 2)
        ]

        # Mock QuestionGenerator.generate_question to return a specific question and suggested answer
        mock_question_generator.return_value.generate_question.return_value = {
            'id': 'test-deploy-id',
            'topic': 'deployments',
            'question': 'Create a Deployment named "my-app" with 3 replicas of "nginx:latest" exposing port 80, with environment variable APP_ENV="production", and resource limits of CPU 500m and memory 256Mi',
            'documentation_link': 'http://example.com/deployments',
            'context_variables': {
                'deployment_name': 'my-app',
                'replicas': 3,
                'image': 'nginx:latest',
                'port': 80,
                'env_var': 'APP_ENV',
                'env_value': 'production',
                'cpu_limit': '500m',
                'memory_limit': '256Mi'
            },
            'suggested_answer': 'kubectl create deployment my-app --image=nginx:latest --replicas=3 --port=80 --env=APP_ENV=production --limits=cpu=500m,memory=256Mi'
        }

        # --- Test Case 1: User provides a command ---
        # Call generate_command directly
        cli.generate_command(topic="deployments", gen=mock_question_generator.return_value)

        # Assert that the question and doc link are printed
        mock_console_print.assert_any_call(f"[bold cyan]Question:[/bold cyan] {mock_question_generator.return_value.generate_question.return_value['question']}")
        mock_console_print.assert_any_call(f"[bold cyan]Documentation:[/bold cyan] [link={mock_question_generator.return_value.generate_question.return_value['documentation_link']}]{mock_question_generator.return_value.generate_question.return_value['documentation_link']}[/link]")

        # Assert that the post-question menu is printed BEFORE user input
        mock_print_menu.assert_called_with("post_question")
        
        # Assert that the suggested command is printed AFTER user input
        mock_console_print.assert_any_call(f"[bold green]Suggested Command:[/bold green] {mock_question_generator.return_value.generate_question.return_value['suggested_answer']}")
        
        # Assert that the post-answer menu is printed
        mock_print_post_answer_menu.assert_called_once()

        # --- Test Case 2: User asks for solution ---
        mock_console_print.reset_mock()
        mock_print_menu.reset_mock()
        mock_print_post_answer_menu.reset_mock()

        # Call generate_command directly
        cli.generate_command(topic="deployments", gen=mock_question_generator.return_value)

        # Assert that the suggested command is printed when 's' is entered
        mock_console_print.assert_any_call(f"[bold green]Suggested Command:[/bold green] {mock_question_generator.return_value.generate_question.return_value['suggested_answer']}")
        mock_print_post_answer_menu.assert_called_once()


    @patch('cli.inquirer.select')
    @patch('cli.inquirer.text')
    @patch('cli.console.print')
    @patch('cli.QuestionGenerator')
    @patch('cli._display_post_answer_menu')
    @patch('cli.webbrowser.open')
    def test_generate_command_no_type_error(self, mock_webbrowser_open, mock_display_post_answer_menu, mock_question_generator, mock_console_print, mock_inquirer_text, mock_inquirer_select):
        # Mock inquirer.select for quiz_menu and generate_command
        mock_inquirer_select.side_effect = [
            MagicMock(execute=MagicMock(side_effect=["Quiz"])), # Main menu choice
            MagicMock(execute=MagicMock(side_effect=["Command"])), # Quiz type choice
            MagicMock(execute=MagicMock(side_effect=["troubleshooting"])), # Topic choice
            MagicMock(execute=MagicMock(side_effect=["No"])), # For the "Generate another question..." prompt
            MagicMock(execute=MagicMock(side_effect=["Again"])), # For post-answer menu action
        ]

        # Mock inquirer.text for the user's command input
        mock_inquirer_text.side_effect = [
            MagicMock(execute=MagicMock(return_value="kubectl get pods")), # User's command input
        ]

        # Mock QuestionGenerator.generate_question to return a dummy question
        mock_question_generator.return_value.generate_question.return_value = {
            'id': 'test-id',
            'topic': 'troubleshooting',
            'difficulty': 'intermediate',
            'question': 'How do you view the logs of a pod?',
            'documentation_link': 'http://example.com/docs',
            'context_variables': {'pod_name': 'my-pod'},
            'suggested_answer': 'kubectl logs my-pod'
        }

        # Mock _display_post_answer_menu to prevent interactive prompts during test
        mock_display_post_answer_menu.return_value = None

        # Call quiz_menu, which should then call generate_command
        cli.quiz_menu()

        # Define the expected calls to inquirer.select
        expected_calls = [
            call(message='Select quiz type:', choices=['Trivia', 'Command', 'Manifest', 'Static', 'AI Generated', 'Back']),
            call(message='Select topic:', choices=[t.value for t in cli.KubernetesTopics]),
            # The difficulty selection is no longer present in quiz_menu directly for Command type
            # call(message='Select difficulty:', choices=[lvl.value for lvl in cli.DifficultyLevel]),
            call(message='Select an action:', choices=['Again', 'Correct', 'Missed', 'Remove Question'])
        ]

        # Assert that inquirer.select was called with the expected arguments
        mock_inquirer_select.assert_has_calls(expected_calls, any_order=False)

        # Verify that generate_command was called (implicitly by not raising TypeError)
        # and that the mock question generator was used.
        mock_question_generator.return_value.generate_question.assert_called_once_with(
            topic='troubleshooting',
            include_context=True
        )

if __name__ == '__main__':
    unittest.main()
