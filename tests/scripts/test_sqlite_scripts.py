import sqlite3
import sys
import pytest
from pathlib import Path
import importlib.util

# Directory containing the maintenance scripts (project root)
ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = ROOT / 'scripts'

def load_script(name):
    """Dynamically load a script module by filename without caching issues."""
    path = SCRIPTS_DIR / f'{name}.py'
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    # Ensure project root is on sys.path for imports
    sys.path.insert(0, str(ROOT))
    spec.loader.exec_module(mod)
    sys.path.pop(0)
    return mod

def test_view_sqlite_schema(tmp_path, capsys, monkeypatch):
    # Create a temporary SQLite DB with a table and an index
    db_path = tmp_path / 'test.db'
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute('CREATE TABLE foo (id INTEGER PRIMARY KEY, name TEXT)')
    cur.execute('CREATE INDEX idx_name ON foo(name)')
    conn.commit()
    conn.close()

    mod = load_script('view_sqlite_schema')
    import kubelingo.utils.config as config
    monkeypatch.setattr(config, 'DATABASE_FILE', str(db_path))
    # Invoke with explicit db-path
    monkeypatch.setattr(sys, 'argv', ['view_sqlite_schema', '-d', str(db_path)])
    mod.main()
    out = capsys.readouterr().out
    assert 'CREATE TABLE foo' in out
    assert 'CREATE INDEX idx_name' in out

def test_locate_sqlite_backups_no_files(tmp_path, capsys, monkeypatch):
    mod = load_script('locate_sqlite_backups')
    monkeypatch.setattr(sys, 'argv', ['locate_sqlite_backups', str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert f'No SQLite backups found in {tmp_path}' in out

def test_locate_sqlite_backups_with_files(tmp_path, capsys, monkeypatch):
    # Create dummy .db files
    f1 = tmp_path / 'a.db'
    f2 = tmp_path / 'b.db'
    f1.write_text('x')
    f2.write_text('y')
    mod = load_script('locate_sqlite_backups')
    monkeypatch.setattr(sys, 'argv', ['locate_sqlite_backups', str(tmp_path)])
    mod.main()
    out = capsys.readouterr().out
    assert str(f1) in out
    assert str(f2) in out

def test_diff_sqlite_detects_changes(tmp_path, capsys, monkeypatch):
    old = tmp_path / 'old.db'
    new = tmp_path / 'new.db'
    # old DB has table a
    conn = sqlite3.connect(str(old))
    conn.execute('CREATE TABLE a (x)')
    conn.commit(); conn.close()
    # new DB has table b
    conn = sqlite3.connect(str(new))
    conn.execute('CREATE TABLE b (x)')
    conn.commit(); conn.close()
    mod = load_script('diff_sqlite')
    monkeypatch.setattr(sys, 'argv', ['diff_sqlite', str(old), str(new)])
    mod.main()
    out = capsys.readouterr().out
    assert 'Removed: table a' in out
    assert 'Added: table b' in out

def test_create_sqlite_backup_error(tmp_path, capsys, monkeypatch):
    # No live DB exists => error
    import kubelingo.utils.config as config
    monkeypatch.setattr(config, 'DATABASE_FILE', str(tmp_path / 'no.db'))
    mod = load_script('create_sqlite_backup')
    monkeypatch.setattr(sys, 'argv', ['create_sqlite_backup', '-o', str(tmp_path / 'backups')])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert 'Error: live database not found' in out

def test_create_sqlite_backup_success(tmp_path, capsys, monkeypatch):
    import kubelingo.utils.config as config
    # Create a dummy live DB file
    dbfile = tmp_path / 'db.db'
    dbfile.write_text('dummy')
    monkeypatch.setattr(config, 'DATABASE_FILE', str(dbfile))
    outdir = tmp_path / 'backups'
    mod = load_script('create_sqlite_backup')
    monkeypatch.setattr(sys, 'argv', ['create_sqlite_backup', '-o', str(outdir)])
    mod.main()
    out = capsys.readouterr().out
    assert 'Backup created:' in out
    # One backup file with timestamped name
    backups = list(outdir.glob('kubelingo_*.db'))
    assert len(backups) == 1

def test_restore_sqlite_error(tmp_path, capsys, monkeypatch):
    mod = load_script('restore_sqlite')
    missing = tmp_path / 'no.db'
    monkeypatch.setattr(sys, 'argv', ['restore_sqlite', str(missing)])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert 'Error: backup file not found' in out

def test_restore_sqlite_success(tmp_path, capsys, monkeypatch):
    import kubelingo.utils.config as config
    backup = tmp_path / 'backup.db'
    backup.write_text('content')
    # Set live DB path
    live_db = tmp_path / 'live.db'
    monkeypatch.setattr(config, 'DATABASE_FILE', str(live_db))
    pre_dir = tmp_path / 'pre'
    mod = load_script('restore_sqlite')
    monkeypatch.setattr(sys, 'argv', ['restore_sqlite', str(backup), '-p', str(pre_dir)])
    mod.main()
    out = capsys.readouterr().out
    assert f'Restored live database from {backup}' in out
    # Live DB was copied
    assert live_db.read_text() == 'content'