import sys
from pathlib import Path

import pytest

# Add project root to path to allow absolute imports
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from kubelingo.database import get_all_questions, get_db_connection
from kubelingo.utils.path_utils import find_yaml_files_from_paths, get_all_question_dirs
from scripts.restore_yaml_to_db import restore_yaml_to_db


def test_app_has_questions(tmp_path: Path):
    """
    Tests if the application can load questions from YAML files into the database.

    This is a basic sanity check to ensure there are questions available for users.
    """
    db_path = tmp_path / "test_kubelingo.db"

    # 1. Discover all YAML question files from configured directories
    question_dirs = get_all_question_dirs()
    yaml_files = find_yaml_files_from_paths(question_dirs)

    # Ensure we found some YAML files to test with. If not, this test can't run.
    if not yaml_files:
        pytest.skip("No YAML question files found in default directories. Cannot test question loading.")

    # 2. Restore YAML questions to the temporary database.
    # This function will also initialize the db.
    restore_yaml_to_db(
        yaml_files=yaml_files,
        clear_db=True,
        db_path=str(db_path)
    )

    # 3. Connect to the database and check if questions were loaded
    conn = get_db_connection(db_path=str(db_path))
    try:
        questions = get_all_questions(conn=conn)
    finally:
        conn.close()

    # 4. Assert that at least one question has been loaded
    assert len(questions) > 0, "Database should contain questions after restoring from YAML files."
