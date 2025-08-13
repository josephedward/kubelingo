import json
import os
import sqlite3
from typing import Dict, List

from kubelingo.database import get_db_connection
from kubelingo.modules.base.loader import BaseLoader
from kubelingo.question import Question


def get_unique_source_files(conn: sqlite3.Connection = None) -> List[str]:
    """Retrieves a list of unique source_file values from the questions table."""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT source_file FROM questions WHERE source_file IS NOT NULL")
        sources = [row[0] for row in cursor.fetchall()]
        return sources
    finally:
        if close_conn and conn:
            conn.close()


def get_questions_by_source_file(source_file: str, conn: sqlite3.Connection = None) -> List[Dict]:
    """Retrieve all questions from the database for a given source_file, as dicts."""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    if conn is None:
        return []

    try:
        base_source_file = os.path.basename(source_file)
        # Use a temporary row_factory to get dicts
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE source_file = ?", (base_source_file,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.row_factory = None  # Reset for other queries
        if close_conn and conn:
            conn.close()


class DBLoader(BaseLoader):
    """Discovers and parses question modules from the SQLite database."""

    def discover(self) -> List[str]:
        """
        Return a list of unique source_file identifiers from the database.
        """
        return get_unique_source_files()

    def load_file(self, path: str) -> List[Question]:
        """
        Loads questions for a given source_file identifier from the database.
        Args:
            path: The source_file identifier to load questions for.
        """
        question_dicts = get_questions_by_source_file(path)
        questions = []
        for q_dict in question_dicts:
            # This logic is based on KubernetesStudyMode._get_questions_by_category_and_subject
            if 'category_id' in q_dict:
                q_dict['schema_category'] = q_dict.pop('category_id')
            if 'subject_id' in q_dict:
                q_dict['subject_matter'] = q_dict.pop('subject_id')
            q_dict.pop('raw', None)  # Not a field in Question dataclass

            # Deserialize JSON fields
            for key in [
                "validation_steps", "validator", "pre_shell_cmds", "initial_files", "answers"
            ]:
                if q_dict.get(key) and isinstance(q_dict[key], str):
                    try:
                        q_dict[key] = json.loads(q_dict[key])
                    except (json.JSONDecodeError, TypeError):
                        q_dict[key] = None # Or some other default
            questions.append(Question(**q_dict))
        return questions
