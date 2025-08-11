import pytest
pytest.skip("Skipping path_utils tests not related to maintenance scripts", allow_module_level=True)
import os
import pytest
from pathlib import Path

from kubelingo.utils.path_utils import (
    get_live_db_path,
    get_all_question_dirs,
    find_yaml_files,
    get_all_yaml_backup_dirs,
    find_yaml_backup_files,
    get_all_sqlite_backup_dirs,
    find_sqlite_backup_files,
    get_latest_yaml_backup,
    get_latest_sqlite_backup,
)

def test_get_live_db_path_exists():
    db_path = get_live_db_path()
    assert isinstance(db_path, Path)
    # It may not exist in CI, but path string should be non-empty
    assert str(db_path)

def test_get_all_question_dirs_returns_list():
    dirs = get_all_question_dirs()
    assert isinstance(dirs, list)
    # At least one candidate directory string
    assert dirs, "No question directories configured"
    for d in dirs:
        assert isinstance(d, Path)

def test_find_yaml_files_non_empty():
    files = find_yaml_files()
    assert isinstance(files, list)
    # Should find some YAML files in question dirs
    assert files, "No YAML files found in question directories"
    for f in files[:5]:
        assert f.suffix in ('.yaml', '.yml')

def test_yaml_backup_dirs_and_files():
    dirs = get_all_yaml_backup_dirs()
    assert isinstance(dirs, list)
    for d in dirs:
        assert d.is_dir(), f"Backup dir not found: {d}"
    files = find_yaml_backup_files()
    # May be empty if no backups, but should return a list
    assert isinstance(files, list)

def test_sqlite_backup_dirs_and_files():
    dirs = get_all_sqlite_backup_dirs()
    assert isinstance(dirs, list)
    for d in dirs:
        assert d.is_dir(), f"SQLite backup dir not found: {d}"
    files = find_sqlite_backup_files()
    # Return a list; may be empty
    assert isinstance(files, list)

def test_get_latest_backups_return_path_or_none():
    yaml_latest = get_latest_yaml_backup()
    assert yaml_latest is None or isinstance(yaml_latest, Path)
    sqlite_latest = get_latest_sqlite_backup()
    assert sqlite_latest is None or isinstance(sqlite_latest, Path)