import os
import shutil
import argparse
import json
import logging
from pathlib import Path
import sys
import re

# Determine project root directory and ensure local modules are importable
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# --- Constants ---
QUESTION_DATA_DIR = project_root / 'question-data'
ARCHIVE_DIR = QUESTION_DATA_DIR / '_archive'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- File Operations ---

def _move_to_archive(src_path, dry_run=False):
    if not src_path.exists():
        return
    dest_path = ARCHIVE_DIR / src_path.name
    logging.info(f"Archiving '{src_path}' to '{dest_path}'")
    if not dry_run:
        shutil.move(str(src_path), str(dest_path))

def organize_files(dry_run=False):
    """Organizes question data files as per the project specification."""
    logging.info("--- Starting file organization ---")
    if not dry_run:
        ARCHIVE_DIR.mkdir(exist_ok=True)

    # 1. Archive legacy stub files
    legacy_files = [
        "ckad_questions.yml",
        "killercoda_ckad_all.json", "killercoda_ckad_all.csv"
    ]
    for filename in legacy_files:
        _move_to_archive(QUESTION_DATA_DIR / "json" / filename, dry_run)
        _move_to_archive(QUESTION_DATA_DIR / "yaml" / filename, dry_run)
        _move_to_archive(QUESTION_DATA_DIR / "csv" / filename, dry_run)
        _move_to_archive(QUESTION_DATA_DIR / filename, dry_run)


    # 2. Strip prefixes from markdown files
    md_dir = QUESTION_DATA_DIR / "md"
    if md_dir.exists():
        for md_file in md_dir.glob("*.md"):
            if re.match(r'^[a-z]\.', md_file.name):
                new_name = re.sub(r'^[a-z]\.', '', md_file.name)
                new_path = md_dir / new_name
                logging.info(f"Renaming '{md_file.name}' to '{new_name}'")
                if not dry_run:
                    md_file.rename(new_path)

    # 3. Rename core JSON quizzes
    json_dir = QUESTION_DATA_DIR / "json"
    if json_dir.exists():
        rename_map = {
            "ckad_quiz_data.json": "kubernetes.json",
            "ckad_quiz_data_with_explanations.json": "kubernetes_with_explanations.json",
            "yaml_edit_questions.json": "yaml_edit.json",
            "vim_quiz_data.json": "vim.json"
        }
        for old_name, new_name in rename_map.items():
            old_path = json_dir / old_name
            new_path = json_dir / new_name
            if old_path.exists():
                logging.info(f"Renaming '{old_name}' to '{new_name}'")
                if not dry_run:
                    old_path.rename(new_path)

    # 4. Clean up empty subdirectories
    for subdir in QUESTION_DATA_DIR.iterdir():
        if subdir.is_dir() and not any(subdir.iterdir()) and subdir.name != '_archive':
            logging.info(f"Removing empty directory: '{subdir}'")
            if not dry_run:
                try:
                    shutil.rmtree(subdir)
                except OSError:
                    pass

    logging.info("--- File organization complete ---")

def main():
    parser = argparse.ArgumentParser(description="Organize Kubelingo question data files.")
    parser.add_argument('--dry-run', action='store_true', help="Show what would be done, but don't make any changes.")
    args = parser.parse_args()
    organize_files(dry_run=args.dry_run)

if __name__ == "__main__":
    main()
