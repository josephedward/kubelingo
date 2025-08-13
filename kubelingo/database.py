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
from kubelingo.question import Question
from kubelingo.utils.config import DATABASE_FILE, MASTER_DATABASE_FILE, SUBJECT_MATTER
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
    """
    manage_connection = conn is None
    if manage_connection:
        conn = get_db_connection()

    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(questions)")
        table_columns = {row[1] for row in cursor.fetchall()}

        q_dict = {k: v for k, v in kwargs.items() if k in table_columns}

        for key, value in q_dict.items():
            if isinstance(value, (dict, list)):
                q_dict[key] = json.dumps(value)
            elif is_dataclass(value):
                q_dict[key] = json.dumps(asdict(value))
            elif isinstance(value, bool):
                q_dict[key] = int(value)

        if 'id' not in q_dict:
            return  # Cannot insert a question without an ID

        columns = ', '.join(q_dict.keys())
        placeholders = ', '.join('?' * len(q_dict))
        sql = f"INSERT OR REPLACE INTO questions ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, tuple(q_dict.values()))

        if manage_connection:
            conn.commit()
    finally:
        if manage_connection and conn:
            conn.close()


def get_questions_for_cli() -> List[Dict[str, Any]]:
    """
    Retrieves all questions from the database for display in the CLI.

    Returns:
        A list of dictionaries representing the questions.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, prompt, category, subject FROM questions ORDER BY id")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_questions_by_subject_matter(subject: str) -> List[Dict[str, Any]]:
    """
    Retrieves questions from the database filtered by subject matter.

    Args:
        subject: The subject matter to filter questions by.

    Returns:
        A list of dictionaries representing the questions.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE subject = ?", (subject,))
        rows = cursor.fetchall()
        return [_row_to_question_dict(row) for row in rows]
    finally:
        conn.close()


def get_question_counts_by_schema_and_subject(schema: str, subject: str) -> int:
    """
    Retrieves the count of questions filtered by schema and subject.

    Args:
        schema: The schema to filter questions by.
        subject: The subject matter to filter questions by.

    Returns:
        The count of questions matching the criteria.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM questions WHERE category = ? AND subject = ?",
            (schema, subject),
        )
        return cursor.fetchone()[0]
    finally:
        conn.close()


def get_all_questions(conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Fetches all questions from the database."""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions")
        rows = cursor.fetchall()
        questions = [_row_to_question_dict(row) for row in rows]
    finally:
        if close_conn:
            conn.close()

    return questions


def get_all_subjects(conn: Optional[sqlite3.Connection] = None) -> List[str]:
    """Fetches all distinct, non-empty subjects from the questions table."""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT subject FROM questions WHERE subject IS NOT NULL AND subject != '' ORDER BY subject")
        rows = cursor.fetchall()
        subjects = [row[0] for row in rows]
    finally:
        if close_conn:
            conn.close()

    return subjects


def get_flagged_questions() -> List[Dict[str, Any]]:
    """
    Retrieves questions that are flagged for review.

    Returns:
        A list of dictionaries representing the flagged questions.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE review = 1")
        rows = cursor.fetchall()
        return [_row_to_question_dict(row) for row in rows]
    finally:
        conn.close()


def update_review_status(question_id: str, review_status: bool):
    """
    Updates the review status of a question.

    Args:
        question_id: The ID of the question to update.
        review_status: The new review status (True or False).
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE questions SET review = ? WHERE id = ?",
            (int(review_status), question_id),
        )
        conn.commit()
    finally:
        conn.close()


def _get_file_hash(file_path: Path) -> str:
    """Computes the SHA256 hash of a file's content."""
    h = hashlib.sha256()
    with file_path.open('rb') as f:
        h.update(f.read())
    return h.hexdigest()


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
                validation_steps_for_db = [step.__dict__ for step in q_obj.validation_steps]

                cursor.execute("""
                    INSERT OR REPLACE INTO questions (id, prompt, source_file, response, category, subject, source, raw, validation_steps, validator, review)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    q_obj.id, q_obj.prompt, q_obj.source_file,
                    json.dumps(q_obj.response) if q_obj.response is not None else None,
                    q_obj.category,
                    q_obj.subject.value if q_obj.subject else None,
                    'yaml_import', json.dumps(q_dict),
                    json.dumps(validation_steps_for_db),
                    json.dumps(q_obj.validator) if q_obj.validator else None,
                    getattr(q_obj, 'review', False)
                ))

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS indexed_files (
            file_path TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            last_indexed TIMESTAMP NOT NULL
        )
    """)

    for _cat in ('basic', 'command', 'manifest'):
        cursor.execute("INSERT OR IGNORE INTO question_categories (id) VALUES (?);", (_cat,))
    for _subj in SUBJECT_MATTER:
        cursor.execute("INSERT OR IGNORE INTO question_subjects (id) VALUES (?);", (_subj,))

    conn.commit()

    # If the database is empty, try to populate it from YAML files.
    cursor.execute("SELECT COUNT(*) FROM questions")
    if cursor.fetchone()[0] == 0:
        try:
            from kubelingo.utils.path_utils import get_all_yaml_files_in_repo
            files = get_all_yaml_files_in_repo()
            if files:
                index_yaml_files(files, conn, verbose=False)
        except (ImportError, Exception):
            # Silently fail if dependencies are missing or an error occurs.
            # The user can run the build-db script manually.
            pass

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


def _row_to_question_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """
    Converts a database row into a dictionary representation of a question,
    deserializing JSON fields and casting boolean values.
    """
    if not row:
        return {}
    q_dict = dict(row)
    # Fields that are stored as JSON strings in the DB
    for key in ['validation_steps', 'answers', 'tags', 'links', 'validator', 'response']:
        if key in q_dict and q_dict[key] and isinstance(q_dict[key], str):
            try:
                q_dict[key] = json.loads(q_dict[key])
            except json.JSONDecodeError:
                # Keep as string if not valid JSON
                pass
    if 'review' in q_dict and q_dict['review'] is not None:
        q_dict['review'] = bool(q_dict['review'])
    return q_dict
