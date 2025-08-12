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
