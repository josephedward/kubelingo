import os
import importlib
import sqlite3

import pytest

import kubelingo.utils.config as config
from pathlib import Path

@pytest.fixture(autouse=True)
def isolate_config(monkeypatch, tmp_path):
    # Redirect project root and data dirs to a temp path for isolation
    monkeypatch.setattr(config, 'PROJECT_ROOT', str(tmp_path))
    # Create canonical subdirs under tmp_path
    qdir = tmp_path / 'question-data' / 'questions'
    yqdir = tmp_path / 'question-data' / 'yaml'
    dd = tmp_path / 'question-data'
    qdir.mkdir(parents=True)
    yqdir.mkdir(parents=True)
    dd.mkdir(exist_ok=True)
    # Override config dirs
    monkeypatch.setattr(config, 'QUESTIONS_DIR', str(qdir))
    monkeypatch.setattr(config, 'YAML_QUIZ_DIR', str(yqdir))
    monkeypatch.setattr(config, 'DATA_DIR', str(tmp_path / 'question-data'))
    # Override database file to tmp
    dbfile = tmp_path / 'kubelingo.db'
    monkeypatch.setattr(config, 'DATABASE_FILE', str(dbfile))
    # Reload path_utils to pick up monkeypatched config
    import kubelingo.utils.path_utils as pu
    importlib.reload(pu)
    return pu

def test_get_all_question_dirs(isolate_config):
    pu = isolate_config
    dirs = pu.get_all_question_dirs()
    # Should include both QUESTIONS_DIR and YAML_QUIZ_DIR
    assert str(config.QUESTIONS_DIR) in dirs
    assert str(config.YAML_QUIZ_DIR) in dirs

def test_discover_question_files(isolate_config, tmp_path, monkeypatch):
    pu = isolate_config
    # Create sample YAML files in QUESTIONS_DIR and YAML_QUIZ_DIR
    qfile = Path(config.QUESTIONS_DIR) / 'test1.yaml'
    qfile.write_text('- foo')
    yfile = Path(config.YAML_QUIZ_DIR) / 'test2.yml'
    yfile.write_text('- bar')
    # Discover
    files = list(pu.discover_question_files())
    assert str(qfile) in files
    assert str(yfile) in files

def test_discover_yaml_backups(isolate_config, tmp_path):
    pu = isolate_config
    # Create backups dir under PROJECT_ROOT
    backups = tmp_path / 'backups'
    backups.mkdir()
    # Create sample YAML backups
    f1 = backups / 'bk1.yaml'
    f2 = backups / 'bk2.yml'
    f1.write_text('[]')
    f2.write_text('[]')
    # Reload path_utils to pick up new dir
    import kubelingo.utils.path_utils as pu_reload
    importlib.reload(pu_reload)
    found = list(pu_reload.discover_yaml_backups())
    assert str(f1) in found
    assert str(f2) in found

def test_discover_sqlite_backups(isolate_config, tmp_path):
    pu = isolate_config
    # Create backups dir under PROJECT_ROOT
    backups = tmp_path / 'backups'
    backups.mkdir()
    # Create sample .db backups
    d1 = backups / 'old.db'
    sconn = sqlite3.connect(str(d1))
    sconn.execute('CREATE TABLE test (id INTEGER)')
    sconn.commit(); sconn.close()
    # Reload path_utils
    import kubelingo.utils.path_utils as pu_reload
    importlib.reload(pu_reload)
    found = list(pu_reload.discover_sqlite_backups())
    assert str(d1) in found

def test_get_live_db_path(isolate_config):
    pu = isolate_config
    # Should return the monkeypatched DATABASE_FILE
    assert pu.get_live_db_path() == config.DATABASE_FILE