#!/usr/bin/env python3
"""
Script to check quiz YAML files for formatting standardization.
"""
import sys
import yaml
import re
from pathlib import Path

# Regex for id format: kebab-case alphanumeric and hyphens
ID_REGEX = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')

# Directory containing quiz YAML files
QUIZ_DIR = Path(__file__).resolve().parent.parent / 'question-data' / 'yaml'

def load_yaml(file_path):
    content = ''.join(line for line in file_path.open('r', encoding='utf-8') if not line.strip().startswith('#'))
    try:
        return yaml.safe_load(content)
    except Exception as e:
        raise RuntimeError(f"YAML parsing error in {file_path}: {e}")

def main():
    errors = []
    ids_global = {}
    for file_path in sorted(QUIZ_DIR.glob('*.yaml')):
        try:
            data = load_yaml(file_path)
        except RuntimeError as e:
            errors.append(str(e))
            continue
        if not isinstance(data, dict):
            errors.append(f"{file_path}: top-level structure is not a dict")
            continue
        questions = data.get('questions')
        if not isinstance(questions, list):
            errors.append(f"{file_path}: missing 'questions' key or it's not a list")
            continue
        ids_local = set()
        for idx, q in enumerate(questions, 1):
            if not isinstance(q, dict):
                errors.append(f"{file_path}[{idx}]: entry is not a dict")
                continue
            for key in ('id', 'category', 'prompt', 'response', 'links'):
                if key not in q:
                    errors.append(f"{file_path}[{idx}]: missing key '{key}'")
            id_val = q.get('id')
            if isinstance(id_val, str):
                if not ID_REGEX.match(id_val):
                    errors.append(f"{file_path}[{idx}]: id '{id_val}' not kebab-case")
                if id_val in ids_local:
                    errors.append(f"{file_path}[{idx}]: duplicate id '{id_val}' in same file")
                ids_local.add(id_val)
                if id_val in ids_global:
                    errors.append(f"{file_path}[{idx}]: id '{id_val}' also found in {ids_global[id_val]}")
                ids_global[id_val] = file_path
            else:
                errors.append(f"{file_path}[{idx}]: id missing or not a string")
            links = q.get('links')
            if not isinstance(links, list) or not links:
                errors.append(f"{file_path}[{idx}]: links should be a non-empty list")
            else:
                for link in links:
                    if not (isinstance(link, str) and link.startswith(('http://', 'https://'))):
                        errors.append(f"{file_path}[{idx}]: invalid link '{link}'")
    if errors:
        print('Quiz formatting errors found:')
        for err in errors:
            print(' -', err)
        sys.exit(1)
    print('All quiz files passed formatting checks.')
    sys.exit(0)

if __name__ == '__main__':
    main()