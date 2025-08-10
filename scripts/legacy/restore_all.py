#!/usr/bin/env python3
"""
Kubelingo Full Restore Helper
Use this script to fully restore your Kubelingo questions:
 1) Restore the questions DB from backup
 2) Restore YAML quizzes from backup directories
 3) Run migration into the DB for YAML and JSON quizzes
"""
import os
import sys

def main():
    # Ensure local package is on PYTHONPATH
    here = os.path.abspath(os.path.dirname(__file__))
    repo = os.path.abspath(os.path.join(here, '..'))
    sys.path.insert(0, repo)
    from kubelingo.cli import restore_db
    import shutil
    # Determine repository paths
    repo = os.path.abspath(os.path.join(here, '..'))
    # Paths for YAML restore
    YAML_SRC1 = os.path.join(repo, 'question-data', 'yaml-bak')
    YAML_SRC2 = os.path.join(repo, 'question-data', 'manifests')
    YAML_DST = os.path.join(repo, 'question-data', 'yaml')

    print("\n=== Kubelingo Full Restore ===")

    # 1) Restore DB
    print("Restoring primary database...")
    restore_db()

    # 2) Restore YAML quizzes from backups
    print("Restoring YAML quiz files from backup directories...")
    os.makedirs(YAML_DST, exist_ok=True)
    for src_dir in (YAML_SRC1, YAML_SRC2):
        if os.path.isdir(src_dir):
            for fname in os.listdir(src_dir):
                if fname.lower().endswith(('.yaml', '.yml')):
                    src = os.path.join(src_dir, fname)
                    dst = os.path.join(YAML_DST, fname)
                    shutil.copy2(src, dst)

    # 3) Migrate YAML quizzes into database manually
    print("Migrating YAML quizzes into database...")
    from kubelingo.modules.yaml_loader import YAMLLoader
    from kubelingo.database import add_question, get_db_connection
    from dataclasses import asdict
    loader = YAMLLoader()
    yaml_files = loader.discover()
    conn = get_db_connection()
    for file_path in yaml_files:
        try:
            questions = loader.load_file(file_path)
            for q in questions:
                q_dict = asdict(q)
                # Rename 'type' to 'question_type' for DB import
                if 'type' in q_dict:
                    q_dict['question_type'] = q_dict.pop('type')
                # Rename 'type' to 'question_type' for DB import
                if 'type' in q_dict:
                    q_dict['question_type'] = q_dict.pop('type')
                add_question(conn, **q_dict)
        except Exception as e:
            print(f"Failed to import YAML file {file_path}: {e}")
    conn.commit()
    conn.close()

    # 4) Import JSON quizzes into database manually
    print("Importing JSON quizzes into database...")
    from kubelingo.modules.json_loader import JSONLoader
    from kubelingo.database import add_question, get_db_connection
    loader = JSONLoader()
    json_files = loader.discover()
    conn = get_db_connection()
    for file_path in json_files:
        try:
            questions = loader.load_file(file_path)
            for q in questions:
                q_dict = asdict(q)
                add_question(conn, **q_dict)
        except Exception as e:
            print(f"Failed to import JSON file {file_path}: {e}")
    conn.commit()
    conn.close()

    print("=== Full Restore Complete ===\n")

if __name__ == '__main__':
    main()