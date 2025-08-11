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
    return max(files, key=lambda p: p.stat().st_mtime)