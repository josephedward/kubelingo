import pytest
from unittest.mock import patch, MagicMock
from kubelingo.modules.kubernetes.session import NewSession

@patch('kubelingo.modules.kubernetes.session.DBLoader')
@patch('kubelingo.modules.kubernetes.session.get_all_flagged_questions', return_value=[])
def test_build_interactive_menu_shows_question_counts(mock_get_flagged, mock_db_loader):
    """Verify that the interactive menu displays question counts for configured quizzes."""
    # Mock DBLoader to return 10 questions for each configured quiz path
    mock_loader = mock_db_loader.return_value
    mock_loader.load_file.return_value = [MagicMock()] * 10

    # Instantiate session and get menu choices
    logger = MagicMock()
    session = NewSession(logger)
    choices, _ = session._build_interactive_menu_choices()

    # Collect expected quiz mappings from config
    from kubelingo.utils.config import BASIC_QUIZZES, COMMAND_QUIZZES, MANIFEST_QUIZZES
    expected_mappings = {**BASIC_QUIZZES, **COMMAND_QUIZZES, **MANIFEST_QUIZZES}
    expected_paths = set(expected_mappings.values())
    # Extract quiz choices from menu
    quiz_choices = [c for c in choices if isinstance(c, dict) and c.get('value') in expected_paths]
    assert len(quiz_choices) == len(expected_paths)

    # Verify each mapping appears correctly
    for display_name, quiz_path in expected_mappings.items():
        expected_label = f"{display_name} (10 questions)"
        entry = next((c for c in quiz_choices
                      if c.get('name') == expected_label and c.get('value') == quiz_path), None)
        assert entry is not None, (
            f"Missing quiz entry: {{'name': {expected_label!r}, 'value': {quiz_path!r}}}"
        )
        mock_loader.load_file.assert_any_call(quiz_path)
