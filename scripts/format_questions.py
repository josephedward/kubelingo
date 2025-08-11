#!/usr/bin/env python3
"""
Lint and reformat question YAML files for style consistency.
"""
import argparse
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print('PyYAML is required. Install with: pip install pyyaml', file=sys.stderr)
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Reformat question YAML files')
    parser.add_argument('directory', nargs='?', default='question-data/questions', help='Directory of YAML question files')
    args = parser.parse_args()
    path = Path(args.directory)
    if not path.is_dir():
        print(f'Directory not found: {path}', file=sys.stderr)
        sys.exit(1)
    for file in path.rglob('*.yaml'):
        data = yaml.safe_load(file)
        with open(file, 'w') as f:
            yaml.safe_dump(data, f, sort_keys=True, default_flow_style=False)
        print(f'Formatted {file}')

if __name__ == '__main__':
    main()