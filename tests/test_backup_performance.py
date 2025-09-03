import os
import shutil
import tempfile
import yaml
import pytest

import kubelingo.utils as utils
from kubelingo.utils import backup_performance_yaml

@pytest.fixture(autouse=True)
def temp_project(tmp_path, monkeypatch):
    # Create a fake project root with user_data and misc
    project_root = tmp_path / "project_root"
    user_data = project_root / "user_data"
    user_data.mkdir(parents=True)
    # Write a dummy performance.yaml
    perf_file = user_data / "performance.yaml"
    perf_file.write_text(yaml.safe_dump({'score': 42}))
    # Monkeypatch PROJECT_ROOT used by backup_performance_yaml
    monkeypatch.setattr(utils, '_PROJECT_ROOT', str(project_root))
    return project_root, perf_file

def test_backup_performance_preserves_original_and_creates_copy(temp_project):
    project_root, orig_file = temp_project
    misc_dir = project_root / 'misc'
    backup_performance_yaml()
    # Original should still exist
    assert orig_file.exists()
    # Backup directory should exist
    assert misc_dir.exists()
    backup_file = misc_dir / 'performance.yaml'
    # Backup file should exist with same contents
    assert backup_file.exists()
    assert backup_file.read_text() == orig_file.read_text()