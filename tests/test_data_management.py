import os
import sys
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch

# Add project root to path to allow importing from kubelingo
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from kubelingo.database import add_question, get_all_questions, init_db, get_db_connection
from scripts.export_db_to_yaml import export_db_to_yaml
from scripts.restore_yaml_to_db import restore_yaml_to_db
from scripts.locate_yaml_backups import main as locate_yaml_backups_main


@pytest.fixture
def temp_db_path(tmp_path):
    """Fixture to create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    return str(db_path)


@pytest.fixture
def populated_db(temp_db_path):
    """Fixture to create and populate a temporary database."""
    init_db(clear=True, db_path=temp_db_path)
    conn = get_db_connection(db_path=temp_db_path)

    questions = [
        {"id": "q1", "prompt": "Prompt 1", "source_file": "test.yaml", "response": "resp1", "category": "cat1"},
        {"id": "q2", "prompt": "Prompt 2", "source_file": "test.yaml", "response": "resp2", "category": "cat2", "validation_steps": [{"cmd": "ls"}]},
    ]

    try:
        for q in questions:
            add_question(conn=conn, **q)
        conn.commit()
    finally:
        conn.close()

    return temp_db_path, questions


def test_export_restore_roundtrip(populated_db, tmp_path):
    """
    Tests that exporting questions to YAML and restoring them results in the same data.
    """
    db_path, original_questions = populated_db
    yaml_path = tmp_path / "backup.yaml"

    # 1. Export DB to YAML
    exported_count = export_db_to_yaml(str(yaml_path), db_path=db_path)
    assert exported_count == len(original_questions)
    assert yaml_path.exists()

    with open(yaml_path, "r") as f:
        yaml_data = yaml.safe_load(f)
    assert len(yaml_data) == len(original_questions)

    # 2. Restore from YAML to a fresh DB
    restore_yaml_to_db(str(yaml_path), clear_db=True, db_path=db_path)

    # 3. Verify data in restored DB
    restored_questions = get_all_questions(db_path=db_path)

    # Sort both by id to ensure order doesn't affect comparison
    original_questions.sort(key=lambda q: q['id'])
    restored_questions.sort(key=lambda q: q['id'])

    assert len(restored_questions) == len(original_questions)
    # The restored questions will have more null fields that were defaulted in the DB
    # We check that the original data is a "subset" of the restored data.
    for i, original_q in enumerate(original_questions):
        restored_q = restored_questions[i]
        for key, value in original_q.items():
            assert restored_q[key] == value


def test_locate_yaml_backups(tmp_path, capsys):
    """
    Tests the locate_yaml_backups.py script.
    """
    # 1. Create dummy backup files
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "backup1.yaml").touch()
    (backup_dir / "backup2.yaml").touch()
    (backup_dir / "not_a_backup.txt").touch()

    # 2. Run the script with mocked sys.argv
    with patch.object(sys, "argv", ["locate_yaml_backups.py", str(backup_dir)]):
        with pytest.raises(SystemExit) as e:
            locate_yaml_backups_main()
        assert e.value.code == 0

    # 3. Check stdout
    captured = capsys.readouterr()
    output = captured.out
    assert "backup1.yaml" in output
    assert "backup2.yaml" in output
    assert "not_a_backup.txt" not in output


def test_locate_yaml_backups_no_files(tmp_path, capsys):
    """
    Tests locate_yaml_backups.py script when no files are found.
    """
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    with patch.object(sys, "argv", ["locate_yaml_backups.py", str(backup_dir)]):
        with pytest.raises(SystemExit) as e:
            locate_yaml_backups_main()
        assert e.value.code == 0

    captured = capsys.readouterr()
    assert "No YAML backups found" in captured.out
