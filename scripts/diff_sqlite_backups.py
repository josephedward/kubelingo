#!/usr/bin/env python3
"""Diffs the two most recent SQLite backups."""

import subprocess
import sys
from pathlib import Path

def get_two_most_recent_backups(backup_dir: Path):
    """Finds the two most recent .db files in the backup directory."""
    if not backup_dir.is_dir():
        return None, None
    
    db_files = list(backup_dir.glob('*.db'))
    if len(db_files) < 2:
        return None, None

    sorted_files = sorted(db_files, key=lambda p: p.stat().st_mtime, reverse=True)
    return sorted_files[0], sorted_files[1]

def diff_databases(db1: Path, db2: Path):
    """Dumps two SQLite databases and prints the diff."""
    print(f"Comparing {db1.name} (newer) and {db2.name} (older)...")
    
    f_old_name, f_new_name = None, None
    try:
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix=".sql", delete=False) as f_old:
            f_old_name = f_old.name
            subprocess.run(["sqlite3", str(db2), ".dump"], stdout=f_old, check=True, text=True)
            
        with tempfile.NamedTemporaryFile(mode='w', suffix=".sql", delete=False) as f_new:
            f_new_name = f_new.name
            subprocess.run(["sqlite3", str(db1), ".dump"], stdout=f_new, check=True, text=True)

        print("-" * 40)
        print(f"--- {db2.name}")
        print(f"+++ {db1.name}")
        subprocess.run(["diff", "-u", f_old_name, f_new_name], text=True)
        print("-" * 40)

    except FileNotFoundError:
        print("Error: 'sqlite3' or 'diff' command not found. Please ensure they are in your PATH.")
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        if e.stderr:
            print(e.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        # Clean up temp files
        if f_old_name:
            Path(f_old_name).unlink(missing_ok=True)
        if f_new_name:
            Path(f_new_name).unlink(missing_ok=True)

def main():
    """Finds the two most recent SQLite backups and diffs them."""
    repo_root = Path(__file__).resolve().parent.parent
    backup_dir = repo_root / 'backups' / 'sqlite'
    
    newest, second_newest = get_two_most_recent_backups(backup_dir)

    if not newest or not second_newest:
        print(f"Need at least two SQLite backup files in {backup_dir} to compare.")
        return
        
    diff_databases(newest, second_newest)

if __name__ == "__main__":
    main()
