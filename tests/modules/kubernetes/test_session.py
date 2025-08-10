import pytest
from unittest.mock import patch, MagicMock
from kubelingo.modules.kubernetes.session import NewSession

@patch('kubelingo.modules.kubernetes.session.YAMLLoader')
@patch('kubelingo.modules.kubernetes.session.get_all_flagged_questions', return_value=[])
def test_build_interactive_menu_shows_question_counts(mock_get_flagged, mock_yaml_loader):
    """Verify that the main interactive menu displays question counts for each quiz."""
    # Mock the YAMLLoader to return 10 questions for each enabled quiz file
    mock_loader_instance = mock_yaml_loader.return_value
    mock_loader_instance.load_file.return_value = [MagicMock()] * 10

    # Instantiate the session and retrieve menu choices
    logger = MagicMock()
    session = NewSession(logger)
    choices, _ = session._build_interactive_menu_choices()

    # Verify that each enabled quiz is listed with the correct question count
    from kubelingo.utils.config import ENABLED_QUIZZES
        
    generated_labels = {c['name'] for c in choices}
        
    assert len(choices) == len(ENABLED_QUIZZES)
    for display_name, quiz_path in ENABLED_QUIZZES.items():
        display_label = f"{display_name} (10 questions)"
        # Find matching entry in choices
        entry = next((c for c in choices if c['name'] == display_label and c['value'] == quiz_path), None)
        assert entry is not None, f"Missing menu entry for '{display_name}'. Expected label: '{display_label}'. Generated labels: {generated_labels}"
        # Ensure loader.load_file was called for this quiz path
        mock_loader_instance.load_file.assert_any_call(quiz_path)
