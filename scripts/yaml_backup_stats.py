import os
from pathlib import Path
import sys

try:
    import yaml
except ImportError:
    print("Error: PyYAML is not installed. Please install it to run this script:")
    print("pip install PyYAML")
    sys.exit(1)

def main():
    """
    Scans for YAML files in question-data-backup/, loads them, and reports
    statistics, such as the number of questions in each file.
    """
    backup_dir = Path("question-data-backup")
    
    if not backup_dir.is_dir():
        print(f"Backup directory not found: {backup_dir}")
        return

    yaml_files = list(backup_dir.glob('*.yaml')) + list(backup_dir.glob('*.yml'))

    if not yaml_files:
        print("No YAML backup files found in question-data-backup/.")
        return

    print("YAML backup file stats:")
    for f_path in yaml_files:
        try:
            with open(f_path, 'r') as f:
                data = yaml.safe_load(f)
            if isinstance(data, list):
                print(f" - {f_path}: {len(data)} questions")
            else:
                print(f" - {f_path}: Not a list of questions (or empty)")
        except Exception as e:
            print(f" - {f_path}: Error loading or parsing file: {e}")

if __name__ == "__main__":
    main()
