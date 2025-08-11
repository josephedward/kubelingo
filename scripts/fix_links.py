#!/usr/bin/env python3
"""
Scan question YAML files for `links` entries and interactively fix broken URLs.
"""
import argparse
import os
import sys
from pathlib import Path

try:
    import yaml
    import requests
except ImportError:
    print('This script requires PyYAML and requests. Install with: pip install pyyaml requests', file=sys.stderr)
    sys.exit(1)

def check_url(url):
    try:
        resp = requests.head(url, allow_redirects=True, timeout=5)
        return resp.status_code < 400
    except Exception:
        return False

def main():
    parser = argparse.ArgumentParser(description='Fix broken links in question YAMLs')
    parser.add_argument('directory', nargs='?', default='question-data/questions', help='Directory of YAML question files')
    args = parser.parse_args()
    path = Path(args.directory)
    if not path.is_dir():
        print(f'Directory not found: {path}', file=sys.stderr)
        sys.exit(1)
    for file in path.rglob('*.yaml'):
        data = yaml.safe_load(file) or []
        changed = False
        for q in data:
            links = q.get('links')
            if not isinstance(links, list):
                continue
            for i, url in enumerate(links):
                if not check_url(url):
                    print(f"Broken URL in {file}:{q.get('id')}: {url}")
                    new = input(f'Enter replacement or leave blank to remove: ').strip()
                    if new:
                        links[i] = new
                    else:
                        links[i] = None
                    changed = True
        if changed:
            # Remove None entries
            for q in data:
                if 'links' in q and isinstance(q['links'], list):
                    q['links'] = [u for u in q['links'] if u]
            with open(file, 'w') as f:
                yaml.safe_dump(data, f)
            print(f'Updated links in {file}')

if __name__ == '__main__':
    main()