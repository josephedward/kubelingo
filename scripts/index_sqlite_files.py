#!/usr/bin/env python3
"""
Finds all SQLite database files and creates an index file with their metadata.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

# Ensure the project root is on the python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.utils.path_utils import find_sqlite_files, get_all_sqlite_files_in_repo
from kubelingo.utils.ui import Fore, Style


def get_file_metadata(path: Path) -> dict:
    """Gathers metadata for a given file."""
    stat = path.stat()
    return {
        "path": str(path.relative_to(project_root)),
        "size_bytes": stat.st_size,
        "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def main():
    """Finds all SQLite files and creates an index file with their metadata."""
    parser = argparse.ArgumentParser(
        description="Finds all SQLite files and creates an index file with their metadata.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "dirs",
        nargs="*",
        default=[],
        help="One or more directories to scan. If not provided, scans the entire repository.",
    )
    args = parser.parse_args()

    index_file_path = project_root / "backups" / "sqlite_index.yaml"

    try:
        import yaml
    except ImportError:
        print(f"{Fore.RED}Error: PyYAML is not installed. Please install it with 'pip install pyyaml'{Style.RESET_ALL}")
        sys.exit(1)

    try:
        if args.dirs:
            print(f"{Fore.CYAN}--- Indexing SQLite files in specified directories ---{Style.RESET_ALL}")
            sqlite_files = find_sqlite_files(args.dirs)
        else:
            print(f"{Fore.CYAN}--- Indexing all SQLite files in repository ---{Style.RESET_ALL}")
            sqlite_files = get_all_sqlite_files_in_repo()

        all_files = sorted(list(set(sqlite_files)))

        if not all_files:
            print(f"{Fore.YELLOW}No SQLite files found to index.{Style.RESET_ALL}")
            return

        print(f"Found {len(all_files)} SQLite files to index.")

        index_data = {
            "last_updated": datetime.now().isoformat(),
            "files": [get_file_metadata(p) for p in all_files],
        }

        # Ensure backups directory exists
        index_file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(index_file_path, "w") as f:
            yaml.safe_dump(index_data, f, indent=2)

        print(f"{Fore.GREEN}Successfully created SQLite index at: {index_file_path}{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
