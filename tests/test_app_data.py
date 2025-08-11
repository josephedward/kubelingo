import pytest
from pathlib import Path

from kubelingo.database import get_all_questions, get_db_connection
from kubelingo.utils.path_utils import get_live_db_path
from kubelingo.utils.config import ENABLED_QUIZZES


def test_live_database_has_questions():
    """
    Tests that the live database is populated with questions.
    This is a basic check to ensure the app has data to work with.
    An empty database will result in the UI showing 0 questions.
    """
    db_path = get_live_db_path()
    assert Path(db_path).exists(), f"Live database not found at {db_path}"

    conn = get_db_connection(db_path=db_path)
    try:
        all_questions = get_all_questions(conn=conn)
        assert len(all_questions) > 0, "The live database contains no questions."
    finally:
        conn.close()


def test_questions_are_assigned_to_enabled_quizzes():
    """
    Tests that there are questions in the database that are assigned to categories
    that are configured as enabled quizzes in the application.

    If this test fails, it might mean question 'category' fields don't
    match the keys in the ENABLED_QUIZZES configuration.
    """
    db_path = get_live_db_path()
    assert Path(db_path).exists(), f"Live database not found at {db_path}"

    conn = get_db_connection(db_path=db_path)
    try:
        all_questions = get_all_questions(conn=conn)
        if not all_questions:
            pytest.skip("Live database is empty, cannot check for quiz assignment.")

        enabled_quiz_categories = set(ENABLED_QUIZZES.keys())

        questions_in_enabled_quizzes = [
            q for q in all_questions if q.get('category') in enabled_quiz_categories
        ]

        assert len(questions_in_enabled_quizzes) > 0, (
            "No questions found for any of the enabled quiz categories. "
            "Check that question categories match the quiz configuration in 'kubelingo/utils/config.py'."
        )

    finally:
        conn.close()
