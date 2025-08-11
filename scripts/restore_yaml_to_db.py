import argparse
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

from typing import Optional
from kubelingo.database import add_question, get_db_connection, init_db


def restore_yaml_to_db(yaml_path: str, clear_db: bool, db_path: Optional[str] = None):
    """
    Restores questions from a YAML file to the database.
    """
    yaml_file = Path(yaml_path)
    if not yaml_file.exists():
        print(f"Error: YAML file not found at {yaml_path}")
        sys.exit(1)

    init_db(clear=clear_db, db_path=db_path)
    conn = get_db_connection(db_path=db_path)

    with open(yaml_file, "r", encoding="utf-8") as f:
        try:
            questions = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file: {e}")
            conn.close()
            sys.exit(1)

    if not isinstance(questions, list):
        print("Error: YAML file should contain a list of questions.")
        conn.close()
        sys.exit(1)

    count = 0
    try:
        for q_data in questions:
            # add_question expects kwargs, so we unpack the dictionary
            add_question(conn=conn, **q_data)
            count += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error adding questions to database: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

    print(f"Successfully restored {count} questions from {yaml_path}")


def main():
    """
    Main function to parse arguments and run the restore.
    """
    parser = argparse.ArgumentParser(
        description="Restore questions from a YAML backup file to the SQLite database."
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="Path to the input YAML file.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the database before restoring questions.",
    )
    args = parser.parse_args()

    restore_yaml_to_db(args.input_file, args.clear)


if __name__ == "__main__":
    main()
