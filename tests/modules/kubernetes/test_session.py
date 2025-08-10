import pytest
from unittest.mock import patch, MagicMock
from kubelingo.modules.kubernetes.session import NewSession

@patch('kubelingo.modules.kubernetes.session.YAMLLoader')
@patch('kubelingo.modules.kubernetes.session.get_all_flagged_questions', return_value=[])
def test_build_interactive_menu_shows_question_counts(mock_get_flagged, mock_yaml_loader):
    """Verify that the main interactive menu displays question counts for each quiz."""
    # Mock the YAMLLoader to load 10 questions for each enabled quiz
    mock_loader_instance = mock_yaml_loader.return_value
    mock_loader_instance.load_file.return_value = [MagicMock()] * 10

    # Instantiate the session and call the private method
    logger = MagicMock()
    session = NewSession(logger)
    choices, _ = session._build_interactive_menu_choices()

    # Verify that all enabled quizzes are listed with the correct question count
    from kubelingo.utils.config import ENABLED_QUIZZES
    assert len(choices) == len(ENABLED_QUIZZES)
    for display_name, quiz_path in ENABLED_QUIZZES.items():
        expected_display = f"{display_name} ({len(mock_loader_instance.load_file.return_value)} questions)"
        choice = next((c for c in choices if c['name'] == expected_display), None)
        assert choice is not None, f"Missing menu entry '{expected_display}'"
        assert choice['value'] == quiz_path
        mock_loader_instance.load_file.assert_any_call(quiz_path)
