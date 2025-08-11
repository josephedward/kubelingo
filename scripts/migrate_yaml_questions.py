#!/usr/bin/env python3
"""
Migrate all consolidated YAML quizzes into the local SQLite database.
This script preserves any existing questions and merges in new quizzes
from the built-in YAML files under the QUESTIONS_DIR and legacy locations.
"""
import os
import sys
# Ensure project root is on sys.path so kubelingo package can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kubelingo.database import init_db, get_db_connection, add_question
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.utils.config import QUESTIONS_DIR, PROJECT_ROOT


def main():
    # Ensure the database schema is ready; preserve existing questions and merge new ones
    print("Initializing database (preserving existing questions; merging new quizzes)...")
    init_db(clear=False)
    conn = get_db_connection()

    loader = YAMLLoader()
    # Discover YAML quiz files in both consolidated and legacy directories (including manifests)
    from glob import glob
    from kubelingo.utils.config import DATA_DIR
    # Include consolidated quizzes, legacy YAML, manifest-based quizzes from misc/, and any backups
    dirs = [
        QUESTIONS_DIR,
        os.path.join(DATA_DIR, 'yaml'),
        # Manifest-based YAML exercises stored in misc/manifests
        os.path.join(PROJECT_ROOT, 'misc', 'manifests'),
        os.path.join(DATA_DIR, 'yaml-bak'),
    ]
    patterns = ['*.yaml', '*.yml', '*.yaml.bak']
    total_imported = 0
    for quiz_dir in dirs:
        if not os.path.isdir(quiz_dir):
            continue
        print(f"Processing YAML directory: {quiz_dir}")
        for pat in patterns:
            for path in sorted(glob(os.path.join(quiz_dir, pat))):
                filename = os.path.basename(path)
                try:
                    questions = loader.load_file(path) or []
                except Exception as e:
                    print(f"Failed to load {filename}: {e}")
                    continue
                print(f"Importing {len(questions)} questions from {filename}")
                for q in questions:
                    try:
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
                            subject=(q.categories[0] if q.categories else None),
                            metadata=getattr(q, 'metadata', None),
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