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

    # Self-healing for default DB: if it doesn't exist, is empty, or corrupt,
    # restore it from the master backup. This does not run for custom db_paths.
    needs_restore = False
    if db_path is None:  # Only for the default database
        if not os.path.exists(db_to_use) or os.path.getsize(db_to_use) == 0:
            needs_restore = True
        else:
            try:
                # Check if the DB is usable and has questions. Connect read-only.
                conn_check = sqlite3.connect(f"file:{db_to_use}?mode=ro", uri=True)
                cursor_check = conn_check.cursor()
                cursor_check.execute("SELECT 1 FROM questions LIMIT 1")
                if cursor_check.fetchone() is None:
                    needs_restore = True  # Table is empty, restore.
                conn_check.close()
            except (sqlite3.OperationalError, sqlite3.DatabaseError):
                # This can happen if table 'questions' doesn't exist or DB is corrupt.
                needs_restore = True

    if needs_restore:
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
                # Ensure we can write to the destination by removing the old file first.
                if os.path.exists(db_to_use):
                    os.remove(db_to_use)

                db_dir = os.path.dirname(db_to_use)
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)
                shutil.copy2(backup_to_use, db_to_use)
            except Exception:
                # If seeding fails, continue and let the app create an empty DB.
                # The user can try to restore manually later if needed.
                pass

    conn = get_db_connection(db_path=db_to_use)
    cursor = conn.cursor()
    if clear:
        cursor.execute("DROP TABLE IF EXISTS questions")
    # Core lookup tables for categories and subjects
    cursor.execute("CREATE TABLE IF NOT EXISTS question_categories (\
                      id TEXT PRIMARY KEY) ")
    cursor.execute("CREATE TABLE IF NOT EXISTS question_subjects (\
                      id TEXT PRIMARY KEY) ")
    # Main questions table: lean, with a JSON column for raw data
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            prompt TEXT NOT NULL,
            response TEXT,
            category_id TEXT REFERENCES question_categories(id),
            subject_id  TEXT REFERENCES question_subjects(id),
            source TEXT,
            source_file TEXT NOT NULL,
            review BOOLEAN NOT NULL DEFAULT 0,
            raw TEXT NOT NULL
        )
    """ )
    # Seed default exercise categories
    for _cat in ('basic', 'command', 'manifest'):
        cursor.execute(
            "INSERT OR IGNORE INTO question_categories (id) VALUES (?);",
            (_cat,)
        )
    # Seed default subject tags
    for _subj in [
        'core_workloads', 'pod_design_patterns', 'commands_args_env', 'app_configuration',
        'probes_health', 'resource_management', 'jobs_cronjobs', 'services',
        'ingress_http_routing', 'networking_utilities', 'persistence',
        'observability_troubleshooting', 'labels_annotations_selectors',
        'imperative_declarative', 'image_registry', 'security_basics',
        'serviceaccounts', 'scheduling_hints', 'namespaces_contexts',
        'api_discovery_docs', 'vim', 'kubectl', 'linux'
    ]:
        cursor.execute(
            "INSERT OR IGNORE INTO question_subjects (id) VALUES (?);",
            (_subj,)
        )

    conn.commit()
    conn.close()

    # Prune old database backups to prevent them from accumulating.
    if db_path is None:
        prune_db_backups()


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


    # Ensure category and subject exist in lookup tables
    if category:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO question_categories (id) VALUES (?)", (category,)
            )
        except Exception:
            pass
    if subject_matter:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO question_subjects (id) VALUES (?)", (subject_matter,)
            )
        except Exception:
            pass
    # Serialize raw question dict for document storage
    raw_dict: Dict[str, Any] = {
        'id': id,
        'prompt': prompt,
        'response': response,
        'category': category,
        'subject_matter': subject_matter,
        'source': source,
        'source_file': source_file,
        'review': review,
        'validation_steps': validation_steps,
        'validator': validator,
        'pre_shell_cmds': pre_shell_cmds,
        'initial_files': initial_files,
        'explanation': explanation,
        'difficulty': difficulty,
        'question_type': question_type,
        'answers': answers,
        'correct_yaml': correct_yaml,
        'schema_category': schema_category,
        'metadata': metadata
    }
    raw_json = json.dumps(raw_dict, ensure_ascii=False)
    # Insert into core questions table (trimmed columns + raw JSON)
    cursor.execute(
        "INSERT OR REPLACE INTO questions "
        "(id, prompt, response, category_id, subject_id, source, source_file, review, raw) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            id,
            prompt,
            response,
            category,
            subject_matter,
            source,
            source_file,
            int(bool(review)),
            raw_json
        )
    )
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
    # Deserialize metadata JSON into Python dict
    metadata_data = q_dict.get('metadata')
    if metadata_data:
        try:
            q_dict['metadata'] = json.loads(metadata_data)
        except (json.JSONDecodeError, TypeError):
            q_dict['metadata'] = {}
    else:
        q_dict['metadata'] = {}
    # Extract correct_yaml column
    q_dict['correct_yaml'] = q_dict.get('correct_yaml')
    # Map question_type column to 'type' key for compatibility
    q_dict['type'] = q_dict.get('question_type') or q_dict.get('type')
    q_dict.pop('question_type', None)
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


def get_questions_by_subject_matter(subject_matter: str, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """
    Fetches all questions for a given subject matter by querying the 'subject_matter' column.
    """
    close_conn = conn is None
    if close_conn:
        conn = get_db_connection()

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE subject_matter = ?", (subject_matter,))
    rows = cursor.fetchall()
    if close_conn:
        conn.close()
    return [_row_to_question_dict(row) for row in rows]


def get_question_counts_by_schema_and_subject(conn: Optional[sqlite3.Connection] = None) -> Dict[str, Dict[str, int]]:
    """
    Returns a nested dict: category_id -> { subject_id -> count }
    """
    close_conn = conn is None
    if close_conn:
        conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT category_id, subject_id, COUNT(*)
        FROM questions
        WHERE category_id IS NOT NULL AND subject_id IS NOT NULL
        GROUP BY category_id, subject_id
    """)
    rows = cursor.fetchall()
    if close_conn:
        conn.close()
    counts: Dict[str, Dict[str, int]] = {}
    for cat_id, subj_id, cnt in rows:
        if not cat_id or not subj_id:
            continue
        counts.setdefault(cat_id, {})[subj_id] = cnt
    return counts


def prune_db_backups(keep: int = 10):
    """
    Removes old database backups, keeping only the most recent ones.
    Also removes associated -shm and -wal files.
    """
    try:
        from kubelingo.utils.config import DATABASE_FILE

        db_dir = Path(DATABASE_FILE).parent
        if not db_dir.is_dir():
            return

        # Regex to match backup files like:
        # 20250812_091456_113974.db
        # kubelingo_db_20250812_092509.db
        backup_pattern = re.compile(r"^(?:kubelingo_db_)?\d{8}_\d{6}(?:_\d+)?\.db$")

        backups = [p for p in db_dir.glob('*.db') if backup_pattern.match(p.name)]

        # Sort by filename, which works due to the YYYYMMDD format
        backups.sort(key=lambda p: p.name)

        if len(backups) <= keep:
            return

        to_delete = backups[:-keep]
        for db_file in to_delete:
            try:
                # Delete the main .db file
                db_file.unlink()

                # Delete associated -shm and -wal files
                for suffix in ['-shm', '-wal']:
                    assoc_file = db_dir / (db_file.name + suffix)
                    assoc_file.unlink(missing_ok=True)
            except OSError:
                # Ignore errors (e.g. file in use or permissions)
                pass
    except Exception:
        # If anything goes wrong, just skip pruning. It's not critical.
        pass


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
