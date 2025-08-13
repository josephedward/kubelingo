#!/usr/bin/env python3
"""
A consolidated tool for managing question data and backups.
"""
import argparse
import hashlib
import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from textwrap import indent

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Please install it using: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# Add project root to path to allow importing kubelingo modules if needed
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from kubelingo.utils.config import APP_DIR
    from kubelingo.utils.path_utils import get_all_question_dirs, find_yaml_files
    from kubelingo.modules.ai_categorizer import AICategorizer
    from kubelingo.database import get_db_connection
    import sqlite3
except ImportError:
    print("Could not import kubelingo modules. Using fallbacks. AI categorization and DB updates will be disabled.", file=sys.stderr)
    APP_DIR = project_root / '.kubelingo' # fallback
    AICategorizer = None
    get_db_connection = None
    sqlite3 = None
    def get_all_question_dirs():
        q_dir = project_root / 'question-data'
        return [str(q_dir)] if q_dir.is_dir() else []
    def find_yaml_files(dirs):
        found = []
        for d in dirs:
            p = Path(d)
            if p.is_dir():
                found.extend(p.rglob("*.yaml"))
        return found


# --- SHA256 Helper ---

def sha256_checksum(file_path: Path, block_size=65536) -> str:
    """Calculates the SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256.update(block)
    return sha256.hexdigest()


# --- New Functionality: List Questions from Database ---

def list_questions():
    """
    Lists all questions stored in the database, including their metadata.
    """
    if not get_db_connection or not sqlite3:
        print("Error: Database functionality is not available.", file=sys.stderr)
        sys.exit(1)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, prompt, category, subject, source_file, created_at, updated_at
            FROM questions
            ORDER BY created_at DESC
        """)
        questions = cursor.fetchall()

        if not questions:
            print("No questions found in the database.")
            return

        print(f"{'ID':<36} {'Category':<10} {'Subject':<20} {'Source File':<40} {'Created At':<20} {'Updated At':<20}")
        print("-" * 140)
        for q in questions:
            print(f"{q['id']:<36} {q['category']:<10} {q['subject']:<20} {q['source_file']:<40} {q['created_at']:<20} {q['updated_at']:<20}")

    except sqlite3.Error as e:
        print(f"Error querying the database: {e}", file=sys.stderr)
    finally:
        if conn:
            conn.close()


# --- From consolidate_backups.py ---

def consolidate_backups():
    """
    Consolidates data files from the project into a single archive directory.
    Files are renamed using their creation timestamp to avoid name conflicts and
    provide a clear history. Duplicate files are detected and removed.
    """
    EXTENSIONS = [".db", ".sqlite3", ".yaml"]
    ARCHIVE_DIR = project_root / "archive"
    EXCLUDE_DIRS = [
        ARCHIVE_DIR.resolve(),
        (project_root / ".git").resolve(),
        (project_root / ".idea").resolve(),
        (project_root / ".vscode").resolve(),
        (project_root / "venv").resolve(),
        (project_root / ".venv").resolve(),
        (project_root / "__pycache__").resolve(),
    ]

    ARCHIVE_DIR.mkdir(exist_ok=True)
    print(f"Archive directory: {ARCHIVE_DIR}")

    existing_hashes = {
        sha256_checksum(p) for p in ARCHIVE_DIR.iterdir() if p.is_file()
    }

    found_files = []
    for ext in EXTENSIONS:
        for file_path in project_root.rglob(f"*{ext}"):
            resolved_path = file_path.resolve()

            if resolved_path == Path(__file__).resolve():
                continue

            in_excluded = False
            for excluded_dir in EXCLUDE_DIRS:
                if not excluded_dir.is_dir():
                    continue
                try:
                    resolved_path.relative_to(excluded_dir)
                    in_excluded = True
                    break
                except ValueError:
                    continue
            if in_excluded:
                continue

            found_files.append(file_path)

    for file_path in sorted(list(set(found_files))):
        try:
            file_hash = sha256_checksum(file_path)
            if file_hash in existing_hashes:
                print(
                    f"Removing duplicate: {file_path.relative_to(project_root)} is identical to a file already in archive."
                )
                file_path.unlink()
                continue
            
            try:
                stat_result = os.stat(file_path)
                creation_time = getattr(stat_result, "st_birthtime", stat_result.st_mtime)
            except AttributeError:
                creation_time = file_path.stat().st_mtime

            dt_object = datetime.fromtimestamp(creation_time)
            new_name = f"{dt_object.strftime('%Y%m%d_%H%M%S_%f')}{file_path.suffix}"
            new_path = ARCHIVE_DIR / new_name

            counter = 1
            while new_path.exists():
                new_name = f"{dt_object.strftime('%Y%m%d_%H%M%S_%f')}_{counter}{file_path.suffix}"
                new_path = ARCHIVE_DIR / new_name
                counter += 1

            print(f"Moving {file_path.relative_to(project_root)} to {new_path.relative_to(project_root)}")
            shutil.move(file_path, new_path)
            existing_hashes.add(file_hash)

        except Exception as e:
            print(f"Error processing {file_path}: {e}")


# --- Main CLI ---

parser = argparse.ArgumentParser(
    description="A consolidated tool for managing question data, manifests, and backups.",
    formatter_class=argparse.RawTextHelpFormatter
)
subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

p_backups = subparsers.add_parser("backups", help="Consolidate all data files (*.db, *.sqlite3, *.yaml) into a single archive directory.")
p_backups.set_defaults(func=consolidate_backups)

p_list_questions = subparsers.add_parser("list-questions", help="List all questions stored in the database, including metadata.")
p_list_questions.set_defaults(func=list_questions)

def main():
    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func()

if __name__ == '__main__':
    main()
