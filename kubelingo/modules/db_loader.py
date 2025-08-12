"""
Loader for quiz questions stored in the SQLite database.

Rationale for using SQLite over YAML files:
- Performance: Faster lookups and filtering of questions without parsing large
  text files on each run.
- Data Integrity: Enforces unique question IDs and a consistent data structure
  through a schema.
- Querying Power: Allows for complex queries (e.g., by category, review status)
  using standard SQL.
- Centralization: Manages all questions in a single, consolidated data store,
  simplifying backups and maintenance.
"""
import sqlite3
from typing import List, Dict, Any, Optional
from kubelingo.modules.base_loader import BaseLoader
from kubelingo.question import Question, ValidationStep
from kubelingo.database import get_db_connection, _row_to_question_dict
import os

class DBLoader(BaseLoader):
    """Discovers and loads questions directly from the local SQLite database."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initializes the DBLoader.
        :param db_path: Optional path to a specific SQLite database file.
        """
        self.db_path = db_path

    def discover(self) -> List[str]:
        """Return a list of distinct source_file entries in the questions DB."""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT source_file FROM questions")
        rows = cursor.fetchall()
        conn.close()
        return [row['source_file'] for row in rows]

    def load_file(self, source_file: str) -> List[Question]:
        """Load all questions with the given source_file from the database."""
        # Allow passing full paths: match only on basename stored in DB
        key = os.path.basename(source_file)
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE source_file = ?", (key,))
        rows = cursor.fetchall()
        conn.close()
        questions: List[Question] = []
        for row in rows:
            qd = _row_to_question_dict(row)

            # Prioritize loading from 'raw' column for the most complete data.
            raw_data_str = qd.get('raw')
            if raw_data_str:
                try:
                    q_data = json.loads(raw_data_str)
                    if isinstance(q_data, dict):
                        # Hydrate ValidationStep objects from dicts.
                        if 'validation_steps' in q_data and isinstance(q_data['validation_steps'], list):
                            q_data['validation_steps'] = [
                                ValidationStep(**step) for step in q_data['validation_steps'] if isinstance(step, dict)
                            ]
                        # The database 'review' status is authoritative.
                        q_data['review'] = qd.get('review', False)

                        question = Question(**q_data)
                        questions.append(question)
                        continue
                except (json.JSONDecodeError, TypeError):
                    # Fallback to manual construction if 'raw' is malformed.
                    pass

            # Fallback for old data without a 'raw' field or if 'raw' processing fails.
            steps: List[ValidationStep] = []
            validation_steps_data = qd.get('validation_steps', [])
            if isinstance(validation_steps_data, list):
                for v in validation_steps_data:
                    if isinstance(v, dict):
                        steps.append(ValidationStep(cmd=v.get('cmd', ''), matcher=v.get('matcher', {})))

            metadata = qd.get('metadata')
            if not isinstance(metadata, dict):
                metadata = {}

            # Manually construct Question from available DB columns.
            question = Question(
                id=qd.get('id'),
                prompt=qd.get('prompt', ''),
                type=qd.get('type', 'command'),
                validation_steps=steps,
                review=qd.get('review', False),
                categories=qd.get('categories', []),
                difficulty=qd.get('difficulty'),
                explanation=qd.get('explanation'),
                initial_files=qd.get('initial_files', {}),
                pre_shell_cmds=qd.get('pre_shell_cmds', []),
                metadata=metadata,
                subject_matter=qd.get('subject')
            )
            questions.append(question)
        return questions
