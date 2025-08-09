import os
import sys
import shutil
import yaml
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
DATA_DIR = os.path.join(PROJECT_ROOT, 'kubelingo', 'question-data')
ARCHIVE_DIR = os.path.join(PROJECT_ROOT, 'kubelingo', 'question-data-archive')
YAML_DIR = os.path.join(DATA_DIR, 'yaml')
JSON_DIR = os.path.join(DATA_DIR, 'json')
MD_DIR = os.path.join(DATA_DIR, 'md')
MANIFESTS_DIR = os.path.join(DATA_DIR, 'manifests')
SOLUTIONS_DIR = os.path.join(DATA_DIR, 'solutions')

BACKUP_DB_DIR = os.path.join(PROJECT_ROOT, 'kubelingo', 'question-data-backup')
BACKUP_DB_FILE = os.path.join(BACKUP_DB_DIR, 'kubelingo_original.db')

def main():
    """
    Consolidates all question sources (JSON, MD, YAML) into a single
    set of YAML files, archives old files, and rebuilds the backup database.
    """
    print("--- Starting Question Consolidation ---")

    # 1. Load all questions from all sources
    print("\n[Step 1/5] Loading questions from all sources...")
    all_questions = []
    loaders = {
        'JSON': (JSONLoader(), JSON_DIR),
        'YAML': (YAMLLoader(), YAML_DIR),
        'Manifests(YAML)': (YAMLLoader(), MANIFESTS_DIR),
        'MD': (MDLoader(), MD_DIR),
    }

    for name, (loader, path) in loaders.items():
        if not os.path.isdir(path):
            continue
        print(f"  -> Searching in {name} directory: {path}")
        try:
            files = loader.discover()
            for f in files:
                if os.path.basename(f) in ['README.md']: continue
                print(f"    - Loading {os.path.basename(f)}")
                questions = loader.load_file(f)
                all_questions.extend(questions)
        except Exception as e:
            print(f"    Could not load from {name} loader: {e}")

    print(f"  => Loaded a total of {len(all_questions)} questions.")

    # 2. Deduplicate questions
    print("\n[Step 2/5] Deduplicating questions...")
    unique_questions = {}
    for q in all_questions:
        # Use prompt for uniqueness, but keep first-seen ID
        if q.prompt not in unique_questions:
            unique_questions[q.prompt] = q

    questions_list = list(unique_questions.values())
    print(f"  => Found {len(questions_list)} unique questions.")

    # 3. Group questions and write to new YAML files
    print("\n[Step 3/5] Writing consolidated YAML files...")
    # Clear out old YAML files before writing new ones.
    if os.path.isdir(YAML_DIR):
        for item in os.listdir(YAML_DIR):
            os.remove(os.path.join(YAML_DIR, item))

    os.makedirs(YAML_DIR, exist_ok=True)
    
    grouped_by_file = {}
    for q in questions_list:
        source_file = q.source_file or 'uncategorized.yaml'
        # Sanitize filenames
        base, _ = os.path.splitext(source_file)
        new_filename = f"{base}.yaml"
        if new_filename not in grouped_by_file:
            grouped_by_file[new_filename] = []
        grouped_by_file[new_filename].append(q)

    for filename, questions in grouped_by_file.items():
        # Convert Question objects to dictionaries for YAML serialization
        questions_dict = [asdict(q) for q in questions]
        output_path = os.path.join(YAML_DIR, filename)
        print(f"  - Writing {len(questions)} questions to {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump({'questions': questions_dict}, f, default_flow_style=False, sort_keys=False)

    print(f"  => Wrote {len(grouped_by_file)} YAML files.")
    
    # 4. Archive old question source directories
    print("\n[Step 4/5] Archiving old question data...")
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    
    to_archive = [JSON_DIR, MD_DIR, MANIFESTS_DIR, SOLUTIONS_DIR]
    for path in to_archive:
        if os.path.isdir(path):
            dest = os.path.join(ARCHIVE_DIR, os.path.basename(path))
            if os.path.exists(dest):
                shutil.rmtree(dest)
            print(f"  - Archiving {path} to {dest}")
            shutil.move(path, dest)

    print("  => Archiving complete.")

    # 5. Rebuild backup database from new YAML files
    print("\n[Step 5/5] Rebuilding backup database...")
    if os.path.exists(BACKUP_DB_FILE):
        os.remove(BACKUP_DB_FILE)
    
    # Temporarily set the main DB path to our backup file
    from kubelingo.utils import config
    original_db_file = config.DATABASE_FILE
    config.DATABASE_FILE = BACKUP_DB_FILE

    try:
        init_db(clear=True) # Create a fresh, empty DB
        conn = get_db_connection()

        loader = YAMLLoader()
        yaml_files = loader.discover()
        for file_path in yaml_files:
            filename = os.path.basename(file_path)
            questions = loader.load_file(file_path)
            for q_obj in questions:
                q_dict = asdict(q_obj)
                add_question(conn=conn, **q_dict)
        conn.commit()
        conn.close()
        print(f"  => Successfully rebuilt backup database at {BACKUP_DB_FILE}")
    finally:
        # Restore original DB path
        config.DATABASE_FILE = original_db_file

    print("\n--- Consolidation Complete! ---")
    print("Your question sources have been unified into `kubelingo/question-data/yaml/`.")
    print("Old sources are archived in `kubelingo/question-data-archive/`.")
    print("The backup database has been rebuilt from the new YAML files.")
    print("\nYou should now commit these changes to your repository.")

if __name__ == '__main__':
    main()
