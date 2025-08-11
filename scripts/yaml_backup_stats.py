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
    main()