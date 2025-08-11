#!/usr/bin/env python3
"""
View statistics of a YAML backup file: total questions, categories, and file size.
"""
import os
import argparse
import sys
try:
    import yaml
except ImportError:
    print("Error: PyYAML is not installed. Please install PyYAML to run this script.")
    sys.exit(1)
from collections import Counter

def main():
    parser = argparse.ArgumentParser(
        description="Show stats for a YAML backup (question count, categories)."
    )
    parser.add_argument(
        'file', help='Path to the YAML backup file'
    )
    args = parser.parse_args()
    path = args.file
    if not os.path.isfile(path):
        print(f"Backup file not found: {path}")
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to parse YAML: {e}")
        return
    if not isinstance(data, list):
        print(f"Unexpected format: expected a YAML list of questions, got {type(data).__name__}")
        return
    total = len(data)
    categories = Counter()
    for item in data:
        cat = item.get('category') or 'UNSPECIFIED'
        categories[cat] += 1
    size = os.path.getsize(path)
    print(f"File: {path}")
    print(f"Size: {size} bytes")
    print(f"Total questions: {total}")
    print("Questions by category:")
    for cat, count in categories.most_common():
        print(f"  {cat}: {count}")

if __name__ == '__main__':
    main()import os
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
