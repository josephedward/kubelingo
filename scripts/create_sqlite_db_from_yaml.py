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
    yaml_files: list[Path], db_path: Optional[str] = None
):
    """
    Populates the database with questions from a list of YAML files.
    """
    if not yaml_files:
        print("No YAML files found to process.")
        return

    conn = get_db_connection(db_path=db_path)

    # Explicitly list allowed arguments for add_question to avoid passing unexpected keys.
    # This is safer than introspection, which may fail in some environments.
    allowed_args = {
        "id",
        "prompt",
        "source_file",
        "response",
        "category",
        "source",
        "validation_steps",
        "validator",
        "review",
        "type",
        "schema_category",
        "answers",
        "correct_yaml",
        "difficulty",
        "explanation",
        "initial_files",
        "pre_shell_cmds",
    }

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

                # The YAML might contain a top-level list or a dictionary with a list of questions.
                questions_list = questions_data
                if isinstance(questions_data, dict):
                    # Find the first list in the dictionary's values.
                    # This handles formats where questions are nested, e.g., {'questions': [...]}.
                    found_list = None
                    for value in questions_data.values():
                        if isinstance(value, list):
                            found_list = value
                            break  # Use the first list found
                    questions_list = found_list

                if not isinstance(questions_list, list):
                    continue

                for q_data in questions_list:
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
        help="Path(s) to input YAML file(s) or directories. If not provided, scans default backup directories and prompts for selection.",
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
        print("No input paths provided. Scanning for YAML backups...")
        backup_dir = project_root / "backups" / "yaml"
        all_backups = sorted(
            list(backup_dir.glob("**/*.yaml")) + list(backup_dir.glob("**/*.yml")),
            key=lambda p: p.name,
        )
        if not all_backups:
            print("No YAML backup files found.")
            sys.exit(0)

        print("\nPlease select a YAML backup to restore from:")
        for i, backup_path in enumerate(all_backups):
            print(f"  {i + 1}: {backup_path.name}")

        try:
            selection = input(f"\nEnter number (1-{len(all_backups)}): ")
            selection_idx = int(selection) - 1
            if not 0 <= selection_idx < len(all_backups):
                raise ValueError
            selected_file = all_backups[selection_idx]
            yaml_files = [selected_file]
        except (ValueError, IndexError):
            print("Invalid selection. Aborting.", file=sys.stderr)
            sys.exit(1)
    else:
        yaml_files = path_utils.find_yaml_files_from_paths(args.input_paths)

    if not yaml_files:
        print("No YAML backup files found.")
        sys.exit(0)

    unique_files = sorted(list(set(yaml_files)))
    print(f"Found {len(unique_files)} YAML file(s) to process:")

    # Show a sample of files instead of all of them if there are too many
    if len(unique_files) > 20:
        print("Showing first 10 files:")
        for f in unique_files[:10]:
            print(f"  - {f.name}")
        print(f"  ...and {len(unique_files) - 10} more.")
    else:
        for f in unique_files:
            print(f"  - {f.name}")

    db_path = path_utils.get_live_db_path()
    if not args.yes:
        print(f"\nWARNING: This will clear and repopulate the database at '{db_path}'.")
        confirm = input("Are you sure you want to proceed? (y/N): ")
        if confirm.lower() != 'y':
            print("Operation cancelled.")
            sys.exit(0)

    # Clear the database before populating to ensure a fresh start.
    init_db(clear=True, db_path=db_path)

    print(f"\nPopulating database at: {db_path}")
    populate_db_from_yaml(unique_files, db_path=db_path)


if __name__ == "__main__":
    main()
