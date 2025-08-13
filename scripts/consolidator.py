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
except ImportError:
    print("Could not import kubelingo modules. Using fallbacks. AI categorization will be disabled.", file=sys.stderr)
    APP_DIR = project_root / '.kubelingo' # fallback
    AICategorizer = None
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


# --- From consolidate_dbs.py ---

def consolidate_dbs():
    """
    Move and rename all database files into a single directory (APP_DIR),
    using each file's creation timestamp for a unified filename, and
    deduplicate identical files by content hash.
    """
    dest_dir = Path(APP_DIR)
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating directory {dest_dir}: {e}", file=sys.stderr)
        sys.exit(1)

    sources = []
    sources.extend([
        Path(APP_DIR) / 'kubelingo.db',
        project_root / 'backup_questions.db',
        project_root / 'categorized.db',
    ])
    sqlite_dir = project_root / 'backups' / 'sqlite'
    if sqlite_dir.is_dir():
        sources.extend(sqlite_dir.glob('*.sqlite3'))

    sources = [p for p in sources if p.is_file()]
    if not sources:
        print("No database files found to consolidate.")
        return

    by_hash = {}
    for p in sources:
        h = sha256_checksum(p)
        st = p.stat()
        ctime = getattr(st, 'st_birthtime', None) or st.st_mtime
        if h not in by_hash or ctime > by_hash[h][0]:
            by_hash[h] = (ctime, p)

    for ctime, p in sorted(by_hash.values(), reverse=True):
        ts_obj = datetime.fromtimestamp(ctime)
        # Add microseconds for uniqueness
        ts_str = ts_obj.strftime('%Y%m%d_%H%M%S_%f')
        new_name = f"kubelingo_db_{ts_str}.db"
        dst = dest_dir / new_name

        # Handle rare filename collisions
        counter = 1
        while dst.exists():
            new_name = f"kubelingo_db_{ts_str}_{counter}.db"
            dst = dest_dir / new_name
            counter += 1

        try:
            p.rename(dst)
            print(f"Moved {p} -> {dst}")
        except Exception as e:
            print(f"Failed to move {p} -> {dst}: {e}", file=sys.stderr)

    yaml_dirs = get_all_question_dirs()
    yaml_files = find_yaml_files(yaml_dirs)
    removed = 0
    if yaml_files:
        for yf in yaml_files:
            try:
                docs = list(yaml.load_all(yf.read_text(encoding='utf-8'), Loader=yaml.UnsafeLoader))
            except Exception:
                continue
            if docs and isinstance(docs[-1], dict) and list(docs[-1].keys()) == ['entries'] and docs[-1].get('entries') == []:
                try:
                    yf.unlink()
                    print(f"Deleted empty YAML: {yf}")
                    removed += 1
                except Exception as e:
                    print(f"Failed to delete {yf}: {e}", file=sys.stderr)
        if removed:
            print(f"Removed {removed} empty YAML file(s).")

    pattern = "kubelingo_db_*.db"
    all_backups = list(dest_dir.glob(pattern))
    if len(all_backups) > 10:
        sorted_backups = sorted(all_backups, key=lambda p: p.stat().st_mtime, reverse=True)
        to_remove = sorted_backups[10:]
        for old in to_remove:
            try:
                old.unlink()
                print(f"Removed old backup: {old}")
            except Exception as e:
                print(f"Failed to remove {old}: {e}", file=sys.stderr)


# --- From consolidate_manifests.py ---

def consolidate_manifests():
    """
    Consolidate all manifest-based YAML quizzes into a single file.
    """
    archive_dir = project_root / 'question-data' / 'archive' / 'manifests'
    if not archive_dir.exists():
        sys.stderr.write(f"Archive manifests dir not found: {archive_dir}\n")
        sys.exit(1)
    all_questions = []
    for manifest_file in sorted(archive_dir.glob('*.yaml')):
        try:
            docs = list(yaml.load_all(manifest_file.read_text(encoding='utf-8'), Loader=yaml.UnsafeLoader))
        except Exception as e:
            sys.stderr.write(f"Failed to parse {manifest_file}: {e}\n")
            continue
        for doc in docs:
            if isinstance(doc, list):
                all_questions.extend(doc)
            elif isinstance(doc, dict) and 'questions' in doc:
                all_questions.extend(doc['questions'])
            elif isinstance(doc, dict) and 'id' in doc:
                all_questions.append(doc)
    if not all_questions:
        print("No manifest quizzes found to consolidate.")
        return
    dest_dir = project_root / 'question-data' / 'yaml'
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_file = dest_dir / 'manifests_quiz.yaml'
    try:
        with open(out_file, 'w', encoding='utf-8') as f:
            yaml.safe_dump(all_questions, f, sort_keys=False)
        print(f"Consolidated {len(all_questions)} manifest questions into {out_file.relative_to(project_root)}")
    except Exception as e:
        sys.stderr.write(f"Failed to write {out_file}: {e}\n")


# --- From merge_quizzes.py ---

def merge_quizzes(source: str, destination: str, delete_source: bool):
    """Merge questions from a source YAML file into a destination YAML file."""
    if not os.path.exists(source):
        print(f"Error: Source file not found at '{source}'")
        sys.exit(1)
        
    dest_dir = os.path.dirname(destination)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    try:
        with open(source, 'r', encoding='utf-8') as f:
            source_questions = yaml.load(f, Loader=yaml.UnsafeLoader) or []

        if os.path.exists(destination):
            with open(destination, 'r', encoding='utf-8') as f:
                dest_questions = yaml.load(f, Loader=yaml.UnsafeLoader) or []
        else:
            print(f"Warning: Destination file '{destination}' not found. It will be created.")
            dest_questions = []

        if not isinstance(source_questions, list) or not isinstance(dest_questions, list):
            print("Error: Both source and destination files must contain a YAML list of questions.")
            sys.exit(1)

        print(f"Found {len(source_questions)} questions in source file.")
        print(f"Found {len(dest_questions)} questions in destination file.")

        seen_ids = {q.get('id') for q in dest_questions if q.get('id')}
        
        new_questions_added = 0
        for q in source_questions:
            q_id = q.get('id')
            if q_id and q_id not in seen_ids:
                dest_questions.append(q)
                seen_ids.add(q_id)
                new_questions_added += 1
            elif not q_id:
                dest_questions.append(q)
                new_questions_added += 1

        if new_questions_added > 0:
            print(f"Adding {new_questions_added} new unique questions to destination file.")
            with open(destination, 'w', encoding='utf-8') as f:
                yaml.safe_dump(dest_questions, f, default_flow_style=False, sort_keys=False, indent=2)
            print(f"Successfully merged questions into '{destination}'.")
        else:
            print("No new unique questions to merge.")

        if delete_source and new_questions_added > 0:
            os.remove(source)
            print(f"Successfully deleted source file '{source}'.")

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


# --- From merge_solutions.py ---

def _consolidate_category(category_dir: Path):
    entries = {}
    for file_path in sorted(category_dir.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in ('.sh', '.yaml', '.yml'):
            continue
        key = file_path.stem
        try:
            entries[key] = file_path.read_text(encoding='utf-8')
        except Exception as e:
            sys.stderr.write(f"Failed to read {file_path}: {e}\n")
    if not entries:
        return
    out_file = category_dir / f"{category_dir.name}_solutions.yaml"
    try:
        with open(out_file, 'w', encoding='utf-8') as wf:
            for key, content in entries.items():
                wf.write(f"{key}: |-\n")
                wf.write(indent(content.rstrip('\n'), '  '))
                wf.write("\n\n")
        print(f"Consolidated {len(entries)} files into {out_file.relative_to(Path.cwd())}")
    except Exception as e:
        sys.stderr.write(f"Failed to write {out_file}: {e}\n")

def merge_solutions():
    """
    Merge individual solution scripts into a single YAML file per category.
    """
    sol_root = project_root / 'question-data' / 'yaml' / 'solutions'
    if not sol_root.is_dir():
        sys.stderr.write(f"Solutions directory not found: {sol_root}\n")
        sys.exit(1)
    for category_dir in sorted(sol_root.iterdir()):
        if category_dir.is_dir():
            _consolidate_category(category_dir)


def organize_ai_questions(source_dir_path: str, dest_dir_path: str, delete_source: bool):
    """
    Organizes individual AI-generated YAML question files into subject-specific files.
    """
    source_dir = Path(source_dir_path)
    dest_dir = Path(dest_dir_path)

    if not source_dir.is_dir():
        print(f"Error: Source directory not found: {source_dir}", file=sys.stderr)
        sys.exit(1)

    dest_dir.mkdir(parents=True, exist_ok=True)

    categorizer = AICategorizer() if 'AICategorizer' in globals() and AICategorizer else None
    if categorizer:
        print("AI categorizer loaded. Will attempt to categorize questions without a subject.")

    yaml_files = list(source_dir.glob("*.yaml"))
    if not yaml_files:
        print(f"No YAML files found in {source_dir}")
        return

    print(f"Found {len(yaml_files)} YAML files to organize.")

    # Step 1: Group all questions by subject from all source files.
    questions_by_subject = defaultdict(list)
    total_questions_processed = 0
    processed_files = []
    for file_path in yaml_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                questions = yaml.load(f, Loader=yaml.UnsafeLoader) or []
                if not isinstance(questions, list):
                    if isinstance(questions, dict):
                        questions = [questions]
                    else:
                        print(f"Warning: Skipping {file_path.name}, content is not a list or dict.")
                        continue

            for question in questions:
                total_questions_processed += 1
                if not isinstance(question, dict):
                    continue

                subject = question.get("subject")
                if not subject and categorizer:
                    try:
                        ai_cats = categorizer.categorize_question(question)
                        if ai_cats:
                            subject = ai_cats.get("subject_matter")
                            print(f"  Categorized question {question.get('id', '')} as '{subject}'")
                    except Exception as e:
                        print(f"AI categorization failed for question {question.get('id', 'N/A')}: {e}", file=sys.stderr)

                subject = subject or "general"
                questions_by_subject[subject].append(question)
            processed_files.append(file_path)
        except Exception as e:
            print(f"Error processing {file_path}: {e}", file=sys.stderr)

    print(f"\nProcessed {total_questions_processed} questions into {len(questions_by_subject)} subjects.")

    # Step 2: Write out the consolidated files.
    organized_count = 0
    for subject, new_questions in questions_by_subject.items():
        # Sanitize subject to create a valid filename
        filename_subject = subject.lower().replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")
        filename_subject = ''.join(c for c in filename_subject if c.isalnum() or c == '_')
        dest_filepath = dest_dir / f"ai_generated_{filename_subject}.yaml"

        existing_questions = []
        if dest_filepath.exists():
            with open(dest_filepath, 'r', encoding='utf-8') as f_read:
                try:
                    docs = list(yaml.load_all(f_read, Loader=yaml.UnsafeLoader))
                    for doc in docs:
                        if isinstance(doc, list):
                            existing_questions.extend(doc)
                except yaml.YAMLError:
                    print(f"Warning: Could not parse existing file {dest_filepath}, it may be overwritten.")

        existing_ids = {q.get('id') for q in existing_questions if q.get('id')}
        questions_to_add = []
        for question in new_questions:
            q_id = question.get('id')
            if not q_id or q_id not in existing_ids:
                questions_to_add.append(question)
                if q_id:
                    existing_ids.add(q_id)

        if not questions_to_add:
            continue

        all_questions_for_file = existing_questions + questions_to_add
        organized_count += len(questions_to_add)

        with open(dest_filepath, 'w', encoding='utf-8') as f_write:
            yaml.dump(all_questions_for_file, f_write, default_flow_style=False, sort_keys=False)

    print(f"\nSuccessfully organized {organized_count} new questions.")

    # Step 3: Delete source files if requested.
    if delete_source:
        for file_path in processed_files:
            file_path.unlink()
        print(f"Deleted {len(processed_files)} source files.")


# --- Main CLI ---

parser = argparse.ArgumentParser(
    description="A consolidated tool for managing question data, manifests, and backups.",
    formatter_class=argparse.RawTextHelpFormatter
)
subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

p_backups = subparsers.add_parser("backups", help="Consolidate all data files (*.db, *.sqlite3, *.yaml) into a single archive directory.")
p_backups.set_defaults(func=consolidate_backups)

p_dbs = subparsers.add_parser("dbs", help="Consolidate and manage database files in the application directory.")
p_dbs.set_defaults(func=consolidate_dbs)

p_manifests = subparsers.add_parser("manifests", help="Consolidate all manifest-based YAML quizzes into a single file.")
p_manifests.set_defaults(func=consolidate_manifests)

p_merge_quizzes = subparsers.add_parser("merge-quizzes", help="Merge questions from one YAML file to another.")
p_merge_quizzes.add_argument("--source", required=True, help="Path to the source YAML file to merge from.")
p_merge_quizzes.add_argument("--destination", required=True, help="Path to the destination YAML file to merge into.")
p_merge_quizzes.add_argument("--delete-source", action="store_true", help="Delete the source file after a successful merge.")
p_merge_quizzes.set_defaults(func=lambda args: merge_quizzes(args.source, args.destination, args.delete_source))

p_merge_solutions = subparsers.add_parser("merge-solutions", help="Merge individual solution files into a single YAML per category.")
p_merge_solutions.set_defaults(func=merge_solutions)

p_organize = subparsers.add_parser("organize-ai-questions", help="Organize individual AI-generated questions into subject-based files.")
p_organize.add_argument("--source-dir", default="yaml", help="Directory containing the individual question files.")
p_organize.add_argument("--dest-dir", default="question-data/yaml", help="Directory to save the consolidated subject-based files.")
p_organize.add_argument("--delete-source", action="store_true", help="Delete the source files after organizing them.")
p_organize.set_defaults(func=lambda args: organize_ai_questions(args.source_dir, args.dest_dir, args.delete_source))

def main():
    args = parser.parse_args()
    if hasattr(args, 'func'):
        if args.command in ('merge-quizzes', 'organize-ai-questions'):
            args.func(args)
        else:
            args.func()

if __name__ == '__main__':
    main()
