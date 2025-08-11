import argparse
import inspect
import sys
from datetime import datetime
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
        "question_type",
        "schema_category",
        "answers",
        "correct_yaml",
        "difficulty",
        "explanation",
        "initial_files",
        "pre_shell_cmds",
        "subject_matter",
        "metadata",
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
                    # Look for a 'questions' key specifically.
                    questions_list = questions_data.get("questions")

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

                    # Normalize 'type' from YAML to 'question_type' for the database
                    if "type" in q_dict:
                        q_dict["question_type"] = q_dict.pop("type")

                    # Normalize 'subject' from YAML to 'subject_matter' for the database
                    if "subject" in q_dict:
                        q_dict["subject_matter"] = q_dict.pop("subject")

                    # Set schema_category based on question type
                    q_type = q_dict.get("question_type", "command")
                    if q_type in ("yaml_edit", "yaml_author", "live_k8s_edit", "manifest"):
                        q_dict["schema_category"] = "manifest"
                    elif q_type in ("command", "kubectl"):
                        q_dict["schema_category"] = "command"
                    else:  # socratic, etc. maps to 'basic'
                        q_dict["schema_category"] = "basic"

                    # Set source_file to the YAML filename being processed if not already present.
                    # This preserves the original source file if it was present in the question data.
                    if not q_dict.get("source_file"):
                        q_dict["source_file"] = file_path.name

                    # Remove legacy keys that are not supported by the database schema.
                    q_dict.pop("solution_file", None)
                    q_dict.pop("subject", None)
                    q_dict.pop("type", None)

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

        if args.yes:
            # When in non-interactive mode, find the latest restorable backup.
            # A restorable backup is assumed to be one of the consolidated files.
            restorable_backups = [
                p
                for p in all_backups
                if p.name.startswith("consolidated_unique_questions")
            ]
            if not restorable_backups:
                print(
                    "No restorable backup files (e.g., 'consolidated_unique_questions*.yaml') found.",
                    file=sys.stderr,
                )
                sys.exit(1)
            selected_file = restorable_backups[-1]  # The last one is the most recent
            print(f"Automatically selecting latest backup: {selected_file.name}")
            yaml_files = [selected_file]
        else:
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

    # Generate a new timestamped database path in the first backup directory.
    sqlite_backup_dirs = path_utils.get_all_sqlite_backup_dirs()
    if not sqlite_backup_dirs:
        print(
            "Error: No SQLite backup directories configured. Cannot create new database.",
            file=sys.stderr,
        )
        sys.exit(1)

    sqlite_backup_dir = Path(sqlite_backup_dirs[0])
    sqlite_backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_filename = f"kubelingo_db_{timestamp}.sqlite3"
    db_path = str(sqlite_backup_dir / db_filename)

    if not args.yes:
        print(f"\nThis will create a new database at: '{db_path}'.")
        confirm = input("Are you sure you want to proceed? (y/N): ")
        if confirm.lower() != 'y':
            print("Operation cancelled.")
            sys.exit(0)
    else:
        print(f"Creating new database at: {db_path}")

    # Initialize the new database.
    init_db(clear=True, db_path=db_path)

    print(f"\nPopulating new database at: {db_path}")
    populate_db_from_yaml(unique_files, db_path=db_path)


if __name__ == "__main__":
    main()
