import os
import pytest
from kubelingo.database import get_db_connection, run_sql_file
from kubelingo.utils.config import PROJECT_ROOT
from kubelingo.utils.path_utils import find_and_sort_files_by_mtime

SQL_DUMP_DIR = [os.path.join(PROJECT_ROOT, ".kubelingo")]


@pytest.fixture
def db_from_latest_dump():
    """
    Finds the latest .sql dump in .kubelingo, creates an in-memory DB,
    and populates it from the dump.
    """
    sql_files = find_and_sort_files_by_mtime(SQL_DUMP_DIR, extensions=[".sql"])
    if not sql_files:
        pytest.skip("No SQL dump found in .kubelingo directory.")

    latest_dump = sql_files[0]

    conn = get_db_connection(":memory:")
    try:
        run_sql_file(conn, str(latest_dump))
        yield conn
    finally:
        conn.close()


def test_import_from_dump_loads_questions(db_from_latest_dump):
    """
    Checks that the 'questions' table is populated after importing from a dump.
    """
    cursor = db_from_latest_dump.cursor()
    cursor.execute("SELECT count(*) FROM questions")
    count = cursor.fetchone()[0]
    assert count > 0, "No questions were loaded from the SQL dump."


def test_imported_quizzes_have_expected_types(db_from_latest_dump):
    """
    Checks that imported quizzes cover both command-line and manifest-based questions.
    """
    cursor = db_from_latest_dump.cursor()
    cursor.execute("SELECT DISTINCT category FROM questions")
    # Normalize to lowercase for case-insensitive matching
    categories = {row[0].lower() for row in cursor.fetchall()}

    has_command_questions = any("command" in cat for cat in categories)
    has_manifest_questions = any("yaml" in cat or "manifest" in cat for cat in categories)

    assert has_command_questions, "Did not find any command-based quiz categories."
    assert has_manifest_questions, "Did not find any YAML/manifest-based quiz categories."


def test_can_ask_and_answer_question(db_from_latest_dump):
    """
    Ensures that a question can be retrieved and answered.
    """
    cursor = db_from_latest_dump.cursor()
    cursor.execute("SELECT id, question FROM questions LIMIT 1")
    question_record = cursor.fetchone()
    assert question_record is not None, "No question was retrieved from the database."

    question_id, question_content = question_record
    assert question_content, "The retrieved question has no text."

    # Simulate answering the question
    cursor.execute(
        "INSERT INTO answers (question_id, answer_text) VALUES (?, ?)",
        (question_id, "Sample answer"),
    )
    db_from_latest_dump.commit()

    # Verify the answer was recorded
    cursor.execute(
        "SELECT answer_text FROM answers WHERE question_id = ?", (question_id,)
    )
    answer = cursor.fetchone()
    assert answer is not None, "The answer was not recorded in the database."
    assert answer[0] == "Sample answer", "The recorded answer does not match."
