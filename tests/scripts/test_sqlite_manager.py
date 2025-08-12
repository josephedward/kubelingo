import datetime
import os
import shutil
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# Add project root to path to allow imports from kubelingo
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts import sqlite_manager


@pytest.fixture
def setup_test_dbs(tmp_path):
    """Set up a temporary directory with mock databases and config for tests."""
    # Create project structure
    (tmp_path / ".kubelingo" / "backups").mkdir(parents=True, exist_ok=True)
    (tmp_path / "archive").mkdir(parents=True, exist_ok=True)
    (tmp_path / "questions_yaml").mkdir(parents=True, exist_ok=True)
    (tmp_path / "backups").mkdir(parents=True, exist_ok=True)

    # Live DB
    live_db_path = tmp_path / ".kubelingo" / "database.db"
    with sqlite3.connect(live_db_path) as conn:
        conn.execute("CREATE TABLE live_table (id INT)")
        conn.execute("INSERT INTO live_table VALUES (1)")

    # Backup DB 1 (more tables/data)
    backup_db_1_path = tmp_path / ".kubelingo" / "backups" / "backup1.db"
    with sqlite3.connect(backup_db_1_path) as conn:
        conn.execute("CREATE TABLE table1 (id INT)")
        conn.execute("CREATE TABLE table2 (name TEXT)")
        conn.execute("INSERT INTO table1 VALUES (10), (20)")
        conn.execute("INSERT INTO table2 VALUES ('alpha')")

    # Backup DB 2 (schema mismatch, different data)
    backup_db_2_path = tmp_path / ".kubelingo" / "backups" / "backup2.db"
    with sqlite3.connect(backup_db_2_path) as conn:
        conn.execute("CREATE TABLE table1 (id INT, description TEXT)")
        conn.execute("INSERT INTO table1 VALUES (10, 'ten')")
    # Make this one older
    mtime = datetime.datetime.now().timestamp() - 3600
    os.utime(backup_db_2_path, (mtime, mtime))

    # DB in archive
    archive_db_path = tmp_path / "archive" / "archived.db"
    with sqlite3.connect(archive_db_path) as conn:
        conn.execute("CREATE TABLE archived_table (data TEXT)")

    # YAML file for import test
    yaml_path = tmp_path / "questions_yaml" / "questions.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(
            {
                "questions": [
                    {
                        "id": "q1",
                        "prompt": "What is a Pod?",
                        "category": "Concepts",
                        "source_file": "some/file.yaml",
                    }
                ]
            },
            f,
        )

    # Patch necessary globals and functions in the sqlite_manager script
    with patch("scripts.sqlite_manager.project_root", tmp_path), \
         patch("scripts.sqlite_manager.get_live_db_path", return_value=str(live_db_path)), \
         patch("scripts.sqlite_manager.SQLITE_BACKUP_DIRS", [str(tmp_path / ".kubelingo" / "backups")]), \
         patch("scripts.sqlite_manager.YAML_BACKUP_DIRS", [str(tmp_path / "questions_yaml")]), \
         patch("scripts.sqlite_manager.ENABLED_QUIZZES", {"Concepts": "some/file.yaml"}):
        yield tmp_path


def test_index(setup_test_dbs, capsys):
    """Test the 'index' command."""
    args = MagicMock(dirs=None)
    sqlite_manager.do_index(args)

    index_file = setup_test_dbs / "backups" / "sqlite_index.yaml"
    assert index_file.exists()
    with open(index_file) as f:
        index_data = yaml.safe_load(f)

    assert "files" in index_data
    assert len(index_data["files"]) == 2  # backup1.db, backup2.db
    paths = {f["path"] for f in index_data["files"]}
    assert ".kubelingo/backups/backup1.db" in paths
    assert ".kubelingo/backups/backup2.db" in paths

    captured = capsys.readouterr()
    assert "Successfully created SQLite index" in captured.out


def test_schema(setup_test_dbs, capsys):
    """Test the 'schema' command."""
    db_path = setup_test_dbs / ".kubelingo" / "backups" / "backup1.db"
    args = MagicMock(db_path=str(db_path), output=None)
    sqlite_manager.do_schema(args)

    captured = capsys.readouterr()
    assert "CREATE TABLE table1 (id INT);" in captured.out
    assert "CREATE TABLE table2 (name TEXT);" in captured.out


def test_list(setup_test_dbs, capsys):
    """Test the 'list' command."""
    args = MagicMock(directories=None, path_only=False)
    sqlite_manager.do_list(args)

    captured = capsys.readouterr()
    # backup1.db is newer and should be listed first
    assert captured.out.find("backup1.db") < captured.out.find("backup2.db")
    assert "Found 2 backup file(s)" in captured.out


def test_unarchive(setup_test_dbs):
    """Test the 'unarchive' command."""
    archive_file = setup_test_dbs / "archive" / "archived.db"
    dest_file = setup_test_dbs / ".kubelingo" / "archived.db"
    assert archive_file.exists()
    assert not dest_file.exists()

    args = MagicMock()
    sqlite_manager.do_unarchive(args)

    assert not archive_file.exists()
    assert dest_file.exists()


def test_restore(setup_test_dbs):
    """Test the 'restore' command."""
    live_db_path = setup_test_dbs / ".kubelingo" / "database.db"
    backup_path = setup_test_dbs / ".kubelingo" / "backups" / "backup1.db"

    # Check live DB content before restore
    with sqlite3.connect(live_db_path) as conn:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("SELECT * FROM table1")

    args = MagicMock(
        backup_db=str(backup_path),
        yes=True,
        no_pre_backup=True,
    )
    sqlite_manager.do_restore(args)

    # Check live DB content after restore
    with sqlite3.connect(live_db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM table1")
        assert cur.fetchone()[0] == 2
        cur.execute("SELECT COUNT(*) FROM table2")
        assert cur.fetchone()[0] == 1


def test_create_from_yaml(setup_test_dbs):
    """Test the 'create-from-yaml' command."""
    yaml_file = setup_test_dbs / "questions_yaml" / "questions.yaml"
    new_db_path = setup_test_dbs / "new_from_yaml.db"

    args = MagicMock(
        yaml_files=[str(yaml_file)],
        db_path=str(new_db_path),
        clear=True
    )
    sqlite_manager.do_create_from_yaml(args)

    assert new_db_path.exists()
    with sqlite3.connect(new_db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, prompt, category, subject FROM questions")
        row = cur.fetchone()
        assert row[0] == "q1"
        assert row[1] == "What is a Pod?"
        assert row[2] == "basic"
        assert row[3] == "Concepts"


def test_diff(setup_test_dbs, capsys):
    """Test the 'diff' command."""
    db_a = setup_test_dbs / ".kubelingo" / "backups" / "backup1.db"
    db_b = setup_test_dbs / ".kubelingo" / "backups" / "backup2.db"
    args = MagicMock(
        db_a=str(db_a),
        db_b=str(db_b),
        no_schema=False,
        no_counts=False
    )
    sqlite_manager.do_diff(args)

    captured = capsys.readouterr()

    # Schema diff
    assert "--- Schema Differences ---" in captured.out
    assert "CREATE TABLE table2 (name TEXT);" in captured.out
    assert "CREATE TABLE table1 (id INT, description TEXT);" in captured.out

    # Row count diff
    assert "--- Row Count Differences ---" in captured.out
    assert "table1: 1 -> 2 (Change:  1)" in captured.out
    assert "table2: N/A -> 1" in captured.out


def test_update_schema_category(setup_test_dbs, capsys):
    """Test the 'update-schema-category' command."""
    # Use the live db from the fixture
    live_db_path = setup_test_dbs / ".kubelingo" / "database.db"

    # Add a questions table and some data
    with sqlite3.connect(live_db_path) as conn:
        conn.execute("""
            CREATE TABLE questions (
                id TEXT PRIMARY KEY,
                source_file TEXT,
                schema_category TEXT
            )
        """)
        test_data = [
            ('q1', 'some/path/vim_practice.yaml', None),
            ('q2', 'another/path/kubectl_operations_quiz.yaml', 'Old Category'),
            ('q3', 'unrelated.yaml', 'Some Category'),
            ('q4', 'long/path/yaml_quiz.yaml', None),
        ]
        conn.executemany(
            "INSERT INTO questions (id, source_file, schema_category) VALUES (?, ?, ?)",
            test_data
        )

    # Use a mock args object for the command
    args = MagicMock(db_path=str(live_db_path))
    sqlite_manager.do_update_schema_category(args)

    # Verify the results in the database
    with sqlite3.connect(live_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, schema_category FROM questions ORDER BY id")
        results = dict(cursor.fetchall())

    assert results['q1'] == 'Basic/Open-Ended'
    assert results['q2'] == 'Command-Based/Syntax'
    assert results['q3'] == 'Some Category'  # Should be unchanged
    assert results['q4'] == 'Manifests'

    captured = capsys.readouterr()
    assert "rows updated for 'vim_practice.yaml' -> 'Basic/Open-Ended'" in captured.out
    assert "rows updated for 'kubectl_operations_quiz.yaml' -> 'Command-Based/Syntax'" in captured.out
    assert "rows updated for 'yaml_quiz.yaml' -> 'Manifests'" in captured.out
