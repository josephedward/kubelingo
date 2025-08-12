import os
import shutil
import sys
from pathlib import Path
import pytest
import yaml

# Add project root to sys.path to allow imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# The script to be tested
from scripts import consolidator

@pytest.fixture
def test_env(tmp_path, monkeypatch):
    """Setup a temporary test environment mirroring the project structure."""
    original_cwd = Path.cwd()
    project_dir = tmp_path
    os.chdir(project_dir)

    # Mock dependencies from kubelingo modules
    monkeypatch.setattr(consolidator, "project_root", project_dir)
    app_dir = project_dir / ".kubelingo"
    app_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(consolidator, "APP_DIR", app_dir)

    # --- Create test directory structure and files ---
    (project_dir / "archive").mkdir()
    question_data_dir = project_dir / "question-data"
    
    # for merge_solutions
    solutions_dir = question_data_dir / "yaml" / "solutions" / "category1"
    solutions_dir.mkdir(parents=True)
    (solutions_dir / "sol1.sh").write_text("echo 'hello'")
    (solutions_dir / "sol2.yaml").write_text("key: value")
    
    # for consolidate_manifests
    manifests_archive_dir = question_data_dir / "archive" / "manifests"
    manifests_archive_dir.mkdir(parents=True)
    (manifests_archive_dir / "m.yaml").write_text(yaml.dump([{"id": "m1", "prompt": "p1"}]))

    # for consolidate_dbs
    (project_dir / "backup_questions.db").touch()
    (project_dir / "categorized.db").touch()
    (app_dir / "kubelingo.db").touch()
    sqlite_backup_dir = project_dir / 'backups' / 'sqlite'
    sqlite_backup_dir.mkdir(parents=True)
    (sqlite_backup_dir / 'old.sqlite3').touch()

    # for merge_quizzes
    (project_dir / "source.yaml").write_text(yaml.dump([{"id": "q1", "p": "p1"}, {"id": "q2", "p": "p2"}]))
    (project_dir / "dest.yaml").write_text(yaml.dump([{"id": "q1", "p": "p1-old"}]))

    # for consolidate_backups
    (project_dir / "toplevel.db").touch()
    (project_dir / "another.yaml").write_text("foo: bar")

    yield project_dir

    os.chdir(original_cwd)

def run_consolidator(monkeypatch, args):
    """Helper to run the consolidator script with args."""
    monkeypatch.setattr(sys, 'argv', ['scripts/consolidator.py'] + args)
    consolidator.main()

def test_consolidate_backups(test_env, monkeypatch):
    assert (test_env / "toplevel.db").exists()
    run_consolidator(monkeypatch, ['backups'])
    archive_dir = test_env / "archive"
    assert len(list(archive_dir.iterdir())) >= 7
    assert not (test_env / "toplevel.db").exists()

def test_consolidate_dbs(test_env, monkeypatch):
    run_consolidator(monkeypatch, ['dbs'])
    app_dir = test_env / ".kubelingo"
    assert len(list(app_dir.glob("kubelingo_db_*.db"))) == 4
    assert not (test_env / "backup_questions.db").exists()

def test_consolidate_manifests(test_env, monkeypatch):
    run_consolidator(monkeypatch, ['manifests'])
    output_file = test_env / "question-data" / "yaml" / "manifests_quiz.yaml"
    assert output_file.exists()
    with open(output_file, 'r') as f:
        data = yaml.safe_load(f)
    assert data[0]['id'] == 'm1'

def test_merge_quizzes(test_env, monkeypatch):
    source_file = test_env / "source.yaml"
    dest_file = test_env / "dest.yaml"
    run_consolidator(monkeypatch, ['merge-quizzes', '--source', str(source_file), '--destination', str(dest_file)])
    with open(dest_file, 'r') as f:
        data = yaml.safe_load(f)
    assert len(data) == 2
    ids = {item['id'] for item in data}
    assert ids == {'q1', 'q2'}
    assert source_file.exists()

def test_merge_quizzes_delete_source(test_env, monkeypatch):
    source_file = test_env / "source.yaml"
    dest_file = test_env / "dest.yaml"
    run_consolidator(monkeypatch, ['merge-quizzes', '--source', str(source_file), '--destination', str(dest_file), '--delete-source'])
    assert not source_file.exists()

def test_merge_solutions(test_env, monkeypatch):
    run_consolidator(monkeypatch, ['merge-solutions'])
    output_file = test_env / "question-data" / "yaml" / "solutions" / "category1" / "category1_solutions.yaml"
    assert output_file.exists()
    with open(output_file, 'r') as f:
        content = f.read()
    assert "sol1: |-" in content
    assert "echo 'hello'" in content
