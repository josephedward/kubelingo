"""
Manages the application's SQLite database connection and operations.

This module is designed based on the principle that YAML files are the single
source of truth for question content. The database only stores metadata about
questions (e.g., source file, review status, content hash) to facilitate quick
lookups and tracking user-specific state.

The DBLoader class was removed from this module to resolve a circular import
dependency and to enforce this metadata-only database design.
"""
import sqlite3
import json
import os
import re
import shutil
import sys
import hashlib
from datetime import datetime
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional
from kubelingo.question import Question, QuestionCategory, QuestionSubject, ValidationStep
from kubelingo.utils.config import DATABASE_FILE, MASTER_DATABASE_FILE
from kubelingo.utils.path_utils import get_project_root, get_all_yaml_files_in_repo


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


def add_question(conn: Optional[sqlite3.Connection] = None, **kwargs: Any):
    """
    Adds or replaces a question in the database using keyword arguments.
    It can operate on a provided connection or manage its own.
    It now tracks creation and update timestamps, and a content hash to detect changes.
    """
    manage_connection = conn is None
    if manage_connection:
        conn = get_db_connection()

    try:
        cursor = conn.cursor()
        q_id = kwargs.get('id')
        if not q_id:
            return  # Cannot insert a question without an ID

        # Preserve created_at on replace by fetching it first.
        cursor.execute("SELECT created_at FROM questions WHERE id = ?", (q_id,))
        result = cursor.fetchone()
        existing_created_at = result[0] if result else None

        cursor.execute("PRAGMA table_info(questions)")
        table_columns = {row[1] for row in cursor.fetchall()}

        q_dict = {k: v for k, v in kwargs.items() if k in table_columns}

        # Set timestamps
        now = datetime.now().isoformat()
        q_dict['updated_at'] = now
        q_dict['created_at'] = existing_created_at or now

        # Convert boolean values to integers for SQLite compatibility.
        for key, value in q_dict.items():
            if isinstance(value, bool):
                q_dict[key] = int(value)

        columns = ', '.join(q_dict.keys())
        placeholders = ', '.join('?' * len(q_dict))
        sql = f"INSERT OR REPLACE INTO questions ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, tuple(q_dict.values()))

        if manage_connection:
            conn.commit()
    finally:
        if manage_connection and conn:
            conn.close()


def get_flagged_questions(conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Fetches all questions flagged for review from the database."""
    manage_connection = conn is None
    if manage_connection:
        conn = get_db_connection()

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE review = 1")
        questions = [dict(row) for row in cursor.fetchall()]
        return questions
    finally:
        if manage_connection and conn:
            conn.close()


def get_question_counts_by_category(conn: Optional[sqlite3.Connection] = None) -> Dict[str, int]:
    """Fetches question counts for each category from the live database."""
    manage_connection = conn is None
    if manage_connection:
        conn = get_db_connection()

    # Initialize counts for all categories to 0
    counts = {cat.value: 0 for cat in QuestionCategory}
    try:
        # This query will get the count of questions for each category_id.
        cursor = conn.cursor()
        cursor.execute("SELECT category_id, COUNT(*) FROM questions GROUP BY category_id")
        rows = cursor.fetchall()
        for row in rows:
            category, count = row
            if category and category in counts:
                counts[category] = count
    finally:
        if manage_connection and conn:
            conn.close()
    return counts


def get_all_questions(conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Fetches all questions from the database and returns them as a list of dicts."""
    manage_connection = conn is None
    if manage_connection:
        conn = get_db_connection()

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions")
        questions = [dict(row) for row in cursor.fetchall()]
        return questions
    finally:
        if manage_connection and conn:
            conn.close()


def _get_file_hash(file_path: Path) -> str:
    """
    Calculates the SHA256 hash of a file's content.

    Args:
        file_path: Path to the file.

    Returns:
        A string representing the SHA256 hash of the file's content.
    """
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            sha256.update(block)
    return sha256.hexdigest()


def index_yaml_files(files: List[Path], conn: sqlite3.Connection, verbose: bool = True):
    """
    Indexes questions from a list of YAML files into the database,
    skipping files that have not changed since the last index.
    """
    try:
        import yaml
        from tqdm import tqdm
    except ImportError:
        if verbose:
            print("Required packages (PyYAML, tqdm) not found. Please install them.", file=sys.stderr)
        return

    cursor = conn.cursor()
    project_root = get_project_root()
    indexed_count = 0
    skipped_count = 0

    file_iterator = tqdm(files, desc="Indexing YAML files") if verbose else files

    for file_path in file_iterator:
        try:
            file_hash = _get_file_hash(file_path)
            rel_path = str(file_path.relative_to(project_root))

            cursor.execute("SELECT content_hash FROM indexed_files WHERE file_path = ?", (rel_path,))
            result = cursor.fetchone()

            if result and result[0] == file_hash:
                skipped_count += 1
                continue  # Skip file if hash is unchanged

            # File is new or has changed, so re-index it.
            # First, remove any existing questions from this file.
            cursor.execute("DELETE FROM questions WHERE source_file = ?", (rel_path,))

            with file_path.open('r', encoding='utf-8') as f:
                data_docs = yaml.safe_load_all(f)
                questions_to_add = []
                for data in data_docs:
                    if not data: continue
                    if isinstance(data, dict) and 'questions' in data:
                        questions_to_add.extend(data['questions'])
                    elif isinstance(data, list):
                        questions_to_add.extend(data)
                    elif isinstance(data, dict) and ('id' in data or 'prompt' in data):
                        questions_to_add.append(data)

            for q_dict in questions_to_add:
                if 'id' not in q_dict or 'prompt' not in q_dict: continue

                q_dict['source_file'] = rel_path
                q_obj = Question(**q_dict)

                # Calculate content hash from a stable representation of the question data.
                stable_repr = json.dumps(q_dict, sort_keys=True, default=str)
                content_hash = hashlib.sha256(stable_repr.encode('utf-8')).hexdigest()

                # Instead of direct insert, use add_question to handle metadata.
                db_dict = {
                    'id': q_obj.id,
                    'source_file': q_obj.source_file,
                    'category_id': q_obj.schema_category.value if q_obj.schema_category else None,
                    'subject_id': q_obj.subject_matter.value if q_obj.subject_matter else None,
                    'review': getattr(q_obj, 'review', False),
                    'triage': getattr(q_obj, 'triage', False),
                    'content_hash': content_hash,
                }
                add_question(conn, **db_dict)

            # Update indexed_files table
            cursor.execute("""
                INSERT OR REPLACE INTO indexed_files (file_path, content_hash, last_indexed)
                VALUES (?, ?, ?)
            """, (rel_path, file_hash, datetime.now()))
            indexed_count += 1

        except (yaml.YAMLError, IOError, Exception) as e:
            if verbose:
                tqdm.write(f"Error processing {file_path}: {e}", file=sys.stderr)

    conn.commit()
    if verbose:
        print(f"\nIndexing complete. Indexed: {indexed_count}, Skipped (unchanged): {skipped_count}")


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

        conn = get_db_connection(db_path=db_to_use)

    # Schema creation and seeding
    cursor = conn.cursor()

    # --- Simple schema migration ---
    # In-place rename 'schema_category' to 'category_id' if an old DB schema is detected.
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='questions'")
    if cursor.fetchone():
        # Table exists, check columns
        cursor.execute("PRAGMA table_info(questions)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'category_id' not in columns and 'schema_category' in columns:
            cursor.execute("ALTER TABLE questions RENAME COLUMN schema_category TO category_id")

    cursor.execute("CREATE TABLE IF NOT EXISTS question_categories (id TEXT PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS question_subjects (id TEXT PRIMARY KEY)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            source_file TEXT NOT NULL,
            category_id TEXT,
            subject_id TEXT,
            review BOOLEAN NOT NULL DEFAULT 0,
            triage BOOLEAN NOT NULL DEFAULT 0,
            content_hash TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS indexed_files (
            file_path TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            last_indexed TIMESTAMP NOT NULL
        )
    """)

    for category in QuestionCategory:
        cursor.execute("INSERT OR IGNORE INTO question_categories (id) VALUES (?);", (category.value,))
    for subject in QuestionSubject:
        cursor.execute("INSERT OR IGNORE INTO question_subjects (id) VALUES (?);", (subject.value,))

    conn.commit()

    if manage_connection:
        conn.close()


