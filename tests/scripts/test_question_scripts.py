import sys
import sqlite3
import pytest
from pathlib import Path
import importlib.util
import sqlite3

# Directory containing the maintenance scripts (project root)
ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = ROOT / 'scripts'

def load_script(name):
    spec = importlib.util.spec_from_file_location(name, str(SCRIPTS_DIR / f'{name}.py'))
    mod = importlib.util.module_from_spec(spec)
    # Ensure project root is on sys.path for imports
    sys.path.insert(0, str(ROOT))
    spec.loader.exec_module(mod)
    sys.path.pop(0)
    return mod

@pytest.fixture
def temp_db_with_duplicates(tmp_path):
    """Creates a temporary database with duplicate and unique questions."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # The schema should match what get_all_questions expects
    cursor.execute("""
        CREATE TABLE questions (
            id TEXT PRIMARY KEY,
            prompt TEXT,
            response TEXT,
            source TEXT,
            source_file TEXT,
            category TEXT,
            validation_steps TEXT,
            validator TEXT,
            review BOOLEAN
        )
    """)
    questions = [
        # id, prompt, response, source, source_file, category, validation_steps, validator, review
        ('q1', 'duplicate prompt', 'res1', 'src1', 'file1.yaml', 'cat1', '[]', '{}', False),
        ('q2', 'unique prompt', 'res2', 'src2', 'file1.yaml', 'cat2', '[]', '{}', False),
        ('q3', 'duplicate prompt', 'res3', 'src3', 'file2.yaml', 'cat3', '[]', '{}', False),
        ('q4', 'another unique', 'res4', 'src4', 'file2.yaml', 'cat4', '[]', '{}', False)
    ]
    cursor.executemany("INSERT INTO questions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", questions)
    conn.commit()
    conn.close()
    return db_path

def test_deduplicate_questions_dry_run(temp_db_with_duplicates, capsys, monkeypatch):
    """Tests the deduplicate subcommand of question_manager.py in dry-run mode."""
    question_manager_mod = load_script('question_manager')

    # Run in dry-run mode
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'deduplicate', '--db-path', str(temp_db_with_duplicates)])
    question_manager_mod.main()

    # Check output
    captured = capsys.readouterr()
    assert "Found 1 prompts with duplicate questions." in captured.out
    assert 'Prompt: "duplicate prompt"' in captured.out
    assert "Keeping: q1" in captured.out
    assert "Duplicate: q3" in captured.out
    assert "another unique" not in captured.out

    # Check db content is unchanged
    conn = sqlite3.connect(temp_db_with_duplicates)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM questions")
    assert cursor.fetchone()[0] == 4
    conn.close()

def test_deduplicate_questions_delete(temp_db_with_duplicates, capsys, monkeypatch):
    """Tests the deduplicate subcommand of question_manager.py with --delete flag."""
    question_manager_mod = load_script('question_manager')

    # Run with --delete flag
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'deduplicate', '--db-path', str(temp_db_with_duplicates), '--delete'])
    question_manager_mod.main()

    # Check output
    captured = capsys.readouterr()
    assert "Found 1 prompts with duplicate questions." in captured.out
    assert "Deleting duplicates" in captured.out
    assert 'Prompt: "duplicate prompt"' in captured.out
    assert "Keeping: q1" in captured.out
    assert "Deleting: q3" in captured.out
    assert "Successfully deleted 1 duplicate questions." in captured.out

    # Check db content was changed
    conn = sqlite3.connect(temp_db_with_duplicates)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM questions")
    assert cursor.fetchone()[0] == 3
    cursor.execute("SELECT id FROM questions WHERE prompt = 'duplicate prompt'")
    assert cursor.fetchone()[0] == 'q1'
    cursor.execute("SELECT COUNT(*) FROM questions WHERE id = 'q3'")
    assert cursor.fetchone()[0] == 0
    conn.close()

def test_categorize_questions_flow(tmp_path, capsys, monkeypatch):
    # Setup a fresh DB for testing
    import kubelingo.utils.config as config
    # Override master backups to avoid seeding
    monkeypatch.setattr(config, 'MASTER_DATABASE_FILE', str(tmp_path / 'no.db'))
    monkeypatch.setattr(config, 'SECONDARY_MASTER_DATABASE_FILE', str(tmp_path / 'no.db'))
    db_file = tmp_path / 'test.db'
    monkeypatch.setattr(config, 'DATABASE_FILE', str(db_file))
    # Initialize empty DB
    import kubelingo.database as dbmod
    dbmod.init_db(clear=True)
    # Insert a question without valid subject
    dbmod.add_question(id='q1', prompt='?', source_file='f.yaml')

    mod = load_script('question_manager')
    # First, list missing subjects
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'categorize'])
    mod.main()
    out = capsys.readouterr().out
    assert 'Questions with missing or invalid subjects' in out
    assert 'subject_matter=None' in out
    # Assign a valid subject
    valid = dbmod.SUBJECT_MATTER[0]
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'categorize', '--assign', '1', valid])
    mod.main()
    out2 = capsys.readouterr().out
    assert f"Assigned subject '{valid}' to question rowid 1" in out2
    # Verify the DB was updated
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute('SELECT subject_matter FROM questions WHERE rowid = ?', (1,))
    sub = cur.fetchone()[0]
    conn.close()
    assert sub == valid
