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
from dataclasses import asdict

from kubelingo.database import add_question, get_all_questions, get_db_connection, init_db
from kubelingo.modules.db_loader import DBLoader
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.question import Question
from kubelingo.utils.config import (
    BACKUP_DATABASE_FILE,
    DATABASE_FILE,
    DATA_DIR,
    ENABLED_QUIZZES,
    MASTER_DATABASE_FILE,
    QUESTIONS_DIR,
    SECONDARY_MASTER_DATABASE_FILE,
    SQLITE_BACKUP_DIRS,
    YAML_BACKUP_DIRS,
)
from kubelingo.utils.path_utils import (
    find_and_sort_files_by_mtime,
    find_sqlite_files,
    find_yaml_files,
    find_yaml_files_from_paths,
    get_all_sqlite_files_in_repo,
    get_live_db_path,
)
from kubelingo.utils.ui import Fore, Style


# --- Migrate from YAML ---
def do_migrate_from_yaml(args):
    """Migrates questions from YAML files to the SQLite database."""
    print("Initializing database...")
    init_db(clear=args.clear)
    if args.clear:
        print("Database cleared and re-initialized.")
    else:
        print("Database initialized.")

    yaml_loader = YAMLLoader()
    total_questions = 0

    yaml_files = []
    if args.file:
        p = Path(args.file)
        if p.exists():
            yaml_files.append(str(p))
        else:
            print(f"Error: File not found at '{args.file}'")
            return
    else:
        source_paths = []
        if args.source_dirs:
            for d in args.source_dirs:
                p = Path(d)
                if p.is_dir():
                    source_paths.append(p)
                else:
                    print(f"Warning: Provided source directory not found, skipping: {d}")
        else:
            # Default directories, as per documentation
            for subdir in ('yaml', 'yaml-bak', 'manifests'):
                source_paths.append(Path(DATA_DIR) / subdir)

        for quiz_dir in source_paths:
            print(f"Scanning quiz directory: {quiz_dir}")
            if not quiz_dir.is_dir():
                continue
            for pattern in ('*.yaml', '*.yml', '*.yaml.bak'):
                for p in quiz_dir.glob(pattern):
                    yaml_files.append(str(p))

    yaml_files = sorted(list(set(yaml_files)))  # de-duplicate and sort

    print(f"Found {len(yaml_files)} unique YAML quiz files to migrate.")

    for file_path in yaml_files:
        print(f"Processing {file_path}...")
        try:
            # Load questions as objects for structured data
            questions_obj: list[Question] = yaml_loader.load_file(file_path)
            
            # Load raw data to get attributes not on the Question dataclass, like 'review'
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_questions_data = yaml.safe_load(f)
            raw_q_map = {
                item.get('id'): item for item in raw_questions_data if isinstance(item, dict)
            }

            for q in questions_obj:
                raw_q_data = raw_q_map.get(q.id, {})
                q_data = {
                    'id': q.id,
                    'prompt': q.prompt,
                    'response': q.response,
                    'category': q.category,
                    'source': getattr(q, 'source', None),
                    'validation_steps': [asdict(step) for step in q.validation_steps],
                    'validator': q.validator,
                    'source_file': os.path.basename(file_path),
                    'review': raw_q_data.get('review', False),
                    'explanation': getattr(q, 'explanation', None)
                }
                add_question(**q_data)
            total_questions += len(questions_obj)
            print(f"  Migrated {len(questions_obj)} questions.")
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")

    print(f"\nMigration complete. Total questions migrated: {total_questions}")

    # Create a backup of the newly migrated database, clearly named in the repo
    try:
        backup_dir = os.path.dirname(BACKUP_DATABASE_FILE)
        os.makedirs(backup_dir, exist_ok=True)
        # Copy the active user DB (~/.kubelingo/kubelingo.db) into project backup
        shutil.copy2(DATABASE_FILE, BACKUP_DATABASE_FILE)
        print(f"Created a backup of the questions database at: {BACKUP_DATABASE_FILE}")
    except Exception as e:
        print(f"Could not create database backup: {e}")


# --- Normalize Source Paths ---
def do_normalize_sources(args):
    """Normalizes `source_file` to be just the basename."""
    db_path = args.db_path or get_live_db_path()
    # Connect to the questions database
    conn = get_db_connection(db_path=db_path)
    cursor = conn.cursor()
    # Fetch all current source_file values
    cursor.execute("SELECT id, source_file FROM questions")
    rows = cursor.fetchall()
    updated = 0
    for qid, src in rows:
        # Compute normalized basename
        base = os.path.basename(src) if src else src
        if base and base != src:
            cursor.execute(
                "UPDATE questions SET source_file = ? WHERE id = ?",
                (base, qid)
            )
            updated += 1
    conn.commit()
    conn.close()
    print(f"Updated {updated} source_file entries in {db_path}")


# --- List DB Modules ---
def do_list_modules(args):
    """Lists all quiz modules currently stored in the Kubelingo SQLite DB."""
    loader = DBLoader()
    modules = loader.discover()
    if not modules:
        print("No quiz modules found in the DB.")
        return
    print("Available DB quiz modules (module_name: question count):")
    for sf in modules:
        name, _ = os.path.splitext(sf)
        # Count questions in each module
        try:
            qs = loader.load_file(sf)
            count = len(qs)
        except Exception:
            count = 'error'
        print(f" - {name}: {count}")


# --- Prune Empty DBs ---
def is_db_empty(db_path: Path) -> bool:
    """Checks if a SQLite database is empty by looking for user-created tables."""
    if db_path.stat().st_size == 0:
        return True

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        tables = cursor.fetchall()
        return len(tables) == 0
    except sqlite3.DatabaseError:
        print(f"Warning: Could not open '{db_path.relative_to(project_root)}' as a database. Skipping.")
        return False
    finally:
        if conn:
            conn.close()

def do_prune_empty(args):
    """Scans configured directories for SQLite files and removes any that are empty."""
    SCAN_DIRS = [
        project_root / ".kubelingo",
        project_root / "archive",
    ]
    SQLITE_EXTENSIONS = [".db", ".sqlite3"]

    print("Scanning for and removing empty databases...")
    deleted_count = 0
    for scan_dir in SCAN_DIRS:
        if not scan_dir.is_dir():
            continue

        print(f"-> Scanning directory: {scan_dir.relative_to(project_root)}")
        found_files = []
        for ext in SQLITE_EXTENSIONS:
            found_files.extend(scan_dir.rglob(f"*{ext}"))

        if not found_files:
            print("  No SQLite files found.")
            continue

        for file_path in found_files:
            if is_db_empty(file_path):
                print(f"  - Deleting empty database: {file_path.relative_to(project_root)}")
                try:
                    file_path.unlink()
                    deleted_count += 1
                except OSError as e:
                    print(f"    Error deleting file: {e}")

    print(f"\nScan complete. Deleted {deleted_count} empty database(s).")


# --- Fix Source Paths ---
def do_fix_sources(args):
    """Ensures source_file paths in the database match the canonical paths in ENABLED_QUIZZES."""
    print("Fixing source_file paths in the database...")
    db_path = args.db_path or get_live_db_path()
    conn = get_db_connection(db_path=db_path)

    all_questions = get_all_questions(conn)
    if not all_questions:
        print("No questions found in the database.")
        conn.close()
        return

    category_to_source_file = ENABLED_QUIZZES
    allowed_args = {
        "id", "prompt", "source_file", "response", "category", "source",
        "validation_steps", "validator", "review", "question_type",
        "schema_category", "answers", "correct_yaml", "difficulty",
        "explanation", "initial_files", "pre_shell_cmds", "subject_matter",
        "metadata",
    }

    updated_count = 0
    try:
        for q_dict in all_questions:
            category = q_dict.get("category")
            if not category:
                continue

            correct_source_file = category_to_source_file.get(category)
            if not correct_source_file:
                continue

            if q_dict.get("source_file") != correct_source_file:
                q_dict["source_file"] = correct_source_file
                q_dict_for_db = {k: v for k, v in q_dict.items() if k in allowed_args}
                add_question(conn=conn, **q_dict_for_db)
                updated_count += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error updating source files: {e}", file=sys.stderr)
    finally:
        conn.close()

    print(f"Finished. Updated {updated_count} question(s).")


# --- Build Master DB ---
def import_questions_for_master(files: list[Path], conn: sqlite3.Connection):
    """Loads all questions from a list of YAML file paths and adds them to the database."""
    print(f"Importing from {len(files)} found YAML files...")

    question_count = 0
    for file_path in files:
        print(f"  - Processing '{file_path.name}'...")
        with open(file_path, 'r', encoding='utf-8') as f:
            questions_data = yaml.safe_load(f)
            if not questions_data:
                continue
            for q_dict in questions_data:
                if 'metadata' in q_dict and isinstance(q_dict['metadata'], dict):
                    metadata = q_dict.pop('metadata')
                    metadata.pop('links', None)
                    for k, v in metadata.items():
                        if k not in q_dict:
                            q_dict[k] = v

                if 'category' in q_dict:
                    q_dict['subject_matter'] = q_dict.pop('category')

                q_type = q_dict.get('type', 'command')
                if q_type in ('yaml_edit', 'yaml_author', 'live_k8s_edit'):
                    schema_cat = 'manifest'
                elif q_type == 'socratic':
                    schema_cat = 'basic'
                else:  # command, etc.
                    schema_cat = 'command'
                q_dict['schema_category'] = schema_cat
                q_dict['category'] = schema_cat

                if 'type' in q_dict:
                    q_dict['question_type'] = q_dict.pop('type')
                else:
                    q_dict['question_type'] = q_type
                if 'answer' in q_dict:
                    q_dict['response'] = q_dict.pop('answer')

                q_dict['source_file'] = file_path.name
                links = q_dict.pop('links', None)
                if links:
                    metadata = q_dict.get('metadata')
                    if not isinstance(metadata, dict):
                        metadata = {}
                    metadata['links'] = links
                    q_dict['metadata'] = metadata
                add_question(conn=conn, **q_dict)
                question_count += 1
    print(f"\nImport complete. Added/updated {question_count} questions.")
    return question_count

def backup_live_to_master(source_db_path: str):
    """Backs up the given database to create the master copies."""
    live_db_path = Path(source_db_path)
    backup_master_path = Path(MASTER_DATABASE_FILE)
    backup_secondary_path = Path(SECONDARY_MASTER_DATABASE_FILE)

    if not live_db_path.exists():
        print(f"Error: Database not found at '{live_db_path}'. Cannot create backup.")
        return

    print(f"\nBacking up database from '{live_db_path}'...")
    backup_master_path.parent.mkdir(exist_ok=True)
    shutil.copy(live_db_path, backup_master_path)
    print(f"  - Created primary master backup: '{backup_master_path}'")
    shutil.copy(live_db_path, backup_secondary_path)
    print(f"  - Created secondary master backup: '{backup_secondary_path}'")
    print("\nBackup complete.")

def do_build_master(args):
    """Builds the Kubelingo master question database from consolidated YAML files."""
    print("--- Building Kubelingo Master Question Database ---")

    print(f"\nScanning for YAML files in: '{QUESTIONS_DIR}'")
    if not os.path.isdir(QUESTIONS_DIR):
        print(f"\nError: The configured questions directory does not exist: '{QUESTIONS_DIR}'")
        sys.exit(1)

    all_yaml_files = find_yaml_files([QUESTIONS_DIR])
    if not all_yaml_files:
        print(f"\nError: No question YAML files found in '{QUESTIONS_DIR}'.")
        sys.exit(1)

    print(f"Found {len(all_yaml_files)} YAML file(s) to process.")

    db_path = args.db_path or DATABASE_FILE
    print(f"\nStep 1: Preparing live database at '{db_path}'...")
    init_db(db_path=db_path, clear=True)
    print("  - Cleared and initialized database for build.")

    print(f"\nStep 2: Importing questions from all found YAML files...")
    questions_imported = 0
    conn = get_db_connection(db_path=db_path)
    try:
        questions_imported = import_questions_for_master(all_yaml_files, conn)
    finally:
        conn.close()

    if questions_imported > 0:
        print(f"\nStep 3: Creating master database backups...")
        backup_live_to_master(db_path)
    else:
        print("\nNo questions were imported. Skipping database backup.")

    print("\n--- Build process finished. ---")


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

    p_migrate = subparsers.add_parser("migrate-from-yaml", help="Migrate questions from YAML files to DB.")
    p_migrate.add_argument("--file", help="Path to a specific YAML file to migrate.")
    p_migrate.add_argument("--source-dir", action="append", dest="source_dirs", help="Specific directory to scan for YAML files.")
    p_migrate.add_argument("--clear", action="store_true", help="Clear the existing database before migrating.")
    p_migrate.set_defaults(func=do_migrate_from_yaml)

    p_normalize = subparsers.add_parser("normalize-sources", help="Normalize source_file paths in DB to basenames.")
    p_normalize.add_argument("--db-path", type=str, default=None, help="Path to the SQLite database file.")
    p_normalize.set_defaults(func=do_normalize_sources)

    p_list_modules = subparsers.add_parser("list-modules", help="List all quiz modules in the DB.")
    p_list_modules.set_defaults(func=do_list_modules)

    p_prune = subparsers.add_parser("prune-empty", help="Scan for and remove empty database files.")
    p_prune.set_defaults(func=do_prune_empty)

    p_fix = subparsers.add_parser("fix-sources", help="Fix source_file paths based on question category.")
    p_fix.add_argument("--db-path", type=str, default=None, help="Path to SQLite DB. Uses live DB if not set.")
    p_fix.set_defaults(func=do_fix_sources)

    p_build = subparsers.add_parser("build-master", help="Build master question DB from YAML files.")
    p_build.add_argument("--db-path", type=str, default=None, help="Path to build DB in. Defaults to live DB path.")
    p_build.set_defaults(func=do_build_master)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
