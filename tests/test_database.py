import pytest
import sqlite3
from pathlib import Path
from kubelingo import database


@pytest.fixture
def temp_db(monkeypatch, tmp_path: Path):
    """Fixture to create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(database, "DATABASE_FILE", db_path)
    database.init_db()
    yield db_path
    db_path.unlink()


def test_init_db(temp_db):
    """Test that init_db creates the database and table."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='questions'")
    assert cursor.fetchone() is not None
    # Check for review column
    cursor.execute("PRAGMA table_info(questions)")
    columns = [info[1] for info in cursor.fetchall()]
    assert "review" in columns
    conn.close()


def test_add_and_get_question(temp_db):
    """Test adding a question and retrieving it."""
    q_id = "test-q-1"
    database.add_question(
        id=q_id,
        prompt="Test prompt",
        source_file="test_source.yaml",
        response="Test response",
        category="testing",
        source="test",
        validation_steps=[{"command": "ls", "output": "file"}],
        validator={"type": "exact"},
        review=False
    )

    questions = database.get_questions_by_source_file("test_source.yaml")
    assert len(questions) == 1
    q = questions[0]
    assert q["id"] == q_id
    assert q["prompt"] == "Test prompt"
    assert q["response"] == "Test response"
    assert q["category"] == "testing"
    assert q["source"] == "test"
    assert q["validation_steps"] == [{"command": "ls", "output": "file"}]
    assert q["validator"] == {"type": "exact"}
    assert q["review"] is False
    assert q["source_file"] == "test_source.yaml"


def test_update_review_status(temp_db):
    """Test updating the review status of a question."""
    q_id = "test-q-2"
    database.add_question(id=q_id, prompt="Review prompt", source_file="review.yaml")

    # Flag for review
    database.update_review_status(q_id, True)
    flagged = database.get_flagged_questions()
    assert len(flagged) == 1
    assert flagged[0]["id"] == q_id
    assert flagged[0]["review"] is True

    # Unflag for review
    database.update_review_status(q_id, False)
    flagged = database.get_flagged_questions()
    assert len(flagged) == 0


def test_get_flagged_questions(temp_db):
    """Test fetching only flagged questions."""
    database.add_question(id="q1", prompt="p1", source_file="f1.yaml", review=True)
    database.add_question(id="q2", prompt="p2", source_file="f1.yaml", review=False)
    database.add_question(id="q3", prompt="p3", source_file="f2.yaml", review=True)

    flagged = database.get_flagged_questions()
    assert len(flagged) == 2
    flagged_ids = {q["id"] for q in flagged}
    assert flagged_ids == {"q1", "q3"}


def test_add_question_handles_nulls(temp_db):
    """Test that add_question works correctly with optional fields as None."""
    q_id = "test-q-null"
    database.add_question(
        id=q_id,
        prompt="Test prompt with nulls",
        source_file="test_source_null.yaml"
    )

    questions = database.get_questions_by_source_file("test_source_null.yaml")
    assert len(questions) == 1
    q = questions[0]
    assert q["id"] == q_id
    assert q["response"] is None
    assert q["category"] is None
    assert q["source"] is None
    assert q["validation_steps"] is None
    assert q["validator"] is None
    assert q["review"] is False


def test_row_to_question_dict_malformed_json(temp_db):
    """Test that _row_to_question_dict handles malformed JSON gracefully."""
    conn = database.get_db_connection()
    conn.execute("""
        INSERT INTO questions (id, prompt, source_file, validation_steps, validator)
        VALUES ('q-malformed', 'p-malformed', 'f-malformed.yaml', '{bad-json}', '{"not": "valid')
    """)
    conn.commit()
    conn.close()

    questions = database.get_questions_by_source_file('f-malformed.yaml')
    assert len(questions) == 1
    q = questions[0]
    assert q['validation_steps'] == []
    assert q['validator'] == {}
