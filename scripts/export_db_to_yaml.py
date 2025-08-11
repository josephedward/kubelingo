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
    main()import argparse
import datetime
import sys
from pathlib import Path

# Add project root to path to allow importing from kubelingo
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    import yaml
except ImportError:
    print("Error: PyYAML is not installed. Please install it to run this script:")
    print("pip install PyYAML")
    sys.exit(1)

from kubelingo.database import get_all_questions, init_db


def export_db_to_yaml(output_path: str):
    """
    Fetches all questions from the database and writes them to a YAML file.
    """
    init_db()  # Ensure DB is initialized
    questions = get_all_questions()

    if not questions:
        print("No questions found in the database to export.")
        return

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        yaml.dump(questions, f, default_flow_style=False, sort_keys=False)

    print(f"Successfully exported {len(questions)} questions to {output_file}")


def main():
    """
    Main function to parse arguments and run the export.
    """
    backup_dir = Path("question-data-backup")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    default_output = backup_dir / f"{timestamp}.yaml"

    parser = argparse.ArgumentParser(
        description="Export all questions from the SQLite database to a YAML file."
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default=str(default_output),
        help=f"Path to the output YAML file. Defaults to a timestamped file in {backup_dir}.",
    )
    args = parser.parse_args()

    export_db_to_yaml(args.output_path)


if __name__ == "__main__":
    main()
