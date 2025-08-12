#!/usr/bin/env python3
"""
Unified tool for managing Kubelingo SQLite databases.
Combines functionality from various scripts like index, schema, list, diff, restore, etc.
"""

import argparse
import datetime
import difflib
import hashlib
import os
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Optional

# Ensure project root on path for imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import questionary
    import yaml
except ImportError:
    print("Error: 'questionary' and 'pyyaml' packages are required.")
    print("Install with: pip install questionary pyyaml")
    sys.exit(1)

# Kubelingo imports
from kubelingo.database import add_question, get_db_connection, init_db
from kubelingo.utils.config import (
    SQLITE_BACKUP_DIRS,
    ENABLED_QUIZZES,
    YAML_BACKUP_DIRS,
    DATABASE_FILE,
)
from kubelingo.utils.path_utils import (
    find_and_sort_files_by_mtime,
    find_sqlite_files,
    get_all_sqlite_files_in_repo,
    get_live_db_path,
    find_yaml_files_from_paths,
)
from kubelingo.utils.ui import Fore, Style


# --- Indexing ---
def get_file_metadata(path: Path) -> dict:
    """Gathers metadata for a given file."""
    stat = path.stat()
    return {
        "path": str(path.relative_to(project_root)),
        "size_bytes": stat.st_size,
        "last_modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def do_index(args):
    """Finds all SQLite files and creates an index file with their metadata."""
    index_file_path = project_root / "backups" / "sqlite_index.yaml"

    default_backup = project_root / ".kubelingo" / "backups"
    if args.dirs:
        scan_dirs = args.dirs
        print(f"{Fore.CYAN}--- Indexing SQLite files in specified directories ---{Style.RESET_ALL}")
    elif SQLITE_BACKUP_DIRS:
        scan_dirs = SQLITE_BACKUP_DIRS
        print(f"{Fore.CYAN}--- Indexing SQLite files in configured backup directories ---{Style.RESET_ALL}")
    else:
        scan_dirs = None
        print(f"{Fore.CYAN}--- Indexing all SQLite files in repository ---{Style.RESET_ALL}")

    if scan_dirs:
        sqlite_files = find_sqlite_files(scan_dirs)
    else:
        sqlite_files = get_all_sqlite_files_in_repo()

    if scan_dirs:
        print("Directories scanned for SQLite files:")
        for d in scan_dirs:
            print(f"  {d}")

    all_files = sorted(list(set(sqlite_files)))

    if not all_files:
        print(f"{Fore.YELLOW}No SQLite files found to index.{Style.RESET_ALL}")
        return

    print(f"Found {len(all_files)} SQLite files to index:")
    for p in all_files:
        print(f"  {p}")

    index_data = {
        "last_updated": datetime.datetime.now().isoformat(),
        "files": [get_file_metadata(p) for p in all_files],
    }

    index_file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(index_file_path, "w") as f:
        yaml.safe_dump(index_data, f, indent=2)

    print(f"{Fore.GREEN}Successfully created SQLite index at: {index_file_path}{Style.RESET_ALL}")


# --- Schema Display ---
def do_schema(args):
    """Display the SQLite database schema."""
    db_path_str = args.db_path or DATABASE_FILE
    
    conn = get_db_connection(db_path=db_path_str)
    cursor = conn.cursor()
    cursor.execute("SELECT type, name, tbl_name, sql FROM sqlite_master WHERE sql NOT NULL ORDER BY type, name")
    rows = cursor.fetchall()
    conn.close()

    statements = [row[3].strip() + ';' for row in rows if row[3]]
    output_text = '\n\n'.join(statements)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output_text)
        print(f"Schema written to {out_path}")
    else:
        print(output_text)


# --- List Backups ---
def do_list(args):
    """Finds and displays all SQLite backup files."""
    backup_dirs = args.directories or SQLITE_BACKUP_DIRS
    if not backup_dirs:
        if not args.path_only:
            print("No SQLite backup directories are configured or provided.", file=sys.stderr)
        sys.exit(1)

    backup_files = find_sqlite_files(backup_dirs)
    if not backup_files:
        if not args.path_only:
            print("No SQLite backup files found.")
        sys.exit(1)

    sorted_files = sorted(backup_files, key=lambda p: p.stat().st_mtime, reverse=True)

    if args.path_only:
        for f in sorted_files:
            print(f)
    else:
        print(f"Searching for SQLite backup files in: {', '.join(backup_dirs)}...")
        print(f"\nFound {len(sorted_files)} backup file(s), sorted by most recent:\n")
        for f in sorted_files:
            mod_time = f.stat().st_mtime
            mod_time_str = datetime.datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  - {f} (Last modified: {mod_time_str})")


# --- Unarchive ---
def _sha256_checksum(file_path: Path, block_size=65536) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256.update(block)
    return sha256.hexdigest()

def do_unarchive(args):
    """Moves SQLite files from archive/ and prunes old databases."""
    ARCHIVE_DIR = project_root / "archive"
    DEST_DIR = project_root / ".kubelingo"
    SQLITE_EXTENSIONS = [".db", ".sqlite3"]
    MAX_DBS_TO_KEEP = 10

    if not ARCHIVE_DIR.is_dir():
        print(f"Error: Archive directory not found at '{ARCHIVE_DIR}'")
        return

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Moving SQLite files to: {DEST_DIR.relative_to(project_root)}")
    existing_hashes = {_sha256_checksum(p) for p in DEST_DIR.iterdir() if p.is_file()}
    found_files = []
    for ext in SQLITE_EXTENSIONS:
        found_files.extend(ARCHIVE_DIR.rglob(f"*{ext}"))
    if not found_files:
        print("No SQLite files found in archive directory.")
    for file_path in found_files:
        dest_path = DEST_DIR / file_path.name
        try:
            file_hash = _sha256_checksum(file_path)
            if file_hash in existing_hashes:
                print(f"Removing duplicate from archive: {file_path.relative_to(project_root)}")
                file_path.unlink()
                continue
            print(f"Moving {file_path.relative_to(project_root)} to {dest_path.relative_to(project_root)}")
            shutil.move(str(file_path), str(dest_path))
            existing_hashes.add(file_hash)
        except Exception as e:
            print(f"Error moving {file_path}: {e}")
    # Prune after moving
    print("\nPruning old SQLite databases...")
    scan_dirs = [str(DEST_DIR), str(ARCHIVE_DIR)]
    all_db_files = find_and_sort_files_by_mtime(scan_dirs, SQLITE_EXTENSIONS)
    if len(all_db_files) > MAX_DBS_TO_KEEP:
        files_to_delete = all_db_files[MAX_DBS_TO_KEEP:]
        print(f"Deleting {len(files_to_delete)} oldest files to keep {MAX_DBS_TO_KEEP} newest.")
        for file_path in files_to_delete:
            try:
                print(f"  - Deleting old database: {file_path}")
                file_path.unlink()
            except OSError as e:
                print(f"    Error deleting file {file_path}: {e}")

# --- Restore ---
def do_restore(args):
    """Restores the live database from a SQLite backup file."""
    selected_backup_path_str = args.backup_db
    if not selected_backup_path_str:
        backup_files = find_and_sort_files_by_mtime(SQLITE_BACKUP_DIRS, [".db", ".sqlite", ".sqlite3"])
        if not backup_files:
            print("No SQLite backup files found to restore from.", file=sys.stderr); sys.exit(1)
        choices = [questionary.Choice(f"{f.name} ({datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')})", value=str(f)) for f in backup_files]
        selected_backup_path_str = questionary.select("Select a backup to restore:", choices=choices).ask()
        if not selected_backup_path_str:
            print("Restore cancelled."); sys.exit(0)

    selected_backup_path = Path(selected_backup_path_str)
    if not selected_backup_path.exists():
        print(f"Error: backup file not found: {selected_backup_path}"); sys.exit(1)

    live_db_path = Path(get_live_db_path())
    print(f"\nThis will OVERWRITE the current live database:\n  {live_db_path}\nwith the contents of backup:\n  {selected_backup_path}")

    if not args.yes and not questionary.confirm("Are you sure you want to proceed?", default=False).ask():
        print("\nRestore aborted by user."); sys.exit(0)
    
    if not args.no_pre_backup:
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        pre_backup_dir = Path(args.pre_backup_dir)
        pre_backup_dir.mkdir(parents=True, exist_ok=True)
        pre_dest = pre_backup_dir / f'kubelingo_pre_restore_{timestamp}.db'
        if live_db_path.exists():
            shutil.copy(str(live_db_path), str(pre_dest))
            print(f"Pre-restore backup created: {pre_dest}")

    try:
        live_db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(selected_backup_path, live_db_path)
        print(f"\nRestore successful. '{live_db_path.name}' has been updated.")
    except Exception as e:
        print(f"\nError during restore: {e}", file=sys.stderr); sys.exit(1)


# --- Create from YAML ---
import json


class QuestionSkipped(Exception):
    def __init__(self, message: str, category: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.category = category

def _normalize_and_prepare_question_for_db(q_data, category_to_source_file, allowed_args):
    q_dict = q_data.copy()

    # Provide defaults for required fields that might be missing in YAML
    q_dict.setdefault('response', '')
    q_dict.setdefault('source', 'YAML import')
    q_dict.setdefault('raw', json.dumps(q_data))

    if "metadata" in q_dict and isinstance(q_dict.get("metadata"), dict):
        metadata = q_dict.pop("metadata")
        q_dict.update({k: v for k, v in metadata.items() if k not in q_dict})
    if "answer" in q_dict: q_dict["correct_yaml"] = q_dict.pop("answer")
    if "starting_yaml" in q_dict: q_dict["initial_files"] = {"manifest.yaml": q_dict.pop("starting_yaml")}
    if "question" in q_dict: q_dict["prompt"] = q_dict.pop("question")
    if q_dict.get("type") in ("yaml_edit", "yaml_author"):
        if "answer" in q_dict and "correct_yaml" not in q_dict: q_dict["correct_yaml"] = q_dict.pop("answer")
        if "starting_yaml" in q_dict and "initial_files" not in q_dict: q_dict["initial_files"] = {"f.yaml": q_dict.pop("starting_yaml")}
    if "type" in q_dict: q_dict["question_type"] = q_dict.pop("type")
    if "subject" in q_dict: q_dict["subject_matter"] = q_dict.pop("subject")
    q_type = q_dict.get("question_type")

    # Map schema category to 'category' column
    if q_type in ("yaml_edit", "yaml_author", "live_k8s_edit", "manifest"):
        q_dict["category"] = "manifest"
    elif q_type in ("command", "kubectl"):
        q_dict["category"] = "command"
    else:
        q_dict["category"] = "basic"

    # Map subject matter from YAML 'category' to 'subject' column
    subject = q_data.get("category")
    if not subject:
        if q_dict.get("question_type") in ("yaml_edit", "yaml_author"):
            subject = "YAML Authoring"
        elif q_dict.get("subject_matter"):
            subject = q_dict["subject_matter"]
        elif q_dict.get("source") == "AI" and q_dict.get("subject_matter"):
            subject = q_dict["subject_matter"].capitalize()

    if subject:
        q_dict['subject'] = subject

    if category_to_source_file.get(subject):
        q_dict["source_file"] = category_to_source_file[subject]
    elif not q_dict.get("source_file"):
        raise QuestionSkipped(f"Unmatched category: {subject}" if subject else "Missing category.", category=subject)

    # Clean up mapped/temporary fields
    for key in ["solution_file", "subject_matter", "type", "category_id", "subject_id"]:
        q_dict.pop(key, None)
        
    return {k: v for k, v in q_dict.items() if k in allowed_args}

def _populate_db_from_yaml(yaml_files, db_path=None):
    if not yaml_files: print("No YAML files found to process."); return
    conn = get_db_connection(db_path=db_path)
    allowed_args = {"id", "prompt", "source_file", "response", "subject", "source", "raw", "validation_steps", "validator", "review", "question_type", "category", "answers", "correct_yaml", "difficulty", "explanation", "initial_files", "pre_shell_cmds", "subject_matter", "metadata"}
    unmatched_categories, skipped_no_category, question_count = set(), 0, 0
    try:
        for file_path in yaml_files:
            print(f"  - Processing '{file_path.name}'...")
            with file_path.open("r", encoding="utf-8") as f:
                questions_data = yaml.safe_load(f)
            if not questions_data: continue
            questions_list = questions_data.get("questions") or questions_data.get("entries") if isinstance(questions_data, dict) else questions_data
            if not isinstance(questions_list, list): continue
            for q_data in questions_list:
                try:
                    q_dict_for_db = _normalize_and_prepare_question_for_db(q_data, ENABLED_QUIZZES, allowed_args)
                    add_question(conn=conn, **q_dict_for_db)
                    question_count += 1
                except QuestionSkipped as e:
                    if e.category: unmatched_categories.add(e.category)
                    else: skipped_no_category += 1
        conn.commit()
    except Exception as e:
        conn.rollback(); print(f"Error adding questions to database: {e}", file=sys.stderr); sys.exit(1)
    finally:
        conn.close()
    if unmatched_categories: print("\nWarning: Skipped questions with unmatched categories:", ", ".join(sorted(list(unmatched_categories))))
    if skipped_no_category > 0: print(f"\nWarning: Skipped {skipped_no_category} questions missing a 'category' field.")
    print(f"\nSuccessfully populated database with {question_count} questions.")

def do_create_from_yaml(args):
    """Populate the SQLite database from YAML backup files."""
    if args.yaml_files:
        yaml_files = find_yaml_files_from_paths(args.yaml_files)
    else:
        print("No input paths provided. Locating most recent YAML backup...")
        all_backups = find_and_sort_files_by_mtime(YAML_BACKUP_DIRS, extensions=[".yaml", ".yml"])
        if not all_backups: print(f"{Fore.RED}Error: No YAML backup files found.{Style.RESET_ALL}"); sys.exit(1)
        latest_backup = all_backups[0]
        print(f"Using most recent backup: {Fore.GREEN}{latest_backup}{Style.RESET_ALL}")
        yaml_files = [latest_backup]
    if not yaml_files: print("No YAML files found."); sys.exit(0)
    unique_files = sorted(list(set(yaml_files)))
    print(f"Found {len(unique_files)} YAML file(s) to process:\n" + "\n".join(f"  - {f.name}" for f in unique_files))
    db_path = args.db_path or get_live_db_path()
    init_db(clear=args.clear, db_path=db_path)
    print(f"\nPopulating database at: {db_path}")
    _populate_db_from_yaml(unique_files, db_path=db_path)

# --- Diff ---
def load_db_schema(db_path):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE sql NOT NULL ORDER BY type, name")
    stmts = [row[0].strip() + ';' for row in cursor.fetchall() if row[0]]
    conn.close()
    return stmts

def get_table_row_counts(conn: sqlite3.Connection) -> dict:
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    return {table: cursor.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables}

def do_diff(args):
    """Compares two SQLite databases."""
    db_a_path, db_b_path = None, None

    if args.db_a and args.db_b:
        db_a_path, db_b_path = Path(args.db_a), Path(args.db_b)
    else:
        # Interactive mode
        backups = find_and_sort_files_by_mtime(SQLITE_BACKUP_DIRS, [".db", ".sqlite", ".sqlite3"])
        if len(backups) < 2:
            print('Need at least two backup databases to diff.')
            return

        choices = [str(p) for p in backups]
        db_a_str = questionary.select('Select first (e.g., newer) DB:', choices).ask()
        db_b_str = questionary.select('Select second (e.g., older) DB:', choices).ask()

        if not db_a_str or not db_b_str:
            print("Diff cancelled.")
            return
        
        db_a_path, db_b_path = Path(db_a_str), Path(db_b_str)

    print(f"\nComparing:\n  (A) {db_a_path}\n  (B) {db_b_path}\n")

    if not args.no_schema:
        print("--- Schema Differences ---")
        schema_a, schema_b = load_db_schema(db_a_path), load_db_schema(db_b_path)
        diff = difflib.unified_diff(schema_a, schema_b, fromfile=str(db_a_path), tofile=str(db_b_path), lineterm='')
        diff_lines = list(diff)
        if diff_lines:
            for line in diff_lines: print(line)
        else:
            print("No schema differences found.")

    if not args.no_counts:
        print("\n--- Row Count Differences ---")
        try:
            conn_a = sqlite3.connect(f"file:{db_a_path}?mode=ro", uri=True)
            conn_b = sqlite3.connect(f"file:{db_b_path}?mode=ro", uri=True)
            counts_a, counts_b = get_table_row_counts(conn_a), get_table_row_counts(conn_b)
            conn_a.close(); conn_b.close()
            all_tables = sorted(list(set(counts_a.keys()) | set(counts_b.keys())))
            diffs = False
            for table in all_tables:
                count_a, count_b = counts_a.get(table, 'N/A'), counts_b.get(table, 'N/A')
                if count_a != count_b:
                    change = (count_a - count_b) if isinstance(count_a, int) and isinstance(count_b, int) else "N/A"
                    change_str = f"{change: d}" if isinstance(change, int) else str(change)
                    print(f"~ {table}: {count_b} -> {count_a} (Change: {change_str})"); diffs = True
            if not diffs: print("No row count differences found.")
        except sqlite3.Error as e:
            print(f"Error comparing row counts: {e}")

def main():
    parser = argparse.ArgumentParser(description="Unified tool for managing Kubelingo SQLite databases.", formatter_class=argparse.RawTextHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True, help="Sub-command to run")

    p_index = subparsers.add_parser("index", help="Index all SQLite files.")
    p_index.add_argument("dirs", nargs="*", default=[], help="Directories to scan. Scans repo if not provided.")
    p_index.set_defaults(func=do_index)

    p_schema = subparsers.add_parser("schema", help="Show SQLite DB schema.")
    p_schema.add_argument('db_path', nargs='?', default=None, help=f"Path to SQLite DB file (default: {DATABASE_FILE})")
    p_schema.add_argument('-o', '--output', type=str, help="Write schema to a file.")
    p_schema.set_defaults(func=do_schema)

    p_list = subparsers.add_parser("list", help="List SQLite backup files.")
    p_list.add_argument('directories', nargs='*', help='Directories to scan (default: configured backup dirs).')
    p_list.add_argument("--path-only", action="store_true", help="Only print file paths.")
    p_list.set_defaults(func=do_list)

    p_unarchive = subparsers.add_parser("unarchive", help="Move SQLite files from archive/ and prune.")
    p_unarchive.set_defaults(func=do_unarchive)

    p_restore = subparsers.add_parser("restore", help="Restore live DB from a backup.")
    p_restore.add_argument('backup_db', nargs='?', help='Path to backup .db file. Interactive if not provided.')
    p_restore.add_argument('--pre-backup-dir', default='backups', help='Dir for pre-restore backup.')
    p_restore.add_argument('--no-pre-backup', action='store_true', help='Skip pre-restore backup.')
    p_restore.add_argument('-y', '--yes', action='store_true', help='Skip confirmation.')
    p_restore.set_defaults(func=do_restore)

    p_create = subparsers.add_parser("create-from-yaml", help="Populate SQLite DB from YAML files.")
    p_create.add_argument("--yaml-files", nargs="*", type=str, help="YAML files. Uses latest backup if not provided.")
    p_create.add_argument("--db-path", type=str, default=None, help="Path to SQLite DB file.")
    p_create.add_argument("--clear", action="store_true", help="Clear DB before populating.")
    p_create.set_defaults(func=do_create_from_yaml)

    p_diff = subparsers.add_parser("diff", help="Diff two SQLite DBs.")
    p_diff.add_argument('db_a', nargs='?', help='First SQLite DB file. Interactive if not provided.')
    p_diff.add_argument('db_b', nargs='?', help='Second SQLite DB file. Interactive if not provided.')
    p_diff.add_argument('--no-schema', action='store_true', help='Do not compare schema.')
    p_diff.add_argument('--no-counts', action='store_true', help='Do not compare row counts.')
    p_diff.set_defaults(func=do_diff)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
