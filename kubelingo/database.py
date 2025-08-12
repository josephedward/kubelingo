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


def run_sql_file(conn: sqlite3.Connection, sql_file_path: str):
    """
    Executes the SQL commands in the provided file against the SQLite database.

    Args:
        conn: SQLite connection object.
        sql_file_path: Path to the SQL file to execute.

    Raises:
        FileNotFoundError: If the SQL file does not exist.
        sqlite3.DatabaseError: If there is an error executing the SQL commands.
    """
    if not os.path.exists(sql_file_path):
        raise FileNotFoundError(f"SQL file not found: {sql_file_path}")

    with open(sql_file_path, 'r') as sql_file:
        sql_script = sql_file.read()

    try:
        cursor = conn.cursor()
        cursor.executescript(sql_script)
        conn.commit()
    except sqlite3.DatabaseError as e:
        raise sqlite3.DatabaseError(f"Error executing SQL script: {e}")


def add_question(
    id: str,
    prompt: str,
    source_file: str,
    response: str,
    category: str,
    source: str,
    validator: Dict[str, Any],
):
    """
    Adds a question to the database.

    Args:
        id: Unique identifier for the question.
        prompt: The question prompt.
        source_file: The source file of the question.
        response: The expected response to the question.
        category: The category of the question.
        source: The source of the question (e.g., 'ai').
        validator: A dictionary containing validation information.

    Raises:
        sqlite3.DatabaseError: If there is an error inserting the question.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO questions (
                id, prompt, response, category, source, source_file, validator
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (id, prompt, response, category, source, source_file, json.dumps(validator)),
        )
        conn.commit()
    except sqlite3.DatabaseError as e:
        raise sqlite3.DatabaseError(f"Error adding question to database: {e}")
    finally:
        conn.close()


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
            raw TEXT,
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

# Other functions remain unchanged...
