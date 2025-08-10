"""
Loader for quiz questions stored in the SQLite database.
"""
import sqlite3
from typing import List, Dict, Any, Optional
from kubelingo.modules.base_loader import BaseLoader
from kubelingo.question import Question, ValidationStep
from kubelingo.database import get_db_connection, _row_to_question_dict

class DBLoader(BaseLoader):
    """Discovers and loads questions directly from the local SQLite database."""

    def discover(self) -> List[str]:
        """Return a list of distinct source_file entries in the questions DB."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT source_file FROM questions")
        rows = cursor.fetchall()
        conn.close()
        return [row['source_file'] for row in rows]

    def load_file(self, source_file: str) -> List[Question]:
        """Load all questions with the given source_file from the database."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE source_file = ?", (source_file,))
        rows = cursor.fetchall()
        conn.close()
        questions: List[Question] = []
        for row in rows:
            qd = _row_to_question_dict(row)
            # Deserialize validation steps
            steps: List[ValidationStep] = []
            for v in qd.get('validation_steps', []):
                steps.append(ValidationStep(cmd=v.get('cmd', ''), matcher=v.get('matcher', {})))
            # Determine question type from DB column 'question_type' or fallback to legacy 'type'
            qtype = qd.get('question_type') or qd.get('type') or 'command'
            question = Question(
                id=qd['id'],
                prompt=qd.get('prompt', ''),
                type=qtype,
                pre_shell_cmds=qd.get('pre_shell_cmds', []),
                initial_files=qd.get('initial_files', {}),
                validation_steps=steps,
                explanation=qd.get('explanation'),
                categories=qd.get('categories', []),
                difficulty=qd.get('difficulty'),
                review=qd.get('review', False),
                metadata=qd.get('metadata', {}),
            )
            questions.append(question)
        return questions