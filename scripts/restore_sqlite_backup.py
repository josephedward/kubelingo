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
