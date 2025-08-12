import subprocess
import sqlite3
import os
import re
from pathlib import Path
import pytest
from kubelingo.database import get_db_connection, run_sql_file

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / 'scripts'


def run(cmd, cwd=ROOT):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def test_show_db_schema_runs(tmp_path, monkeypatch):
    # Ensure script runs without error, even if DB is empty
    # Monkeypatch database file to tmp_path/test.db
    test_db = tmp_path / 'test.db'
    monkeypatch.setenv('HOME', str(tmp_path))
    # Run script
    result = run(['python3', str(SCRIPTS / 'show_db_schema.py')])
    assert result.returncode == 0, result.stderr
    assert 'Tables:' in result.stdout


def test_locate_sqlite_backups_basic(tmp_path):
    # Create directory with two .db files
    backup_dir = tmp_path / 'bkp'
    backup_dir.mkdir()
    file1 = backup_dir / 'one.db'
    file2 = backup_dir / 'two.db'
    file1.write_text('x')
    file2.write_text('y')
    result = run(['python3', str(SCRIPTS / 'locate_sqlite_backups.py'), str(backup_dir)])
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert str(file1) in out
    assert str(file2) in out


def test_diff_sqlite_schema(tmp_path):
    # Create two small DBs with different tables
    db1 = tmp_path / 'a.db'
    db2 = tmp_path / 'b.db'
    conn = sqlite3.connect(db1)
    conn.execute('CREATE TABLE alpha (id);')
    conn.commit(); conn.close()
    conn = sqlite3.connect(db2)
    conn.execute('CREATE TABLE beta (id);')
    conn.commit(); conn.close()
    result = run(['python3', str(SCRIPTS / 'diff_sqlite.py'), str(db1), str(db2)])
    assert result.returncode == 0, result.stderr
    out = result.stdout
    # Expect one removed and one added
    assert re.search(r'Removed: table alpha', out, re.IGNORECASE)
    assert re.search(r'Added: table beta', out, re.IGNORECASE)


def test_create_sqlite_backup_error(tmp_path, monkeypatch):
    # Remove live DB if exists and set HOME to tmp, so DATABASE_FILE missing
    monkeypatch.setenv('HOME', str(tmp_path))
    backup_dir = tmp_path / 'out'
    backup_dir.mkdir()
    # Expect backup of existing live DB
    result = run(['python3', str(SCRIPTS / 'create_sqlite_backup.py'), '-o', str(backup_dir)])
    assert result.returncode == 0, result.stderr
    backups = list(backup_dir.iterdir())
    assert backups, 'No backup file created'
    # Filename starts with prefix
    assert any(p.name.startswith('kubelingo_') and p.suffix == '.db' for p in backups)


def test_restore_sqlite_error(tmp_path, monkeypatch):
    # No backup file -> error
    monkeypatch.setenv('HOME', str(tmp_path))
    fake = tmp_path / 'nope.db'
    result = run(['python3', str(SCRIPTS / 'restore_sqlite.py'), str(fake)])
    assert result.returncode != 0
    assert 'Error: backup file not found' in result.stdout + result.stderr


def test_run_sql_file(tmp_path):
    # Test running a SQL file against the database
    sql_file = tmp_path / "test.sql"
    sql_file.write_text("""
        CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT);
        INSERT INTO test_table (name) VALUES ('Alice'), ('Bob');
    """)

    db_path = tmp_path / "test.db"
    conn = get_db_connection(str(db_path))

    # Run the SQL file
    run_sql_file(conn, str(sql_file))

    # Verify the table and data
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM test_table ORDER BY id")
    rows = cursor.fetchall()
    assert [row["name"] for row in rows] == ["Alice", "Bob"]

    conn.close()
