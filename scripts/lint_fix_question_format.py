#!/usr/bin/env python3
"""
Lint and report missing or malformed fields in question definitions (YAML or DB).
"""
import sys
import argparse
from pathlib import Path

def lint_dict(q, source=''):
    required = ['id', 'prompt', 'source_file']
    missing = [f for f in required if not q.get(f)]
    if missing:
        print(f"[{source}] Missing fields {missing} in question: {q.get('id')}")

def lint_yaml(path):
    try:
        import yaml
    except ImportError:
        print("PyYAML required to lint YAML files.")
        return
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, list):
        print(f"YAML root is not a list in {path}")
        return
    for q in data:
        lint_dict(q, source=path)

def lint_db():
    from kubelingo.database import get_all_questions
    qs = get_all_questions()
    for q in qs:
        lint_dict(q, source='DB')

def main():
    parser = argparse.ArgumentParser(
        description="Lint question structure in YAML or database."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--yaml-file', help='Path to a YAML file of questions')
    group.add_argument('--db', action='store_true', help='Lint questions in the database')
    args = parser.parse_args()

    if args.yaml_file:
        path = Path(args.yaml_file)
        if not path.is_file():
            print(f"File not found: {path}")
            sys.exit(1)
        lint_yaml(path)
    elif args.db:
        lint_db()

if __name__ == '__main__':
    main()