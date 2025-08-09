#!/usr/bin/env python3
"""
Builds the Kubelingo question database from source YAML files.

This script provides a "rock solid" workflow for developers adding or updating
quiz content. It performs two key actions:

1.  Imports all questions from the standard YAML source directories
    (`question-data/yaml`, `question-data/yaml-bak`, `question-data/manifests`)
    into the live user database at `~/.kubelingo/kubelingo.db`. It uses the
    existing `import_yaml_to_db.py` script to ensure consistency.

2.  Creates a version-controlled backup of the newly populated database by
    copying it to `question-data-backup/kubelingo_original.db`. This file
    is used to seed new installations of the application.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    """Runs the database import and backup process."""
    project_root = Path(__file__).parent.parent

    print("Step 1: Importing all YAML questions into the live database...")
    import_script_path = project_root / "scripts" / "import_yaml_to_db.py"

    if not import_script_path.exists():
        print(f"Error: Import script not found at {import_script_path}")
        sys.exit(1)

    result = subprocess.run(
        [sys.executable, str(import_script_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        print("Error during YAML import:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)

    print("YAML import successful.")
    # Show the output of the import script, which lists discovered files.
    print(result.stdout)

    print("\nStep 2: Backing up live database to project backup...")
    live_db_path = Path.home() / ".kubelingo" / "kubelingo.db"
    backup_db_dir = project_root / "question-data-backup"
    backup_db_path = backup_db_dir / "kubelingo_original.db"

    if not live_db_path.exists():
        print(f"Error: Live database not found at {live_db_path}")
        print("Please run the application or the import script to create it.")
        sys.exit(1)

    backup_db_dir.mkdir(exist_ok=True)

    try:
        shutil.copyfile(live_db_path, backup_db_path)
        print(f"Successfully backed up database to {backup_db_path}")
    except Exception as e:
        print(f"Error during database backup: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
