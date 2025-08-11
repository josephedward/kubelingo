import argparse
import inspect
import sys
from pathlib import Path
from typing import Optional

# Add project root to path to allow importing from kubelingo
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    import yaml
except ImportError:
    print("Error: PyYAML is not installed. Please install it to run this script:")
    print("pip install PyYAML")
    sys.exit(1)

from kubelingo.database import add_question, get_db_connection, init_db
from kubelingo.utils import path_utils


def populate_db_from_yaml(
    yaml_files: list[Path], clear_db: bool, db_path: Optional[str] = None
):
    """
    Populates the database with questions from a list of YAML files.
    """
    if not yaml_files:
        print("No YAML files found to process.")
        return

    init_db(clear=clear_db, db_path=db_path)
    conn = get_db_connection(db_path=db_path)

    # Get the list of valid arguments for the add_question function
    sig = inspect.signature(add_question)
    allowed_args = set(sig.parameters.keys())

    question_count = 0
    try:
        for file_path in yaml_files:
            print(f"  - Processing '{file_path.name}'...")
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    questions_data = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    print(f"Error parsing YAML file {file_path}: {e}", file=sys.stderr)
                    continue

                if not questions_data or not isinstance(questions_data, list):
                    continue

                for q_data in questions_data:
                    q_dict = q_data.copy()

                    # Flatten metadata, giving preference to top-level keys
                    if "metadata" in q_dict and isinstance(q_dict["metadata"], dict):
                        metadata = q_dict.pop("metadata")
                        for k, v in metadata.items():
                            if k not in q_dict:
                                q_dict[k] = v

                    # Normalize legacy 'question' key to 'prompt'
                    if "question" in q_dict:
                        q_dict["prompt"] = q_dict.pop("question")

                    # Set schema_category based on question type
                    q_type = q_dict.get("type", "command")
                    if q_type in ("yaml_edit", "yaml_author", "live_k8s_edit", "manifest"):
                        q_dict["schema_category"] = "manifest"
                    elif q_type in ("command", "kubectl"):
                        q_dict["schema_category"] = "command"
                    else:  # socratic, etc. maps to 'basic'
                        q_dict["schema_category"] = "basic"

                    # Map YAML 'type' to DB 'question_type'
                    if "type" in q_dict:
                        q_dict["question_type"] = q_dict.pop("type")

                    # Override source_file to the YAML filename being processed
                    q_dict["source_file"] = file_path.name

                    # Remove legacy keys that are not supported by the database schema.
                    q_dict.pop("solution_file", None)

                    # Filter dict to only include keys that add_question accepts
                    q_dict_for_db = {
                        k: v for k, v in q_dict.items() if k in allowed_args
                    }

                    add_question(conn=conn, **q_dict_for_db)
                    question_count += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error adding questions to database: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

    print(f"\nSuccessfully populated database with {question_count} questions.")


def main():
    """
    Main function to parse arguments and run the population script.
    """
    parser = argparse.ArgumentParser(
        description="Populate the SQLite database from YAML backup files."
    )
    parser.add_argument(
        "input_paths",
        nargs="*",
        type=str,
        help="Path(s) to input YAML file(s) or directories. If not provided, scans default backup directories.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the database before populating.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Automatically confirm and proceed without prompting.",
    )
    args = parser.parse_args()

    yaml_files = []
    if not args.input_paths:
        print("No input paths provided. Scanning default backup directories...")
        yaml_files = path_utils.get_all_yaml_backups()
    else:
        yaml_files = path_utils.find_yaml_files_from_paths(args.input_paths)

    if not yaml_files:
        print("No YAML backup files found.")
        sys.exit(0)

    unique_files = sorted(list(set(yaml_files)))
    print(f"Found {len(unique_files)} YAML file(s) to process:")
    for f in unique_files:
        print(f"  - {f.name}")

    if not args.yes:
        confirm = input("\nProceed with populating the database from these files? (y/N): ")
        if confirm.lower() != 'y':
            print("Operation cancelled.")
            sys.exit(0)

    populate_db_from_yaml(unique_files, args.clear)


if __name__ == "__main__":
    main()
