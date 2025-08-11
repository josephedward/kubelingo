#!/usr/bin/env python3
"""
Show statistics for YAML backup files: question count, categories, file size.
Supports single file or directory of YAML backups, JSON output, and optional AI summary.
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
try:
    from kubelingo.utils.config import get_api_key
except ImportError:
    get_api_key = None

def analyze_file(path):
    loader = YAMLLoader()
    try:
        questions = loader.load_file(str(path))
    except Exception as e:
        return {'file': str(path), 'error': f'parse error: {e}'}
    total = len(questions)
    categories = [getattr(q, "category", None) or "Uncategorized" for q in questions]
    counts = dict(Counter(categories))
    size = path.stat().st_size
    mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(path.stat().st_mtime))
    return {'file': str(path), 'size': size, 'mtime': mtime, 'total': total, 'categories': counts}

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
    parser.add_argument(
        '--ai', action='store_true', help='Use AI to summarize statistics'
    )
    args = parser.parse_args()

    scan_paths = args.paths
    if not scan_paths:
        scan_paths = YAML_BACKUP_DIRS

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
                print(" Questions by category:")
                for cat, cnt in sorted(s['categories'].items(), key=lambda x: -x[1]):
                    print(f"  {cat}: {cnt}")
                print()
    if args.ai:
        try:
            from openai import OpenAI
            api_key = os.getenv('OPENAI_API_KEY') or (get_api_key() if get_api_key else None)
            if not api_key:
                print('No OpenAI API key found; skipping AI summary')
                return
            client = OpenAI(api_key=api_key)
            prompt = ('Here are YAML backup statistics: ' + json.dumps(stats) +
                      '\nPlease provide a concise summary of these backups, highlighting differences and any notable points.')
            resp = client.chat.completions.create(
                model='gpt-3.5-turbo',
                messages=[{'role': 'user', 'content': prompt}]
            )
            summary = resp.choices[0].message.content
            print('\nAI Summary:\n' + summary)
        except ImportError:
            print('OpenAI library not installed; install openai to enable AI summary')
        except Exception as e:
            print(f'Failed to generate AI summary: {e}')
if __name__ == '__main__':
    main()
