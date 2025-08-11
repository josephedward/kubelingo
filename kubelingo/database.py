import sqlite3
import json
import os
import shutil
from dataclasses import asdict, is_dataclass
from typing import Dict, Any, List, Optional
from kubelingo.utils.config import DATABASE_FILE, MASTER_DATABASE_FILE, SUBJECT_MATTER


def get_db_connection(db_path: Optional[str] = None):
    """Establishes a connection to the SQLite database."""
    # Use provided path or fall back to the default application database file.
    db_file = db_path or DATABASE_FILE

    # Ensure the database directory exists
    db_dir = os.path.dirname(db_file)
    if db_dir:
        try:
            os.makedirs(db_dir, exist_ok=True)
        except Exception:
            pass

    # Attempt connection. For default DB, try fallback on error.
    try:
        conn = sqlite3.connect(db_file)
    except Exception:
        if db_path is None:  # Only fallback for the default database
            # Fallback to a local DB in the current working directory
            fallback = os.path.join(os.getcwd(), 'kubelingo.db')
            conn = sqlite3.connect(fallback)
        else:
            raise  # Re-raise exception if a specific path was provided and failed
    conn.row_factory = sqlite3.Row
    return conn


def init_db(clear: bool = False, db_path: Optional[str] = None):
    """Initializes the database and creates/updates the questions table."""
    db_to_use = db_path or DATABASE_FILE

    # If clearing, physically remove the DB file to trigger re-seeding from master.
    # This ensures "clear" means "reset to original state" not "create empty DB".
    if clear and os.path.exists(db_to_use):
        try:
            os.remove(db_to_use)
        except OSError:
            # If removal fails (e.g., permissions), we'll fall back to the old
            # behavior of dropping the table, which is better than nothing.
            pass

    # First-run seeding: if the default user database does not exist, create it from
    # the master backup. This should not run for custom db_paths.
    if db_path is None and not os.path.exists(db_to_use):
        from kubelingo.utils.config import MASTER_DATABASE_FILE, SECONDARY_MASTER_DATABASE_FILE
        master_found = os.path.exists(MASTER_DATABASE_FILE) and os.path.getsize(MASTER_DATABASE_FILE) > 0
        secondary_found = os.path.exists(SECONDARY_MASTER_DATABASE_FILE) and os.path.getsize(SECONDARY_MASTER_DATABASE_FILE) > 0

        backup_to_use = None
        if master_found:
            backup_to_use = MASTER_DATABASE_FILE
        elif secondary_found:
            backup_to_use = SECONDARY_MASTER_DATABASE_FILE

        if backup_to_use:
            try:
                db_dir = os.path.dirname(db_to_use)
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)
                shutil.copy2(backup_to_use, db_to_use)
            except Exception:
                # If seeding fails, continue to create an empty DB.
                # The user can try to restore manually later.
                pass

    conn = get_db_connection(db_path=db_to_use)
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
    for col_name in ["difficulty", "pre_shell_cmds", "initial_files", "question_type", "answers", "correct_yaml"]:
        try:
            cursor.execute(f"ALTER TABLE questions ADD COLUMN {col_name} TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise
    # Add schema_category column for exercise type categorization
    try:
        categories = "('basic', 'command', 'manifest')"
        cursor.execute(f"ALTER TABLE questions ADD COLUMN schema_category TEXT CHECK(schema_category IN {categories})")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            raise
    # Add 'subject_matter' column for question subject matter with CHECK constraint
    try:
        subjects = ', '.join(repr(s) for s in SUBJECT_MATTER)
        cursor.execute(
            f"ALTER TABLE questions ADD COLUMN subject_matter TEXT "
            f"CHECK(subject_matter IN ({subjects}))"
        )
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
    review: bool = False,
    explanation: Optional[str] = None,
    difficulty: Optional[str] = None,
    pre_shell_cmds: Optional[List[str]] = None,
    initial_files: Optional[Dict[str, str]] = None,
    question_type: Optional[str] = None,
    answers: Optional[List[str]] = None,
    correct_yaml: Optional[str] = None,
    schema_category: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    subject_matter: Optional[str] = None,
    conn: sqlite3.Connection = None
):
    """Adds or replaces a question in the database."""
    close_conn = conn is None
    # Open connection if not provided
    if close_conn:
        conn = get_db_connection()
    cursor = conn.cursor()

    # Validate subject matter category if provided
    if subject_matter is not None and subject_matter not in SUBJECT_MATTER:
        raise ValueError(
            f"Invalid subject matter category: {subject_matter!r}. "
            f"Must be one of: {SUBJECT_MATTER}"
        )

    # Serialize complex fields to JSON strings
    validation_steps_json = None
    if validation_steps is not None:
        # Convert list of dataclass objects to list of dicts for JSON serialization
        validation_steps_serializable = [
            asdict(step) if is_dataclass(step) else step for step in validation_steps
        ]
        validation_steps_json = json.dumps(validation_steps_serializable)
    validator_json = json.dumps(validator) if validator is not None else None
    pre_shell_cmds_json = json.dumps(pre_shell_cmds) if pre_shell_cmds is not None else None
    initial_files_json = json.dumps(initial_files) if initial_files is not None else None
    answers_json = json.dumps(answers) if answers is not None else None

    cursor.execute("""
        INSERT OR REPLACE INTO questions (
            id, prompt, response, category, source,
            validation_steps, validator, source_file, review,
            explanation, difficulty, pre_shell_cmds, initial_files,
            question_type, answers, correct_yaml, schema_category, subject_matter
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        question_type,
        answers_json,
        correct_yaml,
        schema_category,
        subject_matter
    ))
    # Commit the insertion to the database
    conn.commit()

    if close_conn:
        conn.close()


def _row_to_question_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Converts a database row into a question dictionary, deserializing JSON fields."""
    q_dict = dict(row)
    # Deserialize validation_steps JSON into list (leave as None if not set)
    vs_raw = q_dict.get('validation_steps')
    if vs_raw is not None:
        try:
            q_dict['validation_steps'] = json.loads(vs_raw)
        except (json.JSONDecodeError, TypeError):
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
    # Deserialize answers JSON into Python list
    answers_data = q_dict.get('answers')
    if answers_data:
        try:
            q_dict['answers'] = json.loads(answers_data)
        except (json.JSONDecodeError, TypeError):
            q_dict['answers'] = []
    else:
        q_dict['answers'] = []
    # Extract correct_yaml column
    q_dict['correct_yaml'] = q_dict.get('correct_yaml')
    # Map question_type column to 'type' key for compatibility
    q_dict['type'] = q_dict.get('question_type') or q_dict.get('type')
    q_dict.pop('question_type', None)
    # Add schema_category if it exists
    q_dict['schema_category'] = q_dict.get('schema_category')
    # Add subject matter if it exists
    q_dict['subject_matter'] = q_dict.get('subject_matter')
    return q_dict


def get_questions_by_source_file(source_file: str, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Fetches all questions from a given source file."""
    close_conn = conn is None
    if close_conn:
        conn = get_db_connection()

    # Allow passing full paths: match only on basename stored in DB
    key = os.path.basename(source_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE source_file = ?", (key,))
    rows = cursor.fetchall()
    if close_conn:
        conn.close()
    return [_row_to_question_dict(row) for row in rows]


def get_flagged_questions(conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Fetches all questions flagged for review."""
    close_conn = conn is None
    if close_conn:
        conn = get_db_connection()

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE review = 1")
    rows = cursor.fetchall()
    if close_conn:
        conn.close()
    return [_row_to_question_dict(row) for row in rows]


def get_all_questions(conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Fetches all questions from the database."""
    close_conn = conn is None
    if close_conn:
        conn = get_db_connection()

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions")
    rows = cursor.fetchall()
    if close_conn:
        conn.close()
    return [_row_to_question_dict(row) for row in rows]


def update_review_status(question_id: str, review: bool, conn: Optional[sqlite3.Connection] = None):
    """Updates the review status of a question in the database."""
    close_conn = conn is None
    if close_conn:
        conn = get_db_connection()

    cursor = conn.cursor()
    cursor.execute("UPDATE questions SET review = ? WHERE id = ?", (review, question_id))
    conn.commit()
    if close_conn:
        conn.close()
