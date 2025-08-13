import logging
import sqlite3
import sys

from kubelingo.database import get_db_connection, init_db, index_all_yaml_questions

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def is_db_empty(conn: sqlite3.Connection) -> bool:
    """Checks if the questions table is empty."""
    try:
        count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        return count == 0
    except sqlite3.OperationalError:
        # Table might not exist yet, which counts as empty.
        return True


def initialize_app():
    """
    Performs necessary startup tasks for the application. It ensures the
    database exists and is populated from the source YAML file if it's empty.
    This avoids slow, destructive re-indexing on every startup.
    """
    conn = None
    try:
        conn = get_db_connection()
        # Ensure schema is up-to-date
        init_db(conn=conn)

        # Only index questions if the database is empty.
        # Forcing a re-index should be a separate, explicit user action.
        if is_db_empty(conn):
            logging.info("Database is empty. Indexing questions from source YAML...")
            # verbose=False to keep startup quiet, no AI categorization on auto-init
            index_all_yaml_questions(conn=conn, verbose=False, force_ai_categorize=False)
            logging.info("Database initialization complete.")

    except sqlite3.OperationalError as e:
        logging.error(f"A database error occurred during initialization: {e}")
        logging.error(
            "This may be due to concurrent processes. Please ensure no other "
            "instances of Kubelingo are running."
        )
        sys.exit(1)
    finally:
        if conn:
            conn.close()


