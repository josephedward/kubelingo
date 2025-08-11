#!/usr/bin/env python3
"""
Finds all YAML quiz and backup files and creates an index file with their metadata.
"""
import sys
from pathlib import Path
from datetime import datetime

# Ensure the project root is on the python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.utils.path_utils import get_all_yaml_files, get_all_yaml_backups
from kubelingo.utils.ui import Fore, Style

INDEX_FILE_PATH = project_root / "backups" / "index.yaml"


def get_file_metadata(path: Path) -> dict:
    """Gathers metadata for a given file."""
    stat = path.stat()
    return {
        "path": str(path.relative_to(project_root)),
        "size_bytes": stat.st_size,
        "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def main():
    """Finds all YAML files and creates an index file with their metadata."""
    print(f"{Fore.CYAN}--- Indexing all YAML question and backup files ---{Style.RESET_ALL}")

    try:
        import yaml
    except ImportError:
        print(f"{Fore.RED}Error: PyYAML is not installed. Please install it with 'pip install pyyaml'{Style.RESET_ALL}")
        sys.exit(1)

    try:
        # According to shared_context, these functions should be available.
        # get_all_yaml_files() searches QUESTION_DIRS
        # get_all_yaml_backups() searches YAML_BACKUP_DIRS
        yaml_files = get_all_yaml_files()
        yaml_backups = get_all_yaml_backups()

        all_files = sorted(list(set(yaml_files + yaml_backups)))

        if not all_files:
            print(f"{Fore.YELLOW}No YAML files found to index.{Style.RESET_ALL}")
            return

        print(f"Found {len(all_files)} YAML files to index.")

        index_data = {
            "last_updated": datetime.now().isoformat(),
            "files": [get_file_metadata(p) for p in all_files],
        }

        # Ensure backups directory exists
        INDEX_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(INDEX_FILE_PATH, "w") as f:
            yaml.safe_dump(index_data, f, indent=2)

        print(f"{Fore.GREEN}Successfully created YAML index at: {INDEX_FILE_PATH}{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
