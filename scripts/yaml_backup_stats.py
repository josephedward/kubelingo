#!/usr/bin/env python3
"""
Show statistics for YAML backup files: question count by exercise type and subject matter.
Supports single file or directory of YAML backups, and JSON output.
"""
import os
import sys
from pathlib import Path
import time
import json
import re
import argparse
from collections import Counter

# Ensure project root is on sys.path for module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from kubelingo.modules.yaml_loader import YAMLLoader
    from kubelingo.utils.path_utils import find_yaml_files_from_paths
    from kubelingo.utils.config import YAML_BACKUP_DIRS
except ImportError:
    print("Error: A required kubelingo module is not available. Ensure you run this from project root.")
    sys.exit(1)
try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

EXERCISE_TYPE_TO_CATEGORY = {
    "socratic": "Basic",
    "command": "Command",
    "yaml_author": "Manifest",
    "yaml_edit": "Manifest",
    "live_k8s_edit": "Manifest",
}

def analyze_file(path):
    """Analyzes a single YAML file and returns statistics about its questions."""
    loader = YAMLLoader()
    try:
        questions = loader.load_file(str(path))
    except Exception as e:
        return {'file': str(path), 'error': f'parse error: {e}'}

    total = len(questions)

    breakdown = {"Basic": Counter(), "Command": Counter(), "Manifest": Counter(), "Unknown": Counter()}
    for q in questions:
        ex_type = getattr(q, "type", "Unknown Type") or "Unknown"
        subject = (getattr(q, 'metadata', None) or {}).get('category', "Uncategorized") or "Uncategorized"

        major_category = EXERCISE_TYPE_TO_CATEGORY.get(ex_type, "Unknown")
        breakdown[major_category][subject] += 1

    # Clean up empty categories
    breakdown = {k: v for k, v in breakdown.items() if v}

    # Convert counters to dicts for JSON and get top-level counts
    breakdown_dict = {k: dict(v) for k, v in breakdown.items()}
    category_counts = {cat: sum(counts.values()) for cat, counts in breakdown.items()}

    size = path.stat().st_size
    mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(path.stat().st_mtime))

    return {
        'file': str(path),
        'size': size,
        'mtime': mtime,
        'total': total,
        'category_counts': category_counts,
        'breakdown': breakdown_dict,
    }

def main():
    parser = argparse.ArgumentParser(
        description="Show stats for the latest YAML backup file found in the given paths."
    )
    parser.add_argument(
        'paths', nargs='*',
        help='Path(s) to YAML file(s) or directory/ies of backups. If not provided, configured backup dirs are used.'
    )
    parser.add_argument(
        '-p', '--pattern', help='Regex to filter filenames'
    )
    parser.add_argument(
        '--json', action='store_true', help='Output stats in JSON format'
    )
    args = parser.parse_args()

    scan_paths = args.paths or YAML_BACKUP_DIRS

    try:
        files = find_yaml_files_from_paths(scan_paths)
    except Exception as e:
        print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)

    if args.pattern:
        regex = re.compile(args.pattern)
        files = [f for f in files if regex.search(str(f))]

    if not files:
        dirs_str = ', '.join(scan_paths)
        print(f"No YAML files found in {dirs_str}")
        sys.exit(0)

    # Analyze only the latest file based on modification time
    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    if not args.json:
        print(f"Found {len(files)} backup files. Analyzing latest: {latest_file}", file=sys.stderr)

    stats = [analyze_file(latest_file)]
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        for s in stats:
            if 'error' in s:
                print(f"{s['file']}: {s['error']}")
            else:
                print(f"File: {s['file']}")
                print(f" Size: {s['size']} bytes  Modified: {s['mtime']}")
                print(f" Total questions: {s['total']}")
                print(" Questions by Exercise Category:")
                for category, count in sorted(s['category_counts'].items(), key=lambda x: -x[1]):
                    print(f"  {category}: {count}")
                    subject_counts = s.get('breakdown', {}).get(category, {})
                    for subject, sub_count in sorted(subject_counts.items(), key=lambda x: -x[1]):
                        print(f"    - {subject}: {sub_count}")
                print()
if __name__ == '__main__':
    main()
