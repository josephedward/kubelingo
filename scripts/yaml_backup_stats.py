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
def analyze_file(path):
    """Analyzes a single YAML file and returns statistics about its questions."""
    loader = YAMLLoader()
    try:
        questions = loader.load_file(str(path))
    except Exception as e:
        return {'file': str(path), 'error': f'parse error: {e}'}

    total = len(questions)
    exercise_types = [getattr(q, "type", "Unknown Type") or "Unknown" for q in questions]
    subject_matters = [getattr(q, "category", "Uncategorized") or "Uncategorized" for q in questions]

    type_counts = dict(Counter(exercise_types))
    subject_counts = dict(Counter(subject_matters))

    size = path.stat().st_size
    mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(path.stat().st_mtime))

    return {
        'file': str(path),
        'size': size,
        'mtime': mtime,
        'total': total,
        'exercise_types': type_counts,
        'subject_matter': subject_counts,
    }

def main():
    parser = argparse.ArgumentParser(
        description="Show stats for YAML backup files."
    )
    parser.add_argument(
        'paths', nargs='*',
        help='Path(s) to YAML file(s) or directory/ies of backups (defaults to configured backup dirs)'
    )
    parser.add_argument(
        '-p', '--pattern', help='Regex to filter filenames'
    )
    parser.add_argument(
        '--json', action='store_true', help='Output stats in JSON format'
    )
    args = parser.parse_args()

    files = []
    scan_paths = args.paths
    project_root = Path(__file__).resolve().parent.parent

    # If no specific paths are given, try to use the index for default backup dirs
    if not scan_paths:
        index_file = project_root / "backups" / "index.yaml"
        if index_file.exists():
            print(f"Info: No paths provided. Using index file to find backup YAMLs.", file=sys.stderr)
            with open(index_file, 'r') as f:
                index_data = yaml.safe_load(f)

            # Resolve backup dirs to absolute paths for consistent comparison.
            # Handles cases where YAML_BACKUP_DIRS might contain relative or absolute paths.
            abs_backup_dirs = [(Path(d) if Path(d).is_absolute() else project_root / d).resolve() for d in YAML_BACKUP_DIRS]
            all_indexed_files = [Path(f['path']) for f in index_data.get('files', [])]

            candidate_files = []
            for file_path in all_indexed_files:
                # Resolve the indexed file path to an absolute path.
                abs_file_path = (project_root / file_path).resolve()
                # Check if the file's directory is a sub-directory of any backup directory.
                if any(abs_backup_dir in abs_file_path.parents for abs_backup_dir in abs_backup_dirs):
                    candidate_files.append(abs_file_path)
            files = candidate_files
        else:
            # Fallback to scanning default dirs if index not found
            print("Info: No index file found, falling back to scanning backup directories.", file=sys.stderr)
            scan_paths = YAML_BACKUP_DIRS
            try:
                files = find_yaml_files_from_paths(scan_paths)
            except Exception as e:
                print(f"Error scanning directories: {e}", file=sys.stderr)
                sys.exit(1)
    else:
        # If paths are provided, scan them directly (old behavior)
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

    stats = [analyze_file(f) for f in files]
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
                print(" Questions by exercise type:")
                for cat, cnt in sorted(s['exercise_types'].items(), key=lambda x: -x[1]):
                    print(f"  {cat}: {cnt}")
                print(" Questions by subject matter:")
                for cat, cnt in sorted(s['subject_matter'].items(), key=lambda x: -x[1]):
                    print(f"  {cat}: {cnt}")
                print()
if __name__ == '__main__':
    main()
