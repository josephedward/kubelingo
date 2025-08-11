#!/usr/bin/env python3
"""
Restores the live database from a selected SQLite backup file.
"""
import sys
import shutil
from pathlib import Path
import datetime

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    import questionary
except ImportError:
    print("Error: Required modules are not installed. Please run:", file=sys.stderr)
    print("pip install questionary", file=sys.stderr)
    sys.exit(1)

try:
    from kubelingo.utils.path_utils import find_and_sort_files_by_mtime, get_live_db_path
    from kubelingo.utils.config import SQLITE_BACKUP_DIRS
except ImportError as e:
    print(f"Error: A required kubelingo module is not available: {e}. "
          "Ensure you run this from the project root.", file=sys.stderr)
    sys.exit(1)


def main():
    """Interactively restores a SQLite backup."""
    backup_dirs = SQLITE_BACKUP_DIRS
    if not backup_dirs:
        print("No SQLite backup directories are configured.", file=sys.stderr)
        sys.exit(1)

    try:
        backup_files = find_and_sort_files_by_mtime(backup_dirs, [".db", ".sqlite", ".sqlite3"])
    except Exception as e:
        print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)

    if not backup_files:
        print("No SQLite backup files found to restore from.", file=sys.stderr)
        sys.exit(1)

    choices = []
    for f in backup_files:
        mod_time = f.stat().st_mtime
        mod_time_str = datetime.datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
        choices.append(
            questionary.Choice(title=f"{f.name} ({mod_time_str})", value=str(f))
        )
    
    selected_backup_path_str = questionary.select(
        "Select a backup to restore:",
        choices=choices,
        use_indicator=True
    ).ask()

    if not selected_backup_path_str:
        print("Restore cancelled.")
        sys.exit(0)

    selected_backup_path = Path(selected_backup_path_str)
    live_db_path_str = get_live_db_path()
    live_db_path = Path(live_db_path_str)

    print(f"\nThis will OVERWRITE the current live database:")
    print(f"  {live_db_path}")
    print(f"with the contents of backup:")
    print(f"  {selected_backup_path}")

    confirm = questionary.confirm(f"Are you sure you want to proceed?", default=False).ask()

    if confirm:
        try:
            live_db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(selected_backup_path, live_db_path)
            print("\nRestore successful.")
            print(f"'{live_db_path.name}' has been updated.")
        except Exception as e:
            print(f"\nError during restore: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("\nRestore aborted by user.")


if __name__ == "__main__":
    main()
