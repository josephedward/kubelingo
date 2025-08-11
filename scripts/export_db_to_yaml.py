#!/usr/bin/env python3
"""
Export all questions from the SQLite database to a YAML backup file.
"""

import argparse
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

    with open(output_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(questions, f, default_flow_style=False, sort_keys=False)

    print(f"Successfully exported {len(questions)} questions to {output_file}")


def main():
    """
    Main function to parse arguments and run the export.
    """
    backup_dir = Path("question-data-backup")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    default_output = backup_dir / f"db_export_{timestamp}.yaml"

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
