import sys
import sqlite3
import pytest
from pathlib import Path
import importlib.util
import sqlite3
import json

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
    # Schema matches the one from kubelingo/database.py
    cursor.execute("""
        CREATE TABLE questions (
            id TEXT PRIMARY KEY,
            prompt TEXT NOT NULL,
            response TEXT,
            category TEXT,
            subject TEXT,
            source TEXT,
            source_file TEXT NOT NULL,
            raw TEXT,
            validation_steps TEXT,
            validator TEXT,
            review BOOLEAN NOT NULL DEFAULT 0
        )
    """)
    questions = [
        ('q1', 'duplicate prompt', 'file1.yaml'),
        ('q2', 'unique prompt', 'file1.yaml'),
        ('q3', 'duplicate prompt', 'file2.yaml'),
        ('q4', 'another unique', 'file2.yaml')
    ]
    cursor.executemany("INSERT INTO questions (id, prompt, source_file) VALUES (?, ?, ?)", questions)
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
    assert "Keeping: q3" in captured.out
    assert "Duplicate: q1" in captured.out
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
    assert "Keeping: q3" in captured.out
    assert "Deleting: q1" in captured.out
    assert "Successfully deleted 1 duplicate questions." in captured.out

    # Check db content was changed
    conn = sqlite3.connect(temp_db_with_duplicates)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM questions")
    assert cursor.fetchone()[0] == 3
    cursor.execute("SELECT id FROM questions WHERE prompt = 'duplicate prompt'")
    assert cursor.fetchone()[0] == 'q3'
    cursor.execute("SELECT COUNT(*) FROM questions WHERE id = 'q1'")
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
    # Prevent auto-population from YAML files
    monkeypatch.setattr(dbmod, 'import_questions_from_yaml_files', lambda *args, **kwargs: None)
    # Create a connection and initialize schema directly to avoid file-based init issues in test
    conn = sqlite3.connect(db_file)
    dbmod.init_db(conn=conn)
    # Clear any pre-existing data from schema init and insert test data
    cursor = conn.cursor()
    cursor.execute("DELETE FROM questions")
    cursor.execute("INSERT INTO questions (id, prompt, source_file, subject) VALUES (?, ?, ?, ?)", ('q1', '?', 'f.yaml', 'invalid-subject-for-test'))
    conn.commit()
    conn.close()

    mod = load_script('question_manager')
    # First, list missing subjects
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'categorize'])
    mod.main()
    out = capsys.readouterr().out
    assert 'Questions with missing or invalid subjects' in out
    assert 'subject=None' in out
    # Assign a valid subject
    valid = dbmod.SUBJECT_MATTER[0]
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'categorize', '--assign', '1', valid])
    mod.main()
    out2 = capsys.readouterr().out
    assert f"Assigned subject '{valid}' to question rowid 1" in out2
    # Verify the DB was updated
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute('SELECT subject FROM questions WHERE rowid = ?', (1,))
    sub = cur.fetchone()[0]
    conn.close()
    assert sub == valid


@pytest.fixture
def temp_yaml_file(tmp_path):
    """Creates a temporary YAML file with a couple of questions."""
    yaml_content = """
- id: yaml_q1
  prompt: 'What is a pod?'
  source_file: 'test.yaml'
  subject: 'Pods'
- id: yaml_q2
  prompt: 'What is a service?'
  source_file: 'test.yaml'
  subject: 'Services'
    """
    yaml_file = tmp_path / "questions.yaml"
    yaml_file.write_text(yaml_content)
    return yaml_file


def test_build_db_command(tmp_path, temp_yaml_file, capsys, monkeypatch):
    """Tests the build-db subcommand of question_manager.py."""
    question_manager_mod = load_script('question_manager')
    db_path = tmp_path / "build_test.db"

    # Run build-db command
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'build-db', '--db-path', str(db_path), str(temp_yaml_file)])
    question_manager_mod.main()

    # Check output
    captured = capsys.readouterr()
    assert "Found 1 YAML files to import." in captured.out
    assert "Import complete. Added: 2, Skipped/Existing: 0" in captured.out

    # Check db content
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM questions")
    assert cursor.fetchone()[0] == 2
    cursor.execute("SELECT id FROM questions WHERE prompt = 'What is a pod?'")
    assert cursor.fetchone()[0] == 'yaml_q1'
    conn.close()


def test_build_db_command_clear(tmp_path, temp_yaml_file, capsys, monkeypatch):
    """Tests the build-db subcommand with the --clear flag."""
    question_manager_mod = load_script('question_manager')
    db_path = tmp_path / "build_test.db"

    # Run once to populate
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'build-db', '--db-path', str(db_path), str(temp_yaml_file)])
    question_manager_mod.main()

    # Create a new yaml file for the clear run
    new_yaml_content = """
- id: yaml_q3
  prompt: 'What is a namespace?'
  source_file: 'new.yaml'
  subject: 'Namespaces'
    """
    new_yaml_file = tmp_path / "new_questions.yaml"
    new_yaml_file.write_text(new_yaml_content)

    # Run build-db with --clear
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'build-db', '--db-path', str(db_path), '--clear', '--no-backup', str(new_yaml_file)])
    question_manager_mod.main()

    # Check output
    captured = capsys.readouterr()
    assert f"Removed existing database at {db_path}" in captured.out
    assert "Import complete. Added: 1, Skipped/Existing: 0" in captured.out

    # Check db content is only the new question
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM questions")
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT id FROM questions")
    assert cursor.fetchone()[0] == 'yaml_q3'
    conn.close()


@pytest.fixture
def temp_db_for_enrich(tmp_path):
    """Creates a temporary database with a question needing source enrichment."""
    db_path = tmp_path / "enrich_test.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Need all columns from schema
    cursor.execute("""
        CREATE TABLE questions (
            id TEXT PRIMARY KEY, prompt TEXT, source TEXT, source_file TEXT,
            response TEXT, category TEXT, subject TEXT, raw TEXT, validation_steps TEXT, validator TEXT, review BOOLEAN,
            category_id TEXT, subject_id TEXT, schema_category TEXT, question_type TEXT, links TEXT
        )
    """)
    cursor.execute(
        "INSERT INTO questions (id, prompt, source_file) VALUES (?, ?, ?)",
        ('enrich_q1', 'a prompt', 'my_quiz.yaml')
    )
    conn.commit()
    conn.close()
    return db_path


def test_enrich_sources_command(temp_db_for_enrich, capsys, monkeypatch):
    """Tests the enrich-sources subcommand of question_manager.py."""
    question_manager_mod = load_script('question_manager')

    # Mock ENABLED_QUIZZES
    monkeypatch.setattr(question_manager_mod.cfg, 'ENABLED_QUIZZES', {'my-quiz-name': '/path/to/my_quiz.yaml'})

    # Mock get_db_connection to return a connection to the temp db
    def mock_get_db_connection(db_path=None):
        return sqlite3.connect(temp_db_for_enrich)

    monkeypatch.setattr(question_manager_mod, 'get_db_connection', mock_get_db_connection)

    # Run enrich-sources command
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'enrich-sources'])
    question_manager_mod.main()

    # Check output
    captured = capsys.readouterr()
    assert "Found 1 questions missing a source. Updating..." in captured.out
    assert "Successfully updated 1 questions." in captured.out

    # Check db content
    conn = sqlite3.connect(temp_db_for_enrich)
    cursor = conn.cursor()
    cursor.execute("SELECT source FROM questions WHERE id = 'enrich_q1'")
    assert cursor.fetchone()[0] == 'my-quiz-name'
    conn.close()


def test_add_service_account_questions_command(tmp_path, capsys, monkeypatch):
    """Tests the add-sa-questions subcommand of question_manager.py."""
    question_manager_mod = load_script('question_manager')

    kubelingo_dir = tmp_path / ".kubelingo"
    monkeypatch.setattr(question_manager_mod.os.path, 'expanduser', lambda _: str(kubelingo_dir))

    # Run add-sa-questions command
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'add-sa-questions'])
    question_manager_mod.main()

    # Check output
    captured = capsys.readouterr()
    assert "Added question service_account_script::1" in captured.out
    assert "Total ServiceAccount questions in DB (source=service_account_script): 3" in captured.out

    # Check db content
    db_path = kubelingo_dir / "kubelingo.db"
    assert db_path.exists()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM questions WHERE source_file = 'service_account_script'")
    assert cursor.fetchone()[0] == 3
    conn.close()


def test_generate_sa_questions_to_stdout(capsys, monkeypatch):
    """Tests the generate-sa-questions subcommand printing to stdout."""
    question_manager_mod = load_script('question_manager')
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'generate-sa-questions', '-n', '1'])
    question_manager_mod.main()

    captured = capsys.readouterr()
    assert '"id": "service_accounts::0"' in captured.out
    assert '"id": "service_accounts::1"' not in captured.out
    assert 'Wrote' not in captured.out


def test_generate_sa_questions_to_file(tmp_path, capsys, monkeypatch):
    """Tests the generate-sa-questions subcommand writing to a file."""
    question_manager_mod = load_script('question_manager')
    output_file = tmp_path / "sa_questions.json"
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'generate-sa-questions', '--output', str(output_file)])
    question_manager_mod.main()

    captured = capsys.readouterr()
    assert f"Wrote 3 questions to {output_file}" in captured.out
    assert output_file.exists()
    content = output_file.read_text()
    assert '"id": "service_accounts::0"' in content
    assert '"id": "service_accounts::2"' in content


@pytest.fixture
def mock_ai_generator(monkeypatch):
    """Mocks the AIQuestionGenerator."""
    class MockGenerator:
        def __init__(self, *args, **kwargs):
            pass
        def generate_questions(self, *args, **kwargs):
            return [
                {
                    "id": "ai_q1",
                    "prompt": "AI generated question",
                    "response": "some response",
                    "validation_steps": [],
                    "validator": {},
                    "subject": "Mocked",
                    "category": "Command",
                }
            ]
        def generate_question(self, *args, **kwargs):
            return self.generate_questions(None)[0]

    monkeypatch.setattr('kubelingo.modules.question_generator.AIQuestionGenerator', MockGenerator)
    return MockGenerator


def test_generate_ai_questions_command(tmp_path, mock_ai_generator, capsys, monkeypatch):
    """Tests the generate-ai-questions subcommand."""
    question_manager_mod = load_script('question_manager')
    db_path = tmp_path / "ai_gen_test.db"

    # Run command
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'generate-ai-questions', 'TestSubject', '--db-path', str(db_path)])
    question_manager_mod.main()

    captured = capsys.readouterr()
    assert "Generating 1 AI questions for subject 'TestSubject'..." in captured.out
    assert "Added 1 new questions to the database." in captured.out

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM questions WHERE id = 'ai_q1'")
    assert cursor.fetchone()[0] == 1
    conn.close()


def test_extract_pdf_ai_command(tmp_path, mock_ai_generator, capsys, monkeypatch):
    """Tests the extract-pdf-ai subcommand."""
    import subprocess
    question_manager_mod = load_script('question_manager')
    pdf_file = tmp_path / "test.pdf"
    pdf_file.touch()
    db_path = tmp_path / "pdf_test.db"

    def mock_get_db_connection():
        conn = sqlite3.connect(db_path)
        question_manager_mod.init_db(conn=conn)
        return conn
    monkeypatch.setattr(question_manager_mod, 'get_db_connection', mock_get_db_connection)

    class MockCompletedProcess:
        def __init__(self, stdout="", stderr="", returncode=0): self.stdout, self.stderr, self.returncode = stdout, stderr, returncode
    monkeypatch.setattr(question_manager_mod.subprocess, 'run', lambda *a, **k: MockCompletedProcess(stdout='pdf text'))

    monkeypatch.setenv("OPENAI_API_KEY", "test_key")

    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'extract-pdf-ai', str(pdf_file), '-n', '1'])
    question_manager_mod.main()

    captured = capsys.readouterr()
    assert "Added question ai_q1" in captured.out

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM questions WHERE id = 'ai_q1'")
    assert cursor.fetchone()[0] == 1
    conn.close()


def test_enrich_unseen_command(tmp_path, mock_ai_generator, capsys, monkeypatch):
    """Tests the enrich-unseen subcommand."""
    import json
    import yaml
    question_manager_mod = load_script('question_manager')
    db_path = tmp_path / "unseen_test.db"
    source_json_file = tmp_path / "source_questions.json"
    output_yaml_file = tmp_path / "new_questions.yaml"

    conn = sqlite3.connect(db_path)
    question_manager_mod.init_db(conn=conn)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO questions (id, prompt, source_file) VALUES (?, ?, ?)", ('q1', 'seen prompt', 'f.yaml'))
    conn.commit()
    conn.close()

    monkeypatch.setattr(question_manager_mod, 'get_db_connection', lambda: sqlite3.connect(db_path))

    source_data = [{'prompt': 'seen prompt'}, {'prompt': 'unseen prompt'}]
    source_json_file.write_text(json.dumps(source_data))

    monkeypatch.setenv("OPENAI_API_KEY", "test_key")

    monkeypatch.setattr(sys, 'argv', [
        'question_manager.py', 'enrich-unseen',
        '--source-file', str(source_json_file),
        '--output-file', str(output_yaml_file),
        '--num-questions', '1'
    ])
    question_manager_mod.main()

    captured = capsys.readouterr()
    assert "Found 1 unseen questions" in captured.out
    assert "Generating question for prompt: \"unseen prompt\"" in captured.out
    assert "SUCCESS: Successfully generated 1 new questions" in captured.out

    assert output_yaml_file.exists()
    with open(output_yaml_file, 'r') as f:
        data = yaml.safe_load(f)
    assert len(data) == 1
    assert data[0]['id'] == 'ai_q1'


def test_categorize_text_command(capsys, monkeypatch):
    """Tests the categorize-text subcommand."""
    question_manager_mod = load_script('question_manager')

    def mock_infer(prompt, response):
        return {"exercise_category": "command", "subject_matter": "Test Subject"}
    
    monkeypatch.setattr(question_manager_mod, '_aicat_infer_categories_from_text', mock_infer)
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'categorize-text', '--prompt', 'some prompt'])
    question_manager_mod.main()

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result['exercise_category'] == 'command'
    assert result['subject_matter'] == 'Test Subject'


def test_suggest_citations_command(tmp_path, capsys, monkeypatch):
    """Tests the suggest-citations subcommand."""
    question_manager_mod = load_script('question_manager')

    # Create dummy JSON file in a directory
    json_dir = tmp_path / "questions_json"
    json_dir.mkdir()
    json_file = json_dir / "test_questions.json"
    questions = [
        {"prompt": "How to get namespaces?", "response": "kubectl get ns"},
        {"prompt": "How to do something else?", "response": "some other command"}
    ]
    json_file.write_text(json.dumps(questions))

    # Run suggest-citations command on the directory
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'suggest-citations', str(json_dir)])
    question_manager_mod.main()

    captured = capsys.readouterr()
    assert "Suggest citation: https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#get" in captured.out
    # Check that the "no citation" message is not printed for the file since one was found
    assert "No citations found in this file" not in captured.out

    # Test for no citation found in a different directory
    no_match_dir = tmp_path / "no_match_dir"
    no_match_dir.mkdir()
    no_match_file = no_match_dir / "no_match.json"
    no_match_file.write_text(json.dumps([{"prompt": "foo", "response": "bar"}]))
    monkeypatch.setattr(sys, 'argv', ['question_manager.py', 'suggest-citations', str(no_match_dir)])
    question_manager_mod.main()
    captured_no_match = capsys.readouterr()
    assert "No citations found in this file" in captured_no_match.out
