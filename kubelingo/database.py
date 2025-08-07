import sqlite3
import json
from typing import Dict, Any, List, Optional
from kubelingo.utils.config import DATABASE_FILE


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the database and creates/updates the questions table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            prompt TEXT NOT NULL,
            response TEXT,
            category TEXT,
            source TEXT,
            validation_steps TEXT,
            validator TEXT,
            source_file TEXT NOT NULL
        )
    """)
    # Add 'review' column if it doesn't exist for backward compatibility
    try:
        cursor.execute("ALTER TABLE questions ADD COLUMN review BOOLEAN NOT NULL DEFAULT 0")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            raise
    conn.commit()
    conn.close()


def add_question(
    id: str,
    prompt: str,
    source_file: str,
    response: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    validation_steps: Optional[List[Dict[str, Any]]] = None,
    validator: Optional[Dict[str, Any]] = None,
    review: bool = False
):
    """Adds or replaces a question in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Serialize complex fields to JSON strings
    validation_steps_json = json.dumps(validation_steps) if validation_steps is not None else None
    validator_json = json.dumps(validator) if validator is not None else None

    cursor.execute("""
        INSERT OR REPLACE INTO questions (id, prompt, response, category, source, validation_steps, validator, source_file, review)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        id,
        prompt,
        response,
        category,
        source,
        validation_steps_json,
        validator_json,
        source_file,
        review
    ))
    conn.commit()
    conn.close()


def _row_to_question_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Converts a database row into a question dictionary, deserializing JSON fields."""
    q_dict = dict(row)
    if q_dict.get('validation_steps'):
        try:
            q_dict['validation_steps'] = json.loads(q_dict['validation_steps'])
        except (json.JSONDecodeError, TypeError):
            q_dict['validation_steps'] = []
    if q_dict.get('validator'):
        try:
            q_dict['validator'] = json.loads(q_dict['validator'])
        except (json.JSONDecodeError, TypeError):
            q_dict['validator'] = {}
    # Ensure review is a boolean
    q_dict['review'] = bool(q_dict.get('review'))
    return q_dict


def get_questions_by_source_file(source_file: str) -> List[Dict[str, Any]]:
    """Fetches all questions from a given source file."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE source_file = ?", (source_file,))
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_question_dict(row) for row in rows]


def get_flagged_questions() -> List[Dict[str, Any]]:
    """Fetches all questions flagged for review."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE review = 1")
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_question_dict(row) for row in rows]


def update_review_status(question_id: str, review: bool):
    """Updates the review status of a question in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE questions SET review = ? WHERE id = ?", (review, question_id))
    conn.commit()
    conn.close()
