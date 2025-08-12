import sqlite3
import json
import os
import re
import shutil
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from kubelingo.utils.config import DATABASE_FILE, MASTER_DATABASE_FILE, SUBJECT_MATTER


def get_db_connection(db_path: Optional[str] = None):
    """Establishes a connection to the SQLite database."""
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
            fallback = os.path.join(os.getcwd(), 'kubelingo.db')
            conn = sqlite3.connect(fallback)
        else:
            raise  # Re-raise exception if a specific path was provided and failed
    conn.row_factory = sqlite3.Row
    return conn


def init_db(clear: bool = False, db_path: Optional[str] = None, conn: Optional[sqlite3.Connection] = None):
    """
    Initializes the database and creates/updates tables.
    Can operate on a provided connection or manage its own.
    """
    manage_connection = conn is None
    db_to_use = db_path or DATABASE_FILE

    if manage_connection:
        # If clearing is requested for a file-based DB, remove it to trigger re-seeding.
        if clear and db_to_use != ":memory:" and os.path.exists(db_to_use):
            try:
                os.remove(db_to_use)
            except OSError:
                pass

        # Self-healing for default DB: restore from master if needed.
        needs_restore = False
        if db_path is None:  # Only for the default database
            if not os.path.exists(db_to_use) or os.path.getsize(db_to_use) == 0:
                needs_restore = True
            else:
                try:
                    conn_check = sqlite3.connect(f"file:{db_to_use}?mode=ro", uri=True)
                    cursor_check = conn_check.cursor()
                    cursor_check.execute("SELECT 1 FROM questions LIMIT 1")
                    if cursor_check.fetchone() is None:
                        needs_restore = True
                    conn_check.close()
                except (sqlite3.OperationalError, sqlite3.DatabaseError):
                    needs_restore = True

        if needs_restore:
            from kubelingo.utils.config import MASTER_DATABASE_FILE, SECONDARY_MASTER_DATABASE_FILE
            master_found = os.path.exists(MASTER_DATABASE_FILE) and os.path.getsize(MASTER_DATABASE_FILE) > 0
            secondary_found = os.path.exists(SECONDARY_MASTER_DATABASE_FILE) and os.path.getsize(SECONDARY_MASTER_DATABASE_FILE) > 0

            backup_to_use = MASTER_DATABASE_FILE if master_found else SECONDARY_MASTER_DATABASE_FILE if secondary_found else None

            if backup_to_use:
                try:
                    if os.path.exists(db_to_use):
                        os.remove(db_to_use)
                    db_dir = os.path.dirname(db_to_use)
                    if db_dir:
                        os.makedirs(db_dir, exist_ok=True)
                    shutil.copy2(backup_to_use, db_to_use)
                except Exception:
                    pass

        conn = get_db_connection(db_path=db_to_use)

    # Schema creation and seeding
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS question_categories (id TEXT PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS question_subjects (id TEXT PRIMARY KEY)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            prompt TEXT NOT NULL,
            response TEXT,
            category TEXT,
            subject TEXT,
            source TEXT,
            source_file TEXT NOT NULL,
            validation_steps TEXT,
            validator TEXT,
            review BOOLEAN NOT NULL DEFAULT 0
        )
    """)

    for _cat in ('basic', 'command', 'manifest'):
        cursor.execute("INSERT OR IGNORE INTO question_categories (id) VALUES (?);", (_cat,))
    for _subj in SUBJECT_MATTER:
        cursor.execute("INSERT OR IGNORE INTO question_subjects (id) VALUES (?);", (_subj,))

    conn.commit()

    if manage_connection:
        conn.close()
        # Prune backups only when managing the connection for the default DB.
        if db_path is None:
            prune_db_backups()


def prune_db_backups():
    """Placeholder function to prune old database backups."""
    # Implement logic to remove old database backups if needed.
    # For now, this is a no-op.
    pass


def add_question(
    conn: sqlite3.Connection,
    id: str,
    prompt: str,
    response: str,
    category_id: str,
    subject_id: str,
    source: str,
    source_file: str,
    raw: str,
    review: bool = False
):
    """
    Adds a question to the database.

    Args:
        conn: SQLite connection object.
        id: Unique identifier for the question.
        prompt: The question prompt.
        response: The expected response.
        category_id: The category ID for the question.
        subject_id: The subject ID for the question.
        source: The source of the question.
        source_file: The file where the question originated.
        raw: The raw data for the question.
        review: Whether the question is marked for review.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO questions (id, prompt, response, category_id, subject_id, source, source_file, raw, review)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (id, prompt, response, category_id, subject_id, source, source_file, raw, review)
    )
    conn.commit()


def _row_to_question_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """
    Converts a SQLite row object into a dictionary representing a question.

    Args:
        row: A SQLite row object.

    Returns:
        A dictionary containing the question data.
    """
    return {
        "id": row["id"],
        "prompt": row["prompt"],
        "response": row["response"],
        "category": row["category"],
        "subject": row["subject"],
        "source": row["source"],
        "source_file": row["source_file"],
        "validation_steps": json.loads(row["validation_steps"]) if row["validation_steps"] else [],
        "validator": row["validator"],
        "review": bool(row["review"]),
    }
