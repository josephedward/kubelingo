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
