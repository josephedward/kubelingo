#!/usr/bin/env python3
"""
Export the Kubelingo questions database to a YAML backup file.
"""
import argparse
import os
import sys
import sqlite3
import datetime
from typing import Optional

try:
    import yaml
except ImportError:
    print("PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# Ensure project root is in path for imports
project_root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root_path not in sys.path:
    sys.path.insert(0, project_root_path)

from kubelingo.database import get_db_connection, _row_to_question_dict
from kubelingo.utils.config import YAML_BACKUP_DIRS


def export_db_to_yaml(output_file: str, db_path: Optional[str] = None) -> int:
    """
    Exports questions from the database to a YAML file.
    Returns the number of questions exported.
    """
    conn = get_db_connection(db_path=db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM questions")
    rows = cur.fetchall()
    conn.close()

    data = [_row_to_question_dict(row) for row in rows]
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

    print(f"Exported {len(data)} questions to {output_file}")
    return len(data)


def main():
    """Main function to parse arguments and run the export."""
    parser = argparse.ArgumentParser(description="Export questions DB to YAML")
    parser.add_argument("-o", "--output", help="Output YAML file path")
    args = parser.parse_args()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.output:
        out_file = args.output
    else:
        # Default to the first configured backup directory
        out_dir = YAML_BACKUP_DIRS[0] if YAML_BACKUP_DIRS else "backups"
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, f"questions_{timestamp}.yaml")

    export_db_to_yaml(out_file)


if __name__ == "__main__":
    main()
