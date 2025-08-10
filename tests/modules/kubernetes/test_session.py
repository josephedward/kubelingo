import pytest
from unittest.mock import patch, MagicMock
from kubelingo.modules.kubernetes.session import NewSession

@patch('kubelingo.modules.kubernetes.session.YAMLLoader')
@patch('kubelingo.modules.kubernetes.session.get_all_flagged_questions', return_value=[])
def test_build_interactive_menu_shows_question_counts(mock_get_flagged, mock_yaml_loader):
    """Verify that the main interactive menu displays question counts for each quiz."""
    # Mock the YAMLLoader to discover one quiz file and load questions for it
    mock_loader_instance = mock_yaml_loader.return_value
    mock_loader_instance.discover.return_value = ["/path/to/kubectl_basics.yaml"]
    mock_loader_instance.load_file.return_value = [MagicMock()] * 10  # 10 questions

    # Instantiate the session and call the private method
    logger = MagicMock()
    session = NewSession(logger)
    choices, _ = session._build_interactive_menu_choices()

    # Find the choice for our test quiz
    test_quiz_choice = next((c for c in choices if c['value'] == "/path/to/kubectl_basics.yaml"), None)

    assert test_quiz_choice is not None
    assert test_quiz_choice['name'] == "Kubectl Basics (10 questions)"

    # Verify that the loader's methods were called correctly
    mock_loader_instance.discover.assert_called_once()
    mock_loader_instance.load_file.assert_called_once_with("/path/to/kubectl_basics.yaml")
