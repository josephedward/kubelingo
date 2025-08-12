#!/usr/bin/env python3
"""
Add UI configuration questions into the Kubelingo SQLite database.

This script loads YAML-editing questions from the backup YAML file under question-data/yaml
and persists them to the local SQLite DB so they are available for the Kubelingo CLI.
"""
import os
import sys

# Ensure project root in path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from kubelingo.database import init_db, add_question
""" Uses manual question definitions to add UI config questions into DB. """
import kubelingo.utils.config as cfg
import kubelingo.database as db_mod

def main():
    # Ensure default user database path (~/.kubelingo/kubelingo.db)
    home_cfg_dir = os.path.expanduser('~/.kubelingo')
    os.makedirs(home_cfg_dir, exist_ok=True)
    cfg.APP_DIR = home_cfg_dir
    cfg.DATABASE_FILE = os.path.join(home_cfg_dir, 'kubelingo.db')
    db_mod.DATABASE_FILE = cfg.DATABASE_FILE
    # Initialize database schema
    init_db()

    # Define UI config footer question manually (bump version)
    starting_yaml = (
        "footer:\n"
        "  version: \"CKAD Simulator Kubernetes 1.33\"\n"
        "  link: \"https://killer.sh\""
    )
    correct_yaml = (
        "footer:\n"
        "  version: \"CKAD Simulator Kubernetes 1.34\"\n"
        "  link: \"https://killer.sh\""
    )
    questions = [
        {
            'id': 'ui_config::footer::0',
            'prompt': 'Bump the version string in the footer from "CKAD Simulator Kubernetes 1.33" to "CKAD Simulator Kubernetes 1.34" in the UI configuration file.',
            'starting_yaml': starting_yaml,
            'correct_yaml': correct_yaml,
            'category': 'Footer',
        }
    ]

    source_file = 'ui_config_script'
    added = 0
    for q in questions:
        validator = {'type': 'yaml', 'expected': q['correct_yaml']}
        try:
            add_question(
                id=q['id'],
                prompt=q['prompt'],
                source_file=source_file,
                response=None,
                category=q.get('category'),
                source='script',
                validation_steps=[],
                validator=validator,
            )
            print(f"Added UI question {q['id']}")
            added += 1
        except Exception as e:
            print(f"Failed to add question {q['id']}: {e}")
    print(f"Total UI questions added: {added}")

if __name__ == '__main__':  # noqa: E999
    main()