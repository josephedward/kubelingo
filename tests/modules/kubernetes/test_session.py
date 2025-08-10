import pytest
from unittest.mock import patch, MagicMock
from kubelingo.modules.kubernetes.session import NewSession

@patch('kubelingo.modules.kubernetes.session.DBLoader')
@patch('kubelingo.modules.kubernetes.session.get_all_flagged_questions', return_value=[])
def test_build_interactive_menu_shows_question_counts(mock_get_flagged, mock_db_loader):
    """Verify that the interactive menu displays question counts for configured quizzes."""
    # Mock DBLoader to return quiz sources and 10 questions each
    mock_loader = mock_db_loader.return_value
    # Simulate discover returning all configured paths
    from kubelingo.utils.config import ENABLED_QUIZZES
    mock_loader.discover.return_value = list(ENABLED_QUIZZES.values())
    mock_loader.load_file.return_value = [MagicMock()] * 10

    # Instantiate the session and get menu choices
    logger = MagicMock()
    session = NewSession(logger)
    choices, _ = session._build_interactive_menu_choices()

    # Filter only quiz entries (skip separators and other menu items)
    from kubelingo.utils.config import ENABLED_QUIZZES
    expected_paths = set(ENABLED_QUIZZES.values())
    quiz_choices = [c for c in choices if isinstance(c, dict) and c.get('value') in expected_paths]
    assert len(quiz_choices) == len(expected_paths)

    # Verify each configured quiz appears with the correct label and count
    for display_name, quiz_path in ENABLED_QUIZZES.items():
        expected_label = f"{display_name} (10 questions)"
        entry = next(
            (c for c in quiz_choices if c.get('name') == expected_label and c.get('value') == quiz_path),
            None
        )
        assert entry is not None, (
            f"Missing quiz entry: {{'name': {expected_label!r}, 'value': {quiz_path!r}}}"
        )
        mock_loader.load_file.assert_any_call(quiz_path)
