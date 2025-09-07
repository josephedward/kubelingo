
import pytest
from unittest.mock import patch, MagicMock
from kubelingo import cli

# Mock question data to be returned by generators
MOCK_QUESTION = {
    'question': 'What is a Pod?',
    'suggested_answer': 'The smallest deployable unit in Kubernetes.',
    'source': 'Kubernetes Docs'
}

@pytest.mark.parametrize("menu_choice", [
    "True/False",
    "Vocab",
    "Stored",
    "Multiple Choice",
    "Imperative (Commands)",
    "Declarative (Manifests)",
    "Back"
])
def test_quiz_menu_flow_standardization(menu_choice):
    """
    Verify that all quiz menu options either lead to a quiz session
    or are explicitly handled (e.g., 'Back', or 'Not Implemented').
    This ensures a standard user experience.
    """
    # Mock all external dependencies of the quiz_menu
    with (patch('kubelingo.cli.inquirer.select') as mock_select,
         patch('kubelingo.cli.quiz_session') as mock_quiz_session,
         patch('kubelingo.cli.select_topic', return_value='some_topic') as mock_select_topic,
         patch('kubelingo.cli.inquirer.text') as mock_inquirer_text,
         patch('kubelingo.cli.QuestionGenerator') as mock_qg,
         patch('glob.glob', return_value=['/fake/path/q.yaml']) as mock_glob,
         patch('builtins.open') as mock_open,
         patch('yaml.safe_load', return_value=[MOCK_QUESTION]) as mock_yaml_load):

        # Configure mocks
        mock_select_instance = MagicMock()
        mock_select_instance.execute.return_value = menu_choice
        mock_select.return_value = mock_select_instance
        
        mock_inquirer_text_instance = MagicMock()
        mock_inquirer_text_instance.execute.return_value = '1'
        mock_inquirer_text.return_value = mock_inquirer_text_instance
        
        # Mock the question generator to return a single question
        mock_generator_instance = MagicMock()
        mock_generator_instance.generate_tf_questions.return_value = [MOCK_QUESTION]
        mock_generator_instance.generate_vocab_questions.return_value = [MOCK_QUESTION]
        mock_generator_instance.generate_mcq_questions.return_value = [MOCK_QUESTION]
        mock_qg.return_value = mock_generator_instance

        # Call the function under test
        cli.quiz_menu()

        # Assertions
        if menu_choice in ["True/False", "Vocab", "Stored", "Multiple Choice", "Imperative (Commands)", "Declarative (Manifests)"]:
            # For implemented choices, quiz_session should be called with questions
            mock_quiz_session.assert_called_once()
            # Check that it was called with a non-empty list of questions
            call_args = mock_quiz_session.call_args[0][0]
            assert isinstance(call_args, list)
            assert len(call_args) > 0
            assert call_args[0] == MOCK_QUESTION
        elif menu_choice == "Back":
            # For 'Back', quiz_session should not be called
            mock_quiz_session.assert_not_called()
        else: # Not implemented types
            # For unimplemented choices, quiz_session should not be called
            mock_quiz_session.assert_not_called()
