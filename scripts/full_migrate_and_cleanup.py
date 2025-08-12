#!/usr/bin/env python3
"""
Full pipeline:
 1. Convert JSON quizzes to YAML
 2. Consolidate manifest quizzes
 3. Merge solution scripts into per-category YAML
 4. (Optional) Convert Markdown question files to YAML
 5. Import all YAML quizzes into SQLite DB
 6. Import all JSON quizzes into DB
 7. Backup the live SQLite DB
 8. Delete legacy JSON, MD, SH, and manifest directories
"""
import sys
import shutil
import subprocess
from pathlib import Path

def run_script(script_name):
    path = Path(__file__).resolve().parents[1] / 'scripts' / script_name
    if path.exists():
        print(f"Running {script_name}...")
        subprocess.run([sys.executable, str(path)], check=False)
    else:
        print(f"Script not found: {script_name}")

def main():
    repo_root = Path(__file__).resolve().parents[1]
    qd = repo_root / 'question-data'

    # 1. JSON → YAML
    run_script('convert_json_to_yaml.py')
    # 2. Manifest consolidation
    run_script('consolidate_manifests.py')
    # 3. Merge solutions
    run_script('merge_solutions.py')
    # 4. (Optional) Convert MD → YAML: not implemented

    # 5. Migrate YAML quizzes into DB
    print("Migrating YAML quizzes into database...")
    subprocess.run(['kubelingo', 'migrate-yaml'], check=False)
    # 6. Import JSON quizzes into DB
    print("Importing JSON quizzes into database...")
    subprocess.run(['kubelingo', 'import-json'], check=False)

    # 7. Backup live DB
    print("Backing up live database...")
    db_src = Path.home() / '.kubelingo' / 'kubelingo.db'
    backup_dir = repo_root / 'question-data-backup'
    backup_dir.mkdir(exist_ok=True)
    db_dst = backup_dir / 'kubelingo.db.bak'
    try:
        shutil.copy2(db_src, db_dst)
        print(f"Copied DB to {db_dst}")
    except Exception as e:
        print(f"Failed to backup DB: {e}")

    # 8. Delete legacy dirs
    for sub in ['json', 'md', 'manifests', 'yaml-bak', 'solutions']:
        path = qd / sub
        if path.exists():
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                print(f"Removed {path.relative_to(repo_root)}")
            except Exception as e:
                print(f"Failed to remove {path}: {e}")

    print("Full migration and cleanup complete.")

if __name__ == '__main__':
    main()