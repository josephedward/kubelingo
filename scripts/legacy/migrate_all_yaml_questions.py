#!/usr/bin/env python3
"""
Migrate all YAML-based quiz questions into the Kubelingo SQLite database.

Scans question-data/yaml for .yaml, .yml, and .yaml.bak files,
loads each via YAMLLoader, and persists into the local questions DB.
"""
import os
import sys
from pathlib import Path

# Ensure project root in PYTHONPATH
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from kubelingo.database import init_db, add_question
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.utils.config import DATA_DIR, QUESTIONS_DIR
from dataclasses import asdict

def main():
    # Initialize DB (creates ~/.kubelingo/kubelingo.db)
    # Clear existing DB and initialize (drops and recreates questions table)
    init_db(clear=True)
    loader = YAMLLoader()
    # Scan both primary and backup YAML quiz directories
    # Include both the new questions directory and legacy YAML directories
    dirs = [Path(QUESTIONS_DIR), Path(DATA_DIR) / 'yaml', Path(DATA_DIR) / 'yaml-bak']
    total_added = 0
    for yaml_dir in dirs:
        if not yaml_dir.is_dir():
            continue
        print(f"Processing YAML directory: {yaml_dir}")
        patterns = ['*.yaml', '*.yml', '*.yaml.bak']
        for pat in patterns:
            for path in sorted(yaml_dir.glob(pat)):
                try:
                    questions = loader.load_file(str(path))
                except Exception as e:
                    print(f"Failed to load {path}: {e}")
                    continue
                if not questions:
                    continue
                source_file = path.name
                for q in questions:
                    vs = []
                    for step in getattr(q, 'validation_steps', []):
                        vs.append(asdict(step))
                    validator = None
                    expected = q.metadata.get('correct_yaml') or q.metadata.get('correct_yaml', None)
                    if expected:
                        validator = {'type': 'yaml', 'expected': expected}
                    try:
                        add_question(
                            id=q.id,
                            prompt=q.prompt,
                            source_file=source_file,
                            response=None,
                            category=(q.categories[0] if q.categories else None),
                            source='migration',
                            validation_steps=vs,
                            validator=validator,
                            # Preserve full question schema
                            question_type=getattr(q, 'type', None),
                            answers=getattr(q, 'answers', None),
                            correct_yaml=getattr(q, 'correct_yaml', None),
                            pre_shell_cmds=getattr(q, 'pre_shell_cmds', None),
                            initial_files=getattr(q, 'initial_files', None),
                            explanation=getattr(q, 'explanation', None),
                            difficulty=getattr(q, 'difficulty', None),
                            schema_category=getattr(q.schema_category, 'value', None),
                        )
                        total_added += 1
                    except Exception as e:
                        print(f"Failed to add {q.id} from {source_file}: {e}")
    print(f"Migration complete: {total_added} YAML questions added to database.")

if __name__ == '__main__':
    main()