#!/usr/bin/env python3
"""
Export all questions from the SQLite database to a YAML backup file.
"""

import os
import time
import argparse
import sys

try:
    import yaml
except ImportError:
    print("Error: PyYAML is not installed. Please install PyYAML to run this script.")
    sys.exit(1)

from kubelingo.database import init_db, get_all_questions
from kubelingo.utils.config import PROJECT_ROOT

def main():
    parser = argparse.ArgumentParser(
        description="Export all questions from the database to a YAML backup file."
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (defaults to question-data-backup/<timestamp>.yaml)"
    )
    args = parser.parse_args()

    # Ensure database exists and schema is initialized
    init_db()
    backup_dir = os.path.join(PROJECT_ROOT, "question-data-backup")
    if not os.path.isdir(backup_dir):
        os.makedirs(backup_dir, exist_ok=True)

    if args.output:
        output_path = args.output
        if os.path.isdir(output_path):
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            output_path = os.path.join(output_path, f"{timestamp}.yaml")
    else:
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        output_path = os.path.join(backup_dir, f"{timestamp}.yaml")

    questions = get_all_questions()

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(questions, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        print(f"Failed to write YAML file: {e}")
        sys.exit(1)

    print(f"Wrote {len(questions)} questions to {output_path}")

if __name__ == "__main__":
    main()