#!/usr/bin/env python3
"""
Restore or merge a SQLite backup into the active Kubelingo database.
"""
import os
import sys
import shutil
import argparse
from pathlib import Path

# Inject project root for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.utils.config import DATABASE_FILE

def main():
    parser = argparse.ArgumentParser(
        description="Restore or merge from a SQLite backup into the active database."
    )
    parser.add_argument(
        'backup_file',
        type=str,
        help="Path to the SQLite backup file to restore from"
    )
    parser.add_argument(
        '-d', '--db-path',
        type=str,
        default=None,
        help=f"Target database path (default: {DATABASE_FILE})"
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help="Overwrite the target database file with the backup"
    )
    args = parser.parse_args()

    backup = Path(args.backup_file)
    if not backup.is_file():
        print(f"Backup file not found: {backup}")
        sys.exit(1)

    target = Path(args.db_path or DATABASE_FILE)
    if args.overwrite:
        # Make a copy of current DB first
        if target.exists():
            backup_current = target.with_suffix(target.suffix + '.pre_restore')
            try:
                shutil.copy2(target, backup_current)
                print(f"Current DB backed up to {backup_current}")
            except Exception as e:
                print(f"Failed to backup current DB: {e}")
                sys.exit(1)
        try:
            shutil.copy2(backup, target)
            print(f"Restored backup {backup} -> {target}")
        except Exception as e:
            print(f"Failed to restore backup: {e}")
            sys.exit(1)
    else:
        print("Merge operation is not implemented yet. Use --overwrite to replace the database.")
        sys.exit(1)

if __name__ == '__main__':
    main()#!/usr/bin/env python3
"""
Restores the Kubelingo questions database from a chosen backup.

This script lists available SQLite backups, prompts the user to select one,
and copies it to the default user database location
(`~/.kubelingo/kubelingo.db`), replacing any existing live database.
"""
import os
import shutil
import sys
from pathlib import Path

def get_backups(backup_dir: Path):
    """Finds all .db files in the backup directory."""
    if not backup_dir.is_dir():
        return []
    return sorted(list(backup_dir.glob('*.db')), key=lambda p: p.stat().st_mtime, reverse=True)

def main():
    try:
        import questionary
    except ImportError:
        print("Error: 'questionary' library not found. Please install it with:")
        print("pip install questionary")
        sys.exit(1)

    repo_root = Path(__file__).resolve().parent.parent
    backup_dir = repo_root / 'backups' / 'sqlite'

    backups = get_backups(backup_dir)
    if not backups:
        print(f"No backup databases found in '{backup_dir}'.")
        return

    backup_to_restore = questionary.select(
        "Which backup would you like to restore?",
        choices=[p.name for p in backups] + [questionary.Separator(), "Cancel"]
    ).ask()

    if not backup_to_restore or backup_to_restore == "Cancel":
        print("Restore operation cancelled.")
        return

    backup_db = backup_dir / backup_to_restore

    # Prepare user DB directory
    home = os.path.expanduser('~')
    app_dir = os.path.join(home, '.kubelingo')
    os.makedirs(app_dir, exist_ok=True)
    dst_db = os.path.join(app_dir, 'kubelingo.db')
    
    # Confirm overwrite
    if os.path.exists(dst_db):
        confirm = questionary.confirm(
            f"This will overwrite the existing database at '{dst_db}'. Continue?",
            default=False
        ).ask()
        if not confirm:
            print("Restore operation cancelled.")
            return

    # Copy
    try:
        shutil.copy2(backup_db, dst_db)
        print(f"Restored questions DB from '{backup_db}' to '{dst_db}'.")
    except Exception as e:
        print(f"Failed to restore DB: {e}")

if __name__ == '__main__':
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
    from kubelingo.utils.path_utils import find_and_sort_files_by_mtime, get_live_db_path
    from kubelingo.utils.config import SQLITE_BACKUP_DIRS
except ImportError as e:
    print(f"Error: A required kubelingo module is not available: {e}. "
          "Ensure you have 'questionary' installed ('pip install questionary') "
          "and run this from the project root.", file=sys.stderr)
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
