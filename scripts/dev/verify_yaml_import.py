"""
Verifies that questions from a YAML file can be imported into a SQLite DB and
loaded correctly by the DBLoader.

Usage:
    python scripts/dev/verify_yaml_import.py <path_to_yaml_file>
"""
import sys
import os
import yaml
import sqlite3
import tempfile
import json
import argparse

# Add project root to path to allow importing kubelingo modules
# This is needed to run the script from the project root.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from kubelingo.modules.db_loader import DBLoader

def create_db_schema(conn: sqlite3.Connection):
    """Creates the questions table in the SQLite database."""
    cursor = conn.cursor()
    # This schema is inferred from DBLoader and Question dataclass.
    # It might need adjustments if the actual schema differs.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id TEXT PRIMARY KEY,
        prompt TEXT,
        source_file TEXT,
        response TEXT,
        category TEXT,
        source TEXT,
        validation_steps TEXT,
        validator TEXT,
        review BOOLEAN,
        question_type TEXT,
        type TEXT,
        subject_matter TEXT,
        metadata TEXT,
        categories TEXT,
        difficulty TEXT,
        pre_shell_cmds TEXT,
        initial_files TEXT,
        explanation TEXT
    )
    """)
    conn.commit()

def import_yaml_to_db(yaml_path: str, conn: sqlite3.Connection):
    """Reads questions from a YAML file and imports them into the DB."""
    try:
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: YAML file not found at {yaml_path}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}", file=sys.stderr)
        sys.exit(1)

    questions = data.get('questions', [])
    source_file = os.path.basename(yaml_path)
    cursor = conn.cursor()

    for q in questions:
        params = {
            'id': q.get('id'),
            'prompt': q.get('prompt', ''),
            'source_file': source_file,
            'response': q.get('response'),
            'category': q.get('category'), # Legacy field
            'source': q.get('source'),
            'validation_steps': json.dumps(q.get('validation_steps', [])),
            'validator': json.dumps(q.get('validator', {})),
            'review': q.get('review', False),
            'question_type': q.get('type') or q.get('question_type', 'command'),
            'type': q.get('type'), # Legacy field
            'subject_matter': q.get('subject_matter'),
            'metadata': json.dumps(q.get('metadata', {})),
            'categories': json.dumps(q.get('categories', [])),
            'difficulty': q.get('difficulty'),
            'pre_shell_cmds': json.dumps(q.get('pre_shell_cmds', [])),
            'initial_files': json.dumps(q.get('initial_files', {})),
            'explanation': q.get('explanation')
        }
        if not params['id']:
            print(f"Skipping question without id: {q.get('prompt', 'No prompt')[:50]}...", file=sys.stderr)
            continue
        
        columns = ', '.join(params.keys())
        placeholders = ', '.join(':' + key for key in params.keys())
        sql = f"INSERT INTO questions ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, params)

    conn.commit()
    print(f"Imported {len(questions)} questions from {yaml_path} into the temporary database.")
    return len(questions)

def main():
    parser = argparse.ArgumentParser(
        description="Verify YAML question import to SQLite and loading via DBLoader.",
        epilog="This script can process single files, multiple files, or directories of files."
    )
    parser.add_argument("paths", nargs='+', help="Path(s) to YAML file(s) or directories containing them.")
    args = parser.parse_args()

    yaml_files = []
    for path in args.paths:
        if os.path.isdir(path):
            print(f"Searching for YAML files in directory: {path}")
            for item in os.listdir(path):
                if item.endswith(('.yml', '.yaml')):
                    full_path = os.path.join(path, item)
                    yaml_files.append(full_path)
        elif os.path.isfile(path):
            if path.endswith(('.yml', '.yaml')):
                yaml_files.append(path)
            else:
                print(f"Warning: Skipping non-YAML file: {path}", file=sys.stderr)
        else:
            if 'path/to/your/quiz.yaml' in path:
                 print(f"Error: YAML file not found at {path}", file=sys.stderr)
                 print("Please replace 'path/to/your/quiz.yaml' with the actual path to your YAML file.", file=sys.stderr)
                 sys.exit(1)
            else:
                print(f"Warning: Path not found or is not a file/directory, skipping: {path}", file=sys.stderr)

    yaml_files = sorted(list(set(yaml_files)))

    if not yaml_files:
        print("Error: No YAML files found in the provided paths.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(yaml_files)} YAML file(s) to process.")
    
    # We use a temporary file on disk so we have a path to pass to DBLoader.
    tmp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp_db_file.name
    tmp_db_file.close()

    try:
        print(f"Using temporary database: {db_path}")
        
        conn = sqlite3.connect(db_path)
        create_db_schema(conn)

        total_imported = 0
        imported_files_map = {}  # basename -> count

        for yaml_file in yaml_files:
            num_imported = import_yaml_to_db(yaml_file, conn)
            if num_imported > 0:
                total_imported += num_imported
                imported_files_map[os.path.basename(yaml_file)] = num_imported
        
        conn.close()

        if total_imported == 0:
            print("No questions found in any YAML file. Exiting.")
            return

        print(f"\nTotal questions imported: {total_imported}")
        print("\nVerifying import using DBLoader...")
        loader = DBLoader(db_path=db_path)
        
        source_files_in_db = loader.discover()
        
        all_sources_discovered = True
        for basename in imported_files_map:
            if basename not in source_files_in_db:
                print(f"ERROR: DBLoader did not discover source_file '{basename}' in the database.", file=sys.stderr)
                all_sources_discovered = False
        
        if not all_sources_discovered:
             print(f"Discovered files in DB: {source_files_in_db}", file=sys.stderr)
             sys.exit(1)
            
        print(f"Successfully discovered all {len(imported_files_map)} source file(s).")

        total_loaded = 0
        all_counts_match = True
        for basename, num_imported in imported_files_map.items():
            loaded_questions = loader.load_file(basename)
            num_loaded = len(loaded_questions)
            total_loaded += num_loaded
            print(f"- '{basename}': Imported {num_imported}, DBLoader loaded {num_loaded}.")
            if num_loaded != num_imported:
                all_counts_match = False
        
        print("-" * 20)
        print(f"Total Imported: {total_imported}, Total Loaded: {total_loaded}")

        if all_counts_match and total_imported == total_loaded:
            print("\nSUCCESS: The number of loaded questions matches the number of imported questions for all files.")
        else:
            print(f"\nERROR: Mismatch in question count detected for one or more files.", file=sys.stderr)
            sys.exit(1)

    finally:
        # Clean up the temporary database file
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"Temporary database {db_path} cleaned up.")


if __name__ == "__main__":
    main()
