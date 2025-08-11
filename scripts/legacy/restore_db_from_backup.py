#!/usr/bin/env python3
"""
Restores the Kubelingo questions database from a chosen backup file.

This script lists available SQLite backups and prompts the user to select one.
The selected backup is then copied to the live database location
(`~/.kubelingo/kubelingo.db`), replacing any existing live database.
"""
import os
import shutil
import sys
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    import questionary
    from kubelingo.utils.path_utils import find_sqlite_files_from_paths
    from kubelingo.utils.config import SQLITE_BACKUP_DIRS
except ImportError:
    print("Error: Required modules are not installed. Please run:")
    print("pip install questionary")
    sys.exit(1)


def main():
    """Interactively select and restore an SQLite backup."""
    backup_dirs = SQLITE_BACKUP_DIRS
    if not backup_dirs:
        print("No SQLite backup directories are configured.", file=sys.stderr)
        sys.exit(1)

    try:
        backup_files = find_sqlite_files_from_paths(backup_dirs)
    except Exception as e:
        print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)

    if not backup_files:
        print("No SQLite backup files found to restore from.", file=sys.stderr)
        sys.exit(1)

    sorted_files = sorted(backup_files, key=lambda p: p.stat().st_mtime, reverse=True)

    selected_backup_str = questionary.select(
        "Which backup would you like to restore?",
        choices=[str(p) for p in sorted_files] + ["Cancel"],
    ).ask()

    if not selected_backup_str or selected_backup_str == "Cancel":
        print("Restore operation cancelled.")
        return

    backup_db = Path(selected_backup_str)

    # Prepare user DB directory
    home = os.path.expanduser("~")
    app_dir = os.path.join(home, ".kubelingo")
    os.makedirs(app_dir, exist_ok=True)
    dst_db = os.path.join(app_dir, "kubelingo.db")

    # Copy
    try:
        shutil.copy2(backup_db, dst_db)
        print(f"\nSuccessfully restored database to '{dst_db}' from backup '{backup_db}'.")
    except Exception as e:
        print(f"Failed to restore DB: {e}")


if __name__ == "__main__":
    main()
