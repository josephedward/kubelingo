"""
Path discovery utilities for YAML and SQLite data files.
"""
import os
from pathlib import Path
from typing import List, Optional

from kubelingo.utils.config import (
    QUESTION_DIRS,
    YAML_BACKUP_DIRS,
    SQLITE_BACKUP_DIRS,
    DATABASE_FILE,
)

def get_live_db_path() -> Path:
    """Return the path to the active SQLite database file."""
    return Path(DATABASE_FILE)

def get_all_question_dirs() -> List[Path]:
    """Return all candidate directories containing question YAML files."""
    dirs: List[Path] = []
    for p in QUESTION_DIRS:
        path = Path(p)
        if path.is_dir():
            dirs.append(path)
    return dirs

def find_yaml_files() -> List[Path]:
    """Recursively find all YAML files in the question directories."""
    files: List[Path] = []
    for d in get_all_question_dirs():
        files.extend(d.rglob('*.yaml'))
        files.extend(d.rglob('*.yml'))
    return files

def get_all_yaml_backup_dirs() -> List[Path]:
    """Return all candidate directories for YAML backups."""
    dirs: List[Path] = []
    for p in YAML_BACKUP_DIRS:
        path = Path(p)
        if path.is_dir():
            dirs.append(path)
    return dirs

def find_yaml_backup_files() -> List[Path]:
    """Find all YAML backup files in backup directories."""
    files: List[Path] = []
    for d in get_all_yaml_backup_dirs():
        files.extend(d.glob('*.yaml'))
        files.extend(d.glob('*.yml'))
    return files

def get_all_sqlite_backup_dirs() -> List[Path]:
    """Return all candidate directories for SQLite backups."""
    dirs: List[Path] = []
    for p in SQLITE_BACKUP_DIRS:
        path = Path(p)
        if path.is_dir():
            dirs.append(path)
    return dirs

def find_sqlite_backup_files() -> List[Path]:
    """Find all SQLite backup files in backup directories."""
    files: List[Path] = []
    for d in get_all_sqlite_backup_dirs():
        files.extend(d.glob('*.db'))
    return files

def get_latest_yaml_backup() -> Optional[Path]:
    """Return the most recently modified YAML backup file, or None if none found."""
    files = find_yaml_backup_files()
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)

def get_latest_sqlite_backup() -> Optional[Path]:
    """Return the most recently modified SQLite backup file, or None if none found."""
    files = find_sqlite_backup_files()
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)import glob
import os
from pathlib import Path
from typing import List, Optional

from .config import (
    QUESTION_DIRS,
    YAML_BACKUP_DIRS,
    SQLITE_BACKUP_DIR,
    get_live_db_path as get_live_db_path_from_config,
)


def _find_files(patterns: List[str], file_suffix: str) -> List[Path]:
    """Helper to find files matching a suffix in a list of directory patterns."""
    found_files = []
    for dir_pattern in patterns:
        # Using glob to handle potential wildcards in future directory patterns
        for directory in glob.glob(dir_pattern):
            if os.path.isdir(directory):
                path = Path(directory)
                found_files.extend(path.glob(f"**/*{file_suffix}"))
    # Return a sorted list of unique paths
    return sorted(list(set(found_files)))


def get_all_yaml_files(dirs: Optional[List[str]] = None) -> List[Path]:
    """
    Scans candidate directories for .yaml or .yml files.
    If no directories are provided, uses the default QUESTION_DIRS from config.
    """
    if dirs is None:
        dirs = get_all_question_dirs()

    yaml_files = _find_files(dirs, ".yaml")
    yml_files = _find_files(dirs, ".yml")

    return sorted(list(set(yaml_files + yml_files)))


def get_all_question_dirs() -> List[str]:
    """Returns a list of all directories that could contain YAML question files."""
    return QUESTION_DIRS


def get_all_yaml_backups() -> List[Path]:
    """Scans all configured YAML backup directories for .yaml or .yml files."""
    yaml_files = _find_files(YAML_BACKUP_DIRS, ".yaml")
    yml_files = _find_files(YAML_BACKUP_DIRS, ".yml")
    return sorted(list(set(yaml_files + yml_files)))


def get_all_sqlite_backups() -> List[Path]:
    """Scans the configured SQLite backup directory for .db files."""
    return _find_files([SQLITE_BACKUP_DIR], ".db")


def get_live_db_path() -> str:
    """Returns the path to the live user database by calling the config helper."""
    return get_live_db_path_from_config()
#!/usr/bin/env python3
"""
Utilities for discovering and resolving file paths within the project.

This module centralizes path logic, providing a resilient discovery layer that
can scan configured candidate directories for question data and backups. Scripts
and application code should use these helpers instead of hard-coding paths.
"""
import os
from pathlib import Path
from typing import List, Optional

from kubelingo.utils.config import (
    DATABASE_FILE,
    QUESTION_SOURCE_DIRS,
    YAML_BACKUP_DIRS,
    SQLITE_BACKUP_DIR,
)


def get_live_db_path() -> str:
    """Returns the absolute path to the live user database."""
    return DATABASE_FILE


def get_all_question_dirs() -> List[str]:
    """Returns a list of all configured candidate directories for question YAML files."""
    return [d for d in QUESTION_SOURCE_DIRS if os.path.isdir(d)]


def find_best_question_source() -> Optional[Path]:
    """
    Scans all candidate question directories and returns the first one
    that contains at least one YAML or YML file.
    """
    for d in get_all_question_dirs():
        p = Path(d)
        # Use iterator with next to avoid creating full lists if not needed
        has_yaml = next(p.glob('**/*.yaml'), None)
        has_yml = next(p.glob('**/*.yml'), None)
        if has_yaml or has_yml:
            return p
    return None


def get_all_yaml_backup_dirs() -> List[str]:
    """Returns a list of all configured candidate directories for YAML backups."""
    return [d for d in YAML_BACKUP_DIRS if os.path.isdir(d)]


def get_sqlite_backup_dir() -> str:
    """Returns the absolute path to the SQLite backup directory."""
    return SQLITE_BACKUP_DIR


def get_all_yaml_backups() -> List[Path]:
    """Scans all configured YAML backup directories and returns a list of all .yaml/.yml files found."""
    all_files = []
    for backup_dir in get_all_yaml_backup_dirs():
        p = Path(backup_dir)
        if p.is_dir():
            all_files.extend(p.glob("**/*.yaml"))
            all_files.extend(p.glob("**/*.yml"))
    return sorted(list(set(all_files)))


def get_all_sqlite_backups() -> List[Path]:
    """Scans the configured SQLite backup directory and returns a list of all .db files found."""
    backup_dir = Path(get_sqlite_backup_dir())
    if not backup_dir.is_dir():
        return []
    return sorted(list(backup_dir.glob("*.db")))
