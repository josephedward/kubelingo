import argparse
import sys
from pathlib import Path
from typing import List, Optional

import yaml
from rich.console import Console
from rich.progress import track

# Add project root to path to allow absolute imports
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from kubelingo.database import add_question, get_db_connection, init_db
from kubelingo.utils.path_utils import find_yaml_files_from_paths, get_all_question_dirs


def restore_yaml_to_db(
    yaml_files: list[Path], clear_db: bool, db_path: Optional[str] = None
):
    """
    Restores questions from a list of YAML files to the SQLite database.

    Args:
        yaml_files: List of Path objects for the YAML files to process.
        clear_db: If True, the existing database will be cleared before import.
        db_path: Optional path to the SQLite database file.
    """
    console = Console()
    if clear_db:
        console.print("[bold yellow]Clearing existing database...[/bold yellow]")
        init_db(clear=True, db_path=db_path)
    else:
        # Ensure DB is initialized without clearing if it doesn't exist
        init_db(clear=False, db_path=db_path)

    total_questions = 0
    errors = 0

    # Get a single connection to use for all insertions
    conn = get_db_connection(db_path=db_path)
    try:
        for path in track(yaml_files, description="Processing YAML files..."):
            console.print(f"  - Processing '{path.name}'...")
            try:
                with open(path, 'r') as f:
                    data = yaml.safe_load(f)

                # Gracefully skip files that are not structured as question files
                if not isinstance(data, dict) or 'questions' not in data:
                    console.print(f"    [yellow]Skipping file (not a valid question format): {path.name}[/yellow]")
                    continue

                for q_data in data.get('questions', []):
                    try:
                        # Ensure required fields are present before trying to add
                        if not all(k in q_data for k in ['id', 'prompt']):
                            console.print(f"[red]Error in {path.name}: Skipping question missing 'id' or 'prompt'. ID: {q_data.get('id', 'N/A')}[/red]")
                            errors += 1
                            continue

                        q_data['source_file'] = str(path)
                        # Map `type` from YAML to `question_type` in DB schema
                        if 'type' in q_data:
                            q_data['question_type'] = q_data.pop('type')
                        # Map `subject` from YAML to `subject_matter` in DB schema
                        if 'subject' in q_data:
                            q_data['subject_matter'] = q_data.pop('subject')

                        # Filter to only include arguments expected by add_question
                        valid_keys = {
                            'id', 'prompt', 'response', 'category', 'source',
                            'validation_steps', 'validator', 'source_file', 'review',
                            'explanation', 'difficulty', 'pre_shell_cmds', 'initial_files',
                            'question_type', 'answers', 'correct_yaml', 'schema_category',
                            'metadata', 'subject_matter'
                        }
                        kwargs_for_add = {
                            key: q_data[key] for key in valid_keys if key in q_data
                        }

                        add_question(conn=conn, **kwargs_for_add)
                        total_questions += 1
                    except Exception as e:
                        console.print(f"[red]Error adding question from {path.name} ({q_data.get('id', 'N/A')}): {e}[/red]")
                        errors += 1

            except yaml.YAMLError as e:
                console.print(f"[red]Error parsing YAML file {path.name}: {e}[/red]")
                errors += 1
            except Exception as e:
                console.print(f"[red]An unexpected error occurred with file {path.name}: {e}[/red]")
                errors += 1
    finally:
        conn.close()

    console.print(f"\n[bold green]Restore complete.[/bold green]")
    console.print(f"  - Total questions added: {total_questions}")
    if errors > 0:
        console.print(f"  - Errors encountered: {errors}")


def main():
    """Main function to handle command-line arguments and start the restore process."""
    parser = argparse.ArgumentParser(
        description="Restore questions from YAML files into the SQLite database."
    )
    parser.add_argument(
        "paths",
        nargs='*',
        help="Paths to specific YAML files or directories to scan. "
             "If not provided, scans default question directories."
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help="Clear the existing database before restoring."
    )
    parser.add_argument(
        '--db-path',
        type=str,
        default=None,
        help="Path to the SQLite database file. Uses default if not specified."
    )
    args = parser.parse_args()
    console = Console()

    if args.paths:
        yaml_files = find_yaml_files_from_paths(args.paths)
    else:
        console.print("No input paths provided. Scanning default question directories...")
        default_dirs = get_all_question_dirs()
        yaml_files = find_yaml_files_from_paths(default_dirs)

    if not yaml_files:
        console.print("[bold red]No YAML files found to process.[/bold red]")
        sys.exit(1)

    console.print(f"Found {len(yaml_files)} YAML file(s) to process.")

    restore_yaml_to_db(
        yaml_files=sorted(list(yaml_files)),
        clear_db=args.clear,
        db_path=args.db_path
    )


if __name__ == "__main__":
    main()
