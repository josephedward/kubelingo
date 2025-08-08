import sqlite3
import json
import os
import shutil
from typing import Dict, Any, List, Optional
from kubelingo.utils.config import DATABASE_FILE, BACKUP_DATABASE_FILE


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    # Ensure the database directory exists
    db_dir = os.path.dirname(DATABASE_FILE)
    if db_dir:
        try:
            os.makedirs(db_dir, exist_ok=True)
        except Exception:
            pass

    # Seed database from backup if needed
    seed_needed = False
    if not os.path.exists(DATABASE_FILE):
        seed_needed = True
    else:
        try:
            temp_conn = sqlite3.connect(DATABASE_FILE)
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute("SELECT COUNT(*) FROM questions")
            count = temp_cursor.fetchone()[0]
            temp_conn.close()
            if count == 0:
                seed_needed = True
        except Exception:
            seed_needed = True
    if seed_needed and os.path.exists(BACKUP_DATABASE_FILE):
        try:
            shutil.copyfile(BACKUP_DATABASE_FILE, DATABASE_FILE)
        except Exception:
            pass

    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(clear: bool = False):
    """Initializes the database and creates/updates the questions table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if clear:
        cursor.execute("DROP TABLE IF EXISTS questions")
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
    # Add 'explanation' column if it doesn't exist for backward compatibility
    try:
        cursor.execute("ALTER TABLE questions ADD COLUMN explanation TEXT")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            raise
    # Add other columns from Question model for compatibility
    for col_name in ["difficulty", "pre_shell_cmds", "initial_files", "question_type"]:
        try:
            cursor.execute(f"ALTER TABLE questions ADD COLUMN {col_name} TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise
    conn.commit()
    conn.close()


def add_question(
    conn: sqlite3.Connection,
    id: str,
    prompt: str,
    source_file: str,
    response: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    validation_steps: Optional[List[Dict[str, Any]]] = None,
    validator: Optional[Dict[str, Any]] = None,
    review: bool = False,
    explanation: Optional[str] = None,
    difficulty: Optional[str] = None,
    pre_shell_cmds: Optional[List[str]] = None,
    initial_files: Optional[Dict[str, str]] = None,
    question_type: Optional[str] = None
):
    """Adds or replaces a question in the database."""
    cursor = conn.cursor()

    # Serialize complex fields to JSON strings
    validation_steps_json = json.dumps(validation_steps) if validation_steps is not None else None
    validator_json = json.dumps(validator) if validator is not None else None
    pre_shell_cmds_json = json.dumps(pre_shell_cmds) if pre_shell_cmds is not None else None
    initial_files_json = json.dumps(initial_files) if initial_files is not None else None

    cursor.execute("""
        INSERT OR REPLACE INTO questions (id, prompt, response, category, source, validation_steps, validator, source_file, review, explanation, difficulty, pre_shell_cmds, initial_files, question_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        id,
        prompt,
        response,
        category,
        source,
        validation_steps_json,
        validator_json,
        source_file,
        review,
        explanation,
        difficulty,
        pre_shell_cmds_json,
        initial_files_json,
        question_type
    ))


def _row_to_question_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Converts a database row into a question dictionary, deserializing JSON fields."""
    q_dict = dict(row)
    # Deserialize validation_steps JSON into list, default to empty list
    if q_dict.get('validation_steps'):
        try:
            q_dict['validation_steps'] = json.loads(q_dict['validation_steps'])
        except (json.JSONDecodeError, TypeError):
            q_dict['validation_steps'] = []
    else:
        q_dict['validation_steps'] = []
    if q_dict.get('validator'):
        try:
            q_dict['validator'] = json.loads(q_dict['validator'])
        except (json.JSONDecodeError, TypeError):
            q_dict['validator'] = {}
    # Ensure review is a boolean
    q_dict['review'] = bool(q_dict.get('review'))
    # Deserialize pre_shell_cmds JSON into Python list
    pre_cmds = q_dict.get('pre_shell_cmds')
    if pre_cmds:
        try:
            q_dict['pre_shell_cmds'] = json.loads(pre_cmds)
        except (json.JSONDecodeError, TypeError):
            q_dict['pre_shell_cmds'] = []
    else:
        q_dict['pre_shell_cmds'] = []
    # Deserialize initial_files JSON into Python dict
    init_files = q_dict.get('initial_files')
    if init_files:
        try:
            q_dict['initial_files'] = json.loads(init_files)
        except (json.JSONDecodeError, TypeError):
            q_dict['initial_files'] = {}
    else:
        q_dict['initial_files'] = {}
    # Map question_type column to 'type' key for compatibility
    q_dict['type'] = q_dict.get('question_type') or q_dict.get('type')
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
