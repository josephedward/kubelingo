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


def init_db(clear: bool = False, db_path: Optional[str] = None):
    """Initializes the database and creates/updates the questions table."""
    db_to_use = db_path or DATABASE_FILE

    # If clearing is explicitly requested, remove the DB file to trigger re-seeding from master.
    if clear and os.path.exists(db_to_use):
        try:
            os.remove(db_to_use)
        except OSError:
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
                if os.path.exists(db_to_use):
                    os.remove(db_to_use)

                db_dir = os.path.dirname(db_to_use)
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)
                shutil.copy2(backup_to_use, db_to_use)
            except Exception:
                pass

    conn = get_db_connection(db_path=db_to_use)
    cursor = conn.cursor()

    # Create tables if they do not exist, but do not clear existing data
    cursor.execute("CREATE TABLE IF NOT EXISTS question_categories (id TEXT PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS question_subjects (id TEXT PRIMARY KEY)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            prompt TEXT NOT NULL,
            response TEXT,
            category_id TEXT REFERENCES question_categories(id),
            subject_id TEXT REFERENCES question_subjects(id),
            source TEXT,
            source_file TEXT NOT NULL,
            review BOOLEAN NOT NULL DEFAULT 0,
            raw TEXT NOT NULL
        )
    """)

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


# Other functions remain unchanged
