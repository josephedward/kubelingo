import logging
import unittest
from argparse import Namespace
from io import StringIO
from unittest.mock import patch, MagicMock

from kubelingo.question import Question


# These imports are based on the provided file summaries.
# They might need to be adjusted if the structure is different.
from kubelingo.modules.kubernetes.session import NewSession


class KubernetesQuizFeaturesTest(unittest.TestCase):
    """
    Tests the new Kubernetes quiz features like AI question generation,
    --list-questions flag, and auto-advancing quiz flow.
    """

    def setUp(self):
        """Set up common test data."""
        self.static_questions = [
            Question(id='q1', prompt='Static Prompt 1', response='res1', validation=[]),
            Question(id='q2', prompt='Static Prompt 2', response='res2', validation=[]),
        ]
        self.ai_questions = [
            Question(id='ai-q1', prompt='AI Prompt 1', response='ai-res1', validation=[]),
        ]
        # Suppress logs during tests to keep output clean
        self.logger = logging.getLogger('test_logger')
        self.logger.addHandler(logging.NullHandler())

    def _get_mock_args(self, **kwargs):
        """Helper to create a mock args namespace."""
        defaults = {
            'file': 'dummy.yaml',
            'num_questions': 2,
            'category': None,
            'review': False,
            'review_only': False,
            'all_flagged': False,
            'clear_all_review': False,
            'list_questions': False,
            'ai_only': False,
            'docker': False,
            'help': False,
            'vim_output': None,
        }
        defaults.update(kwargs)
        return Namespace(**defaults)

    @patch('kubelingo.modules.kubernetes.session.load_questions')
    @patch('kubelingo.modules.question_generator.AIQuestionGenerator.generate_questions')
    @patch('sys.stdout', new_callable=StringIO)
    def test_list_questions_flag_prints_all_questions_and_exits(
        self, mock_stdout, mock_generate_questions, mock_load_questions
    ):
        # Arrange
        mock_load_questions.return_value = self.static_questions
        mock_generate_questions.return_value = self.ai_questions
        args = self._get_mock_args(list_questions=True, num_questions=3)
        session = NewSession(self.logger)

        # Act
        session.run_exercises(args)

        # Assert
        output = mock_stdout.getvalue()
        # It should print the full list of final questions
        self.assertIn("1. Static Prompt 1", output)
        self.assertIn("2. Static Prompt 2", output)
        self.assertIn("3. AI Prompt 1", output)
        
        # And it should not start the interactive quiz
        self.assertNotIn("Starting Kubelingo Quiz", output)

    @patch('kubelingo.modules.kubernetes.session.load_questions')
    @patch('kubelingo.modules.question_generator.AIQuestionGenerator')
    @patch('questionary.prompt')
    @patch('sys.stdout', new_callable=StringIO)
    def test_ai_generation_failure_shows_warning_and_continues(
        self, mock_stdout, mock_prompt, MockAIGenerator, mock_load_questions
    ):
        # Arrange: Mimic the user-provided log where AI generation fails
        mock_load_questions.return_value = self.static_questions
        
        # AI generator is asked for 2 questions but returns 0
        mock_ai_instance = MockAIGenerator.return_value
        mock_ai_instance.generate_questions.return_value = []

        args = self._get_mock_args(num_questions=4) # 2 static + 2 AI
        session = NewSession(self.logger)
        
        # Exit quiz immediately after it starts
        mock_prompt.return_value = {'action': 'Exit App'}

        # Act
        session.run_exercises(args)

        # Assert
        output = mock_stdout.getvalue()
        self.assertIn("Warning: Could not generate 2 unique AI questions. Proceeding with 0 generated.", output)
        self.assertIn("File: dummy.yaml, Questions: 2", output)
        mock_prompt.assert_called_once() # Verify interactive quiz started

    @patch('kubelingo.modules.kubernetes.session.load_questions')
    @patch('kubelingo.modules.kubernetes.session.check_answer')
    @patch('questionary.prompt')
    @patch('sys.stdout', new_callable=StringIO)
    def test_auto_advances_after_checking_answer(
        self, mock_stdout, mock_prompt, mock_check_answer, mock_load_questions
    ):
        # Arrange
        mock_load_questions.return_value = self.static_questions
        mock_check_answer.return_value = (True, []) # Assume correct answer
        
        # Simulate user actions:
        # 1. On Q1, choose 'Check Answer'. The runner should auto-advance.
        # 2. On Q2, choose 'Exit Quiz' to end the test.
        mock_prompt.side_effect = [
            {'action': 'Check Answer'},
            {'action': 'Exit Quiz'},
        ]

        args = self._get_mock_args(num_questions=2)
        session = NewSession(self.logger)

        # Act
        session.run_exercises(args)

        # Assert
        # It should print Q1, then after "Check Answer", it should print Q2.
        output = mock_stdout.getvalue()
        self.assertIn("Question 1/2", output)
        self.assertIn("Question 2/2", output)
        
        # Verify that check_answer was called for the first question.
        mock_check_answer.assert_called_once()
        
        # There should be two calls to prompt: one for Q1 menu, one for Q2 menu.
        # If auto-advance failed, there would be more calls.
        self.assertEqual(mock_prompt.call_count, 2)
