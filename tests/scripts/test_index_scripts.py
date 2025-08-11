import sys
import pytest
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = ROOT / 'scripts'

def load_script(name):
    spec = importlib.util.spec_from_file_location(name, str(SCRIPTS_DIR / f'{name}.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT))
    spec.loader.exec_module(mod)
    sys.path.pop(0)
    return mod

def test_index_yaml_files(tmp_path, capsys, monkeypatch):
    # Setup a fake question directory with yaml files
    dir1 = tmp_path / 'questions'
    dir1.mkdir()
    f1 = dir1 / 'a.yaml'
    f2 = dir1 / 'b.yml'
    f1.write_text('x')
    f2.write_text('y')
    # Override QUESTION_DIRS
    import kubelingo.utils.config as config
    monkeypatch.setattr(config, 'QUESTION_DIRS', [str(dir1)])
    mod = load_script('index_yaml_files')
    mod.main()
    out = capsys.readouterr().out
    assert str(dir1) in out
    assert str(f1) in out
    assert str(f2) in out

def test_index_sqlite_files(tmp_path, capsys, monkeypatch):
    # Setup fake backup directory with sqlite files
    dir1 = tmp_path / 'backups'
    dir1.mkdir()
    d1 = dir1 / 'foo.db'
    d2 = dir1 / 'bar.db'
    d1.write_text('')
    d2.write_text('')
    # Override SQLITE_BACKUP_DIRS
    import kubelingo.utils.config as config
    monkeypatch.setattr(config, 'SQLITE_BACKUP_DIRS', [str(dir1)])
    mod = load_script('index_sqlite_files')
    mod.main()
    out = capsys.readouterr().out
    assert str(dir1) in out
    assert str(d1) in out
    assert str(d2) in out

def test_index_sqlite_no_files(tmp_path, capsys, monkeypatch):
    # Empty backup dir
    dir1 = tmp_path / 'backups'
    dir1.mkdir()
    import kubelingo.utils.config as config
    monkeypatch.setattr(config, 'SQLITE_BACKUP_DIRS', [str(dir1)])
    mod = load_script('index_sqlite_files')
    mod.main()
    out = capsys.readouterr().out
    assert 'No SQLite files found' in out