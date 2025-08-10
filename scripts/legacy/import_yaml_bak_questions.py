#!/usr/bin/env python3
"""
Import all YAML-backed quiz questions into the live Kubelingo database,
then snapshot the updated database into the project backup folder.

Usage:
    python3 scripts/import_yaml_bak_questions.py
"""
import os
import sys
import shutil
from pathlib import Path

# Ensure project root in path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from kubelingo.database import init_db, add_question
from kubelingo.modules.yaml_loader import YAMLLoader
import kubelingo.utils.config as cfg

def main():
    # Initialize or migrate the live database
    init_db()

    # Directory containing backup YAML quizzes
    yaml_bak_dir = PROJECT_ROOT / 'question-data' / 'yaml-bak'
    if not yaml_bak_dir.is_dir():
        print(f"Backup YAML directory not found: {yaml_bak_dir}")
        return

    loader = YAMLLoader()
    total = 0
    # Process .yaml and .yml files
    for pattern in ('*.yaml', '*.yml'):
        for path in sorted(yaml_bak_dir.glob(pattern)):
            print(f"Importing questions from: {path.name}")
            try:
                questions = loader.load_file(str(path))
            except Exception as e:
                print(f"  Failed to load {path.name}: {e}")
                continue
            for q in questions:
                steps = [ {'cmd': s.cmd, 'matcher': s.matcher} for s in q.validation_steps ]
                validator = None
                expected = q.metadata.get('correct_yaml')
                if expected:
                    validator = {'type': 'yaml', 'expected': expected}
                try:
                    add_question(
                        id=q.id,
                        prompt=q.prompt,
                        source_file=path.name,
                        response=q.response,
                        category=(q.categories[0] if q.categories else q.category),
                        source='backup',
                        validation_steps=steps,
                        validator=validator,
                    )
                    total += 1
                except Exception as e:
                    print(f"  Could not add {q.id}: {e}")
    print(f"Imported {total} questions from YAML backup into the DB.")

    # Snapshot the live DB into the project backup
    try:
        shutil.copy2(cfg.DATABASE_FILE, cfg.BACKUP_DATABASE_FILE)
        print(f"Database backup created at: {cfg.BACKUP_DATABASE_FILE}")
    except Exception as e:
        print(f"Failed to backup database: {e}")

if __name__ == '__main__':
    main()