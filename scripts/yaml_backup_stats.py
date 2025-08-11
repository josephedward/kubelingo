#!/usr/bin/env python3
"""
yaml_backup_stats.py: Show total questions and per-category counts in a YAML quiz file.
"""
import os
import sys

# Ensure project root is on sys.path for module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    import yaml
except ImportError:
    print("PyYAML is required to run this script. Please install it with: pip install pyyaml")
    sys.exit(1)

from collections import Counter
from kubelingo.modules.yaml_loader import YAMLLoader

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {os.path.basename(sys.argv[0])} <path-to-yaml-file>")
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.isfile(path):
        print(f"File not found: {path}")
        sys.exit(1)

    loader = YAMLLoader()
    questions = loader.load_file(path)
    total = len(questions)
    print(f"Total questions found: {total}")

    # Count by category (first category entry or metadata.category)
    categories = []
    for q in questions:
        cat = None
        if hasattr(q, 'categories') and q.categories:
            cat = q.categories[0]
        elif hasattr(q, 'metadata') and isinstance(q.metadata, dict):
            cat = q.metadata.get('category')
        categories.append(cat or 'Uncategorized')

    counts = Counter(categories)
    if counts:
        print("Questions per category:")
        for cat, cnt in counts.most_common():
            print(f" - {cat}: {cnt}")

if __name__ == '__main__':
    main()