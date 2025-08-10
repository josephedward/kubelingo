#!/usr/bin/env python3
"""
Migrate all consolidated YAML quizzes into the local SQLite database.
This script clears any existing database and reloads questions from the
built-in YAML files under the QUESTIONS_DIR.
"""
import os
import sys
# Ensure project root is on sys.path so kubelingo package can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kubelingo.database import init_db, get_db_connection, add_question
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.utils.config import QUESTIONS_DIR


def main():
    # Ensure the database schema is fresh
    print("Initializing database (this will clear existing questions)...")
    init_db(clear=True)
    conn = get_db_connection()

    loader = YAMLLoader()
    # Discover YAML quiz files
    files = loader.discover()
    print(f"Discovered {len(files)} YAML files in '{QUESTIONS_DIR}'")

    total_imported = 0
    for path in files:
        filename = os.path.basename(path)
        try:
            questions = loader.load_file(path) or []
        except Exception as e:
            print(f"Failed to load {filename}: {e}")
            continue
        count = len(questions)
        print(f"Importing {count} questions from {filename}")
        for q in questions:
            try:
                # Insert or replace question record
                add_question(
                    id=q.id,
                    prompt=q.prompt,
                    source_file=filename,
                    response=getattr(q, 'response', None),
                    category=(q.categories[0] if q.categories else None),
                    source=getattr(q, 'source', None),
                    validation_steps=[{'cmd': step.cmd, 'matcher': step.matcher} for step in q.validation_steps],
                    validator=getattr(q, 'validator', None),
                    review=q.review,
                    explanation=q.explanation,
                    difficulty=q.difficulty,
                    pre_shell_cmds=q.pre_shell_cmds,
                    initial_files=q.initial_files,
                    question_type=q.type,
                    answers=q.answers,
                    correct_yaml=q.correct_yaml,
                    schema_category=q.schema_category.value,
                    conn=conn
                )
                total_imported += 1
            except Exception as ex:
                print(f"  [ERROR] Could not insert question {q.id}: {ex}")
                continue
    conn.close()
    print(f"Migration complete: {total_imported} questions imported into the database.")


if __name__ == '__main__':
    import sys, traceback
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)