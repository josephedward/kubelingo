import pytest
from unittest.mock import patch, MagicMock
from kubelingo.modules.kubernetes.session import NewSession

@patch('kubelingo.modules.kubernetes.session.YAMLLoader')
@patch('kubelingo.modules.kubernetes.session.get_all_flagged_questions', return_value=[])
def test_build_interactive_menu_shows_question_counts(mock_get_flagged, mock_yaml_loader, monkeypatch):
    """Verify that the main interactive menu displays question counts for each quiz."""
    # Mock the YAMLLoader to return a specific number of questions
    mock_loader_instance = mock_yaml_loader.return_value
    mock_loader_instance.load_file.return_value = [MagicMock()] * 10  # 10 questions

    # Mock the enabled quizzes
    mock_quizzes = {"Kubectl Basics": "kubectl_basics.yaml"}
    monkeypatch.setattr('kubelingo.modules.kubernetes.session.ENABLED_QUIZZES', mock_quizzes)
    
    # Instantiate the session and call the private method
    logger = MagicMock()
    session = NewSession(logger)
    choices, _ = session._build_interactive_menu_choices()

    # Find the choice for our test quiz
    test_quiz_choice = next((c for c in choices if c['value'] == "kubectl_basics.yaml"), None)

    assert test_quiz_choice is not None
    assert test_quiz_choice['name'] == "Kubectl Basics (10 questions)"

    # Verify that the loader was called with the correct path
    mock_loader_instance.load_file.assert_called_once_with("kubectl_basics.yaml")
