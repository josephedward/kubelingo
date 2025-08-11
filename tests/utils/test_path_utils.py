import time
from pathlib import Path

import pytest

from kubelingo.utils import path_utils


@pytest.fixture
def setup_test_db_paths(tmp_path: Path):
    """Set up a temporary directory structure for database path tests."""
    # Default DB location
    default_db_dir = tmp_path / ".kubelingo"
    default_db_dir.mkdir()
    default_db_path = default_db_dir / "kubelingo.db"
    default_db_path.touch()

    # Backup DB location
    backup_dir = tmp_path / "backups" / "sqlite"
    backup_dir.mkdir(parents=True)

    # Create a few backup files with different timestamps
    db1_path = backup_dir / "kubelingo_db_20250101_000000.sqlite3"
    db1_path.touch()
    time.sleep(0.1)  # Ensure modification times are distinct

    db2_path = backup_dir / "kubelingo_db_20250102_000000.sqlite3"
    db2_path.touch()

    return default_db_path, backup_dir, db2_path


def test_get_live_db_path_finds_latest_backup(
    setup_test_db_paths, monkeypatch
):
    """
    Test that get_live_db_path returns the path to the most recent backup
    when backups are present.
    """
    default_db_path, backup_dir, latest_db_path = setup_test_db_paths

    # Monkeypatch config constants and functions to use our temporary paths
    monkeypatch.setattr(path_utils, "DATABASE_FILE", str(default_db_path))
    monkeypatch.setattr(
        path_utils, "get_all_sqlite_backup_dirs", lambda: [str(backup_dir)]
    )

    # Call the function and assert it returns the latest DB path
    live_db_path = path_utils.get_live_db_path()
    assert live_db_path == str(latest_db_path)


def test_get_live_db_path_falls_back_to_default(
    setup_test_db_paths, monkeypatch
):
    """
    Test that get_live_db_path returns the default path when no backups
    are found in the backup directory.
    """
    default_db_path, backup_dir, _ = setup_test_db_paths

    # Clear the backup directory to simulate no backups
    for f in backup_dir.iterdir():
        f.unlink()

    monkeypatch.setattr(path_utils, "DATABASE_FILE", str(default_db_path))
    monkeypatch.setattr(
        path_utils, "get_all_sqlite_backup_dirs", lambda: [str(backup_dir)]
    )

    live_db_path = path_utils.get_live_db_path()
    assert live_db_path == str(default_db_path)


def test_get_live_db_path_handles_empty_backup_config(
    setup_test_db_paths, monkeypatch
):
    """
    Test that get_live_db_path falls back to default if backup dirs list is empty.
    """
    default_db_path, _, _ = setup_test_db_paths
    monkeypatch.setattr(path_utils, "DATABASE_FILE", str(default_db_path))
    monkeypatch.setattr(path_utils, "get_all_sqlite_backup_dirs", lambda: [])

    live_db_path = path_utils.get_live_db_path()
    assert live_db_path == str(default_db_path)
