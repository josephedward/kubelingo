#!/usr/bin/env python3
"""
Creates a timestamped backup of the live Kubelingo SQLite database.
"""
import os
import shutil
import sys
import datetime
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from kubelingo.utils.config import SQLITE_BACKUP_DIRS
    from kubelingo.utils.path_utils import get_live_db_path
except ImportError as e:
    print(f"Error: A required kubelingo module is not available: {e}. "
          "Ensure you run this from the project root.", file=sys.stderr)
    sys.exit(1)

def main():
    """Copies the live db to the first configured backup directory."""
    live_db_path_str = get_live_db_path()
    live_db_path = Path(live_db_path_str)

    if not live_db_path.exists():
        print(f"Live database not found at '{live_db_path}'. Cannot create backup.", file=sys.stderr)
        sys.exit(1)
        
    backup_dirs = SQLITE_BACKUP_DIRS
    if not backup_dirs:
        print("No SQLite backup directories are configured. Cannot create backup.", file=sys.stderr)
        sys.exit(1)
        
    # Use the first configured backup directory
    backup_dir = Path(backup_dirs[0])
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"kubelingo_backup_{timestamp}.db"
    backup_path = backup_dir / backup_filename

    try:
        shutil.copy2(live_db_path, backup_path)
        print(f"Successfully created backup: {backup_path}")
    except Exception as e:
        print(f"Failed to create backup: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
