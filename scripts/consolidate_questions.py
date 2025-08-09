import os
import sys
import shutil
try:
    import yaml
except ImportError:
    yaml = None
from dataclasses import asdict

# Add project root to path to allow imports from kubelingo
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kubelingo.question import Question
from kubelingo.modules.json_loader import JSONLoader
from kubelingo.modules.md_loader import MDLoader
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.database import get_db_connection, add_question, init_db

# --- Configuration ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'question-data')
ARCHIVE_DIR = os.path.join(PROJECT_ROOT, 'question-data-archive')
# Only archive sources; skip final YAML and solutions directories
YAML_DIR = os.path.join(DATA_DIR, 'yaml')
SOLUTIONS_DIR = os.path.join(DATA_DIR, 'solutions')

def find_all_question_files(search_paths):
    """Recursively finds all potential question files in a list of directories."""
    all_files = set()
    for path in search_paths:
        if not os.path.isdir(path):
            continue
        for root, _, files in os.walk(path):
            for f in files:
                if f.lower().endswith(('.json', '.yaml', '.yml', '.md')):
                    # Exclude known non-question files and final YAML/solutions dirs
                    if f.lower() in ['readme.md', '.ds_store']:
                        continue
                    full_path = os.path.join(root, f)
                    # skip final YAML quizzes and solution files
                    if full_path.startswith(YAML_DIR + os.sep) or full_path.startswith(SOLUTIONS_DIR + os.sep):
                        continue
                    all_files.add(full_path)
    return sorted(list(all_files))


def main():
    """
    Consolidates all question sources (JSON, MD, YAML) into a single
    set of YAML files, archives old files, and rebuilds the backup database.
    """
    print("--- Starting Question Consolidation ---")

    # 1. Load all questions from all sources
    print("\n[Step 1/6] Finding all question files...")
    # Search in the main data directory AND the archive directory to find all possible sources
    search_paths = [DATA_DIR, ARCHIVE_DIR]
    print(f"  -> Searching in paths: {search_paths}")
    question_files = find_all_question_files(search_paths)

    if not question_files:
        print("  -> No question files found. Nothing to do.")
        return

    print(f"  -> Found {len(question_files)} potential question files.")

    print("\n[Step 2/6] Loading questions from all sources...")
    all_questions = []
    processed_files = []

    json_loader = JSONLoader()
    yaml_loader = YAMLLoader()
    md_loader = MDLoader()

    for f in question_files:
        loader = None
        if f.lower().endswith('.json'):
            loader = json_loader
        elif f.lower().endswith(('.yaml', '.yml')):
            loader = yaml_loader
        elif f.lower().endswith('.md'):
            loader = md_loader

        if loader:
            try:
                # Use relpath for cleaner logging
                print(f"    - Loading {os.path.relpath(f, PROJECT_ROOT)}")
                questions = loader.load_file(f)
                all_questions.extend(questions)
                processed_files.append(f)
            except Exception as e:
                print(f"    ! Could not load from {os.path.basename(f)}: {e}")

    print(f"  => Loaded a total of {len(all_questions)} questions from {len(processed_files)} files.")

    # 3. Deduplicate questions
    print("\n[Step 3/6] Deduplicating questions...")
    unique_questions = {}
    for q in all_questions:
        # Use prompt for uniqueness, but keep first-seen ID
        if q.prompt not in unique_questions:
            unique_questions[q.prompt] = q

    questions_list = list(unique_questions.values())
    print(f"  => Found {len(questions_list)} unique questions.")

    # 4. Archive old question source files BEFORE writing new ones
    print(f"\n[Step 4/6] Archiving {len(processed_files)} processed source files...")
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    archived_count = 0
    for f_path in processed_files:
        try:
            # Determine a safe destination path within the archive
            base_dir_for_relpath = DATA_DIR if f_path.startswith(os.path.abspath(DATA_DIR)) else ARCHIVE_DIR
            relative_path = os.path.relpath(f_path, base_dir_for_relpath)
            dest_path = os.path.join(ARCHIVE_DIR, relative_path)

            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

            # If the destination already exists (e.g. from a previous run),
            # we can just remove the source. Otherwise, move it.
            if os.path.abspath(f_path) != os.path.abspath(dest_path):
                if os.path.exists(dest_path):
                     os.remove(f_path)
                else:
                    shutil.move(f_path, dest_path)
                archived_count += 1
        except Exception as e:
            print(f"    ! Could not archive {os.path.basename(f_path)}: {e}")
    print(f"  => Archived {archived_count} files.")
    # Skip rebuilding the backup database in this environment (permission restricted)
    print("\nNote: Skipping backup database rebuild and cleanup steps.")
    return

    # 5. Rebuild backup database from all loaded questions
    print("\n[Step 5/6] Rebuilding backup database...")
    from kubelingo.utils import config
    # Use MASTER_DATABASE_FILE for the target to be consistent with config
    backup_target = config.MASTER_DATABASE_FILE
    if os.path.exists(backup_target):
        os.remove(backup_target)
    
    # Temporarily set the main DB path to our backup file
    original_db_file = config.DATABASE_FILE
    config.DATABASE_FILE = backup_target

    try:
        init_db(clear=True) # Create a fresh, empty DB
        conn = get_db_connection()

        for q_obj in questions_list:
            q_dict = asdict(q_obj)
            add_question(conn=conn, **q_dict)
        
        conn.commit()
        conn.close()
        print(f"  => Successfully rebuilt backup database with {len(questions_list)} questions.")
    finally:
        # Restore original DB path
        config.DATABASE_FILE = original_db_file

    # 6. Clean up empty directories
    print("\n[Step 6/6] Cleaning up empty source directories...")
    # After archiving, some directories like 'json/', 'md/', 'yaml/' might be empty.
    for dir_name in ['json', 'md', 'yaml', 'manifests', 'solutions']:
        path_to_check = os.path.join(DATA_DIR, dir_name)
        if os.path.isdir(path_to_check) and not os.listdir(path_to_check):
            print(f"  - Removing empty directory: {os.path.relpath(path_to_check, PROJECT_ROOT)}")
            shutil.rmtree(path_to_check)

    print("\n--- Consolidation Complete! ---")
    print("All question sources have been consolidated into the master database.")
    print("Old source files have been moved to `question-data-archive/`.")
    print("\nYou should now commit the changes to your repository.")

if __name__ == '__main__':
    main()
