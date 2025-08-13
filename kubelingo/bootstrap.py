import logging
import sqlite3
import sys

from kubelingo.database import get_db_connection, init_db, index_all_yaml_questions

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def initialize_app():
    """
    Performs necessary startup tasks for the application, including database
    schema initialization and YAML question indexing. It ensures that all
    database operations at startup are handled through a single connection
    to prevent locking issues.
    """
    conn = None
    try:
        # Use a single connection for all startup operations
        conn = get_db_connection()
        init_db(conn=conn)
        index_all_yaml_questions(conn=conn, verbose=False)
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


