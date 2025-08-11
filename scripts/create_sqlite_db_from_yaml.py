#!/usr/bin/env python3
import argparse
import inspect
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path to allow importing from kubelingo
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import os

try:
    import yaml
except ImportError:
    print("Error: PyYAML is not installed. Please install it to run this script:")
    print("pip install PyYAML")
    sys.exit(1)

from kubelingo.database import add_question, get_db_connection, init_db
from kubelingo.utils import path_utils
from kubelingo.utils.config import ENABLED_QUIZZES, YAML_BACKUP_DIRS
from kubelingo.utils.config import get_live_db_path
from kubelingo.utils.ui import Fore, Style


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

    category_to_source_file = ENABLED_QUIZZES
    unmatched_categories = set()

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

    # Create a mapping from category names to their source filenames.
    category_to_source_file = {
        k: os.path.basename(v) for k, v in ENABLED_QUIZZES.items()
    }
    unmatched_categories = set()

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
                    # Look for a 'questions' or 'entries' key specifically.
                    questions_list = questions_data.get("questions") or questions_data.get("entries")

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

                    # Normalize legacy 'answer' to 'correct_yaml' for yaml_author/yaml_edit questions
                    if "answer" in q_dict:
                        q_dict["correct_yaml"] = q_dict.pop("answer")

                    # Normalize legacy 'starting_yaml' to 'initial_files' for yaml_edit questions
                    if "starting_yaml" in q_dict:
                        q_dict["initial_files"] = {"manifest.yaml": q_dict.pop("starting_yaml")}

                    # Normalize legacy 'question' key to 'prompt'
                    if "question" in q_dict:
                        q_dict["prompt"] = q_dict.pop("question")

                    # Normalize legacy yaml editing/authoring fields
                    q_type = q_dict.get("type")
                    if q_type in ("yaml_edit", "yaml_author"):
                        if "answer" in q_dict and "correct_yaml" not in q_dict:
                            q_dict["correct_yaml"] = q_dict.pop("answer")
                        if "starting_yaml" in q_dict and "initial_files" not in q_dict:
                            # Use a generic filename for the initial file content, as one is required.
                            q_dict["initial_files"] = {
                                "f.yaml": q_dict.pop("starting_yaml")
                            }

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

                    # Derive source_file from category to ensure correct quiz association,
                    # especially when processing consolidated backups.
                    category = q_dict.get("category")
                    source_file_from_category = category_to_source_file.get(category)

                    if source_file_from_category:
                        q_dict["source_file"] = source_file_from_category
                    elif not q_dict.get("source_file"):
                        # If a source file can't be determined, we can't link the question to a quiz.
                        # This can happen if a category in the YAML is not in ENABLED_QUIZZES.
                        if category:
                            unmatched_categories.add(category)
                        continue

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


    if unmatched_categories:
        print("\nWarning: The following categories from the YAML file did not match any quiz. Questions in these categories were skipped:")
        for cat in sorted(list(unmatched_categories)):
            print(f"  - {cat}")

    print(f"\nSuccessfully populated database with {question_count} questions.")


def main():
    """
    Main function to parse arguments and run the population script.
    """
    parser = argparse.ArgumentParser(
        description="Populate the SQLite database from YAML backup files."
    )
    parser.add_argument(
        "--yaml-files",
        nargs="+",
        default=None,
        type=str,
        help="Path(s) to input YAML file(s) or directories. Overrides default behavior of using the latest backup.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to the SQLite database file. Defaults to the live application database.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the database before populating. Default is to append questions.",
    )
    args = parser.parse_args()

    if args.yaml_files:
        yaml_files = path_utils.find_yaml_files_from_paths(args.yaml_files)
    else:
        # Default behavior: find the most recent YAML backup file
        print("No specific YAML files provided. Searching for the most recent backup...")
        sorted_backups = path_utils.find_and_sort_files_by_mtime(
            YAML_BACKUP_DIRS, [".yaml", ".yml"]
        )

        if not sorted_backups:
            print(
                "Error: No YAML backup files found in configured backup directories."
            )
            print(f"Searched in: {YAML_BACKUP_DIRS}")
            sys.exit(1)

        latest_backup = sorted_backups[0]
        print(f"Found latest backup: {latest_backup}")
        yaml_files = [latest_backup]

    if not yaml_files:
        print("No YAML files found.")
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

    db_path = args.db_path or get_live_db_path()

    # Initialize the database. If --clear is specified, the database will be
    # re-created. Otherwise, questions will be appended.
    init_db(clear=args.clear, db_path=db_path)

    print(f"\nPopulating database at: {db_path}")
    populate_db_from_yaml(unique_files, db_path=db_path)


if __name__ == "__main__":
    main()
