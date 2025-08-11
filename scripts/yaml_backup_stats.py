#!/usr/bin/env python3
"""
Loads a given YAML dump and prints statistics: number of questions,
per-schema/subcategory counts, and file timestamp.
"""
import os
import sys
from pathlib import Path
import time
import argparse
from collections import Counter

# Ensure project root is on sys.path for module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from kubelingo.modules.yaml_loader import YAMLLoader
except ImportError:
    print("Error: kubelingo.modules.yaml_loader not available. Ensure you run this from project root.")
    sys.exit(1)
try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


def analyze_file(path):
    """Loads questions from a YAML file and returns statistics."""
    loader = YAMLLoader()
    try:
        questions = loader.load_file(str(path))
    except Exception as e:
        return {'file': str(path), 'error': f'parse error: {e}'}

    total = len(questions)
    categories = [getattr(q, "category", None) or "Uncategorized" for q in questions]
    counts = dict(Counter(categories))

    # Derive schema categories for stats, mirroring logic from build_question_db.py
    schema_categories = []
    for q in questions:
        q_type = getattr(q, 'question_type', 'command')
        if q_type in ('yaml_edit', 'yaml_author', 'live_k8s_edit'):
            schema_categories.append('Manifests')
        elif q_type == 'socratic':
            schema_categories.append('Basic/Open-Ended')
        else:  # command, etc.
            schema_categories.append('Command-Based/Syntax')
    schema_counts = dict(Counter(schema_categories))

    size = path.stat().st_size
    mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(path.stat().st_mtime))
    return {
        'file': str(path),
        'size': size,
        'mtime': mtime,
        'total': total,
        'categories': counts,
        'schema_categories': schema_counts
    }

def main():
    parser = argparse.ArgumentParser(
        description="Show stats for a given YAML backup file."
    )
    parser.add_argument(
        'path',
        help='Path to YAML file to analyze.'
    )
    args = parser.parse_args()

    target = Path(args.path)
    if not target.is_file():
        print(f"Error: Path is not a file: {target}")
        sys.exit(1)

    stats = analyze_file(target)

    if 'error' in stats:
        print(f"{stats['file']}: {stats['error']}")
    else:
        print(f"File: {stats['file']}")
        print(f" Size: {stats['size']} bytes  Modified: {stats['mtime']}")
        print(f" Total questions: {stats['total']}")

        print("\nQuestions by schema category:")
        for cat, cnt in sorted(stats['schema_categories'].items(), key=lambda x: -x[1]):
            print(f"  {cat}: {cnt}")

        print("\nQuestions by subcategory:")
        for cat, cnt in sorted(stats['categories'].items(), key=lambda x: -x[1]):
            print(f"  {cat}: {cnt}")
        print()

if __name__ == '__main__':
    main()
