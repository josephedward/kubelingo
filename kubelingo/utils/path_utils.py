"""
Utilities for discovering and managing file paths within the project.

This module centralizes logic for finding question files, backups, and other
critical data, making scripts and the application more resilient to changes
in directory structure.
"""
import sys
from pathlib import Path
from typing import List

from kubelingo.utils.config import (
    DATABASE_FILE,
    QUESTION_DIRS,
    SQLITE_BACKUP_DIRS,
    YAML_BACKUP_DIRS,
)


def get_project_root() -> Path:
    """Returns the project root directory."""
    # Assumes this file is at kubelingo/utils/path_utils.py
    return Path(__file__).resolve().parent.parent.parent


def get_live_db_path() -> str:
    """Returns the absolute path to the live user database."""
    return DATABASE_FILE


def get_all_question_dirs() -> List[str]:
    """Returns a list of all configured directories that may contain question YAML files."""
    return QUESTION_DIRS


def get_all_yaml_backup_dirs() -> List[str]:
    """Returns a list of all configured directories for YAML backups."""
    return YAML_BACKUP_DIRS


def get_all_sqlite_backup_dirs() -> List[str]:
    """Returns a list of all configured directories for SQLite backups."""
    return SQLITE_BACKUP_DIRS


def find_yaml_files(search_dirs: List[str]) -> List[Path]:
    """
    Scans a list of directories and returns all unique .yaml/.yml files found.
    """
    yaml_files = set()
    for dir_path_str in search_dirs:
        dir_path = Path(dir_path_str)
        if dir_path.is_dir():
            yaml_files.update(dir_path.glob("**/*.yaml"))
            yaml_files.update(dir_path.glob("**/*.yml"))
    return sorted(list(yaml_files))


def find_sqlite_files(search_dirs: List[str]) -> List[Path]:
    """
    Scans a list of directories and returns all unique .db/.sqlite/.sqlite3 files found.
    """
    sqlite_files = set()
    for dir_path_str in search_dirs:
        dir_path = Path(dir_path_str)
        if dir_path.is_dir():
            sqlite_files.update(dir_path.glob("**/*.db"))
            sqlite_files.update(dir_path.glob("**/*.sqlite"))
            sqlite_files.update(dir_path.glob("**/*.sqlite3"))
    return sorted(list(sqlite_files))


def get_all_yaml_files() -> List[Path]:
    """
    Discovers all YAML files from all configured question directories.
    """
    return find_yaml_files(get_all_question_dirs())


def get_all_yaml_files_in_repo() -> List[Path]:
    """
    Discovers all YAML files from the project root.
    """
    return find_yaml_files([str(get_project_root())])


def get_all_sqlite_files_in_repo() -> List[Path]:
    """
    Discovers all SQLite database files from the project root.
    """
    return find_sqlite_files([str(get_project_root())])


def find_yaml_files_from_paths(paths: List[str]) -> List[Path]:
    """
    Scans a list of paths (files or directories) and returns all unique .yaml/.yml files found.
    """
    yaml_files = set()
    for path_str in paths:
        path = Path(path_str)
        if not path.exists():
            print(f"Warning: Path not found, skipping: {path_str}", file=sys.stderr)
            continue
        if path.is_dir():
            yaml_files.update(path.glob("**/*.yaml"))
            yaml_files.update(path.glob("**/*.yml"))
        elif path.is_file() and path.suffix.lower() in [".yaml", ".yml"]:
            yaml_files.add(path)
        else:
            print(
                f"Warning: Path is not a YAML file or directory, skipping: {path_str}",
                file=sys.stderr,
            )
    return sorted(list(yaml_files))
