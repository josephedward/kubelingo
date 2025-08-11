#!/usr/bin/env python3
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
