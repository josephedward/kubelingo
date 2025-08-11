#!/usr/bin/env python3
"""
Index the live SQLite database and all configured backup files.
"""
import sys
from pathlib import Path
from kubelingo.utils.path_utils import get_live_db_path, get_all_sqlite_backup_dirs, find_sqlite_backup_files

def main():
    live = get_live_db_path()
    print("Live database:")
    print(f"  {live}")
    print()

    dirs = get_all_sqlite_backup_dirs()
    print("Configured SQLite backup directories:")
    for d in dirs:
        print(f" - {d}")
    print()

    files = find_sqlite_backup_files()
    if not files:
        print("No SQLite files found in any configured backup directories.")
        sys.exit(0)
    print("SQLite backup files:")
    for f in sorted(files):
        print(f)

if __name__ == '__main__':
    main()#!/usr/bin/env python3
"""
Finds and lists all SQLite database files within the project repository.
"""
import sys
from pathlib import Path

# Ensure the project root is on the python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kubelingo.utils.path_utils import get_all_sqlite_files_in_repo
from kubelingo.utils.ui import Fore, Style


def main():
    """Prints a list of all SQLite files in the repository."""
    print(f"{Fore.CYAN}--- All SQLite Files in Repository ---{Style.RESET_ALL}")
    try:
        sqlite_files = get_all_sqlite_files_in_repo()
        if not sqlite_files:
            print(f"{Fore.YELLOW}No SQLite files found.{Style.RESET_ALL}")
            return

        for f in sqlite_files:
            print(str(f))

        print(f"\n{Fore.GREEN}Found {len(sqlite_files)} file(s).{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
