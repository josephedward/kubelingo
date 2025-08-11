import argparse
import sqlite3
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
from kubelingo.question import QuestionCategory
from kubelingo.utils.path_utils import find_yaml_files_from_paths, get_all_yaml_files


def restore_yaml_to_db(
    yaml_files: list[Path], clear_db: bool, db_path: Optional[str] = None
):
    """
    Restores questions from a list of YAML files to the database.
    """
    if not yaml_files:
        print("No YAML files found to restore.")
        return

    init_db(clear=clear_db, db_path=db_path)
    conn = get_db_connection(db_path=db_path)

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

                if not questions_data:
                    continue

                if not isinstance(questions_data, list):
                    print(
                        f"Warning: YAML file {file_path} should contain a list of questions. Skipping.",
                        file=sys.stderr,
                    )
                    continue

                for q_dict in questions_data:
                    # Flatten metadata, giving preference to top-level keys
                    if "metadata" in q_dict and isinstance(q_dict["metadata"], dict):
                        metadata = q_dict.pop("metadata")
                        # Pop unsupported 'links' key from metadata before merging.
                        metadata.pop("links", None)
                        for k, v in metadata.items():
                            if k not in q_dict:
                                q_dict[k] = v

                    # Set schema_category based on the question type
                    q_type = q_dict.get("type", "command")
                    if q_type in ("yaml_edit", "yaml_author", "live_k8s_edit"):
                        q_dict["schema_category"] = QuestionCategory.MANIFEST.value
                    elif q_type == "socratic":
                        q_dict["schema_category"] = QuestionCategory.OPEN_ENDED.value
                    else:  # command, etc.
                        q_dict["schema_category"] = QuestionCategory.COMMAND.value

                    # The 'type' field from YAML needs to be mapped to 'question_type' for the DB
                    if "type" in q_dict:
                        q_dict["question_type"] = q_dict.pop("type")
                    else:
                        q_dict["question_type"] = q_type

                    # Override source_file to the YAML filename being processed
                    q_dict["source_file"] = file_path.name
                    # Preserve any `links` entries in metadata
                    links = q_dict.pop("links", None)
                    if links:
                        metadata = q_dict.get("metadata")
                        if not isinstance(metadata, dict):
                            metadata = {}
                        metadata["links"] = links
                        q_dict["metadata"] = metadata
                    add_question(conn=conn, **q_dict)
                    question_count += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error adding questions to database: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

    print(f"\nSuccessfully restored {question_count} questions.")


def main():
    """
    Main function to parse arguments and run the restore.
    """
    parser = argparse.ArgumentParser(
        description="Restore questions from YAML backup files to the SQLite database."
    )
    parser.add_argument(
        "input_paths",
        nargs="*",
        type=str,
        help="Path(s) to input YAML file(s) or directories. If not provided, scans default question source directories.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the database before restoring questions.",
    )
    args = parser.parse_args()

    yaml_files = []
    if not args.input_paths:
        print("No input paths provided. Scanning default question directories...")
        yaml_files = get_all_yaml_files()
    else:
        yaml_files = find_yaml_files_from_paths(args.input_paths)

    if not yaml_files:
        print("No YAML files found.")
        sys.exit(0)

    unique_files = sorted(list(set(yaml_files)))
    print(f"Found {len(unique_files)} YAML file(s) to process.")

    restore_yaml_to_db(unique_files, args.clear)


if __name__ == "__main__":
    main()
