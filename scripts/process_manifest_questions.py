#!/usr/bin/env python3
"""
Script to process YAML files in the questions directory to validate and fix nested YAML manifests in solution strings.
"""
import os
import sys
try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with 'pip install PyYAML'")
    sys.exit(1)

def validate_and_fix_nested_yaml(data):
    """
    Recursively validate and fix nested YAML strings within a data structure.
    Returns True if any changes were made.
    """
    changed = False
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                try:
                    nested = yaml.safe_load(value)
                    if nested is not None and isinstance(nested, (dict, list)):
                        data[key] = yaml.safe_dump(nested, default_flow_style=False, sort_keys=False, indent=2).rstrip()
                        changed = True
                        print(f"Fixed nested YAML for key: {key}")
                except yaml.YAMLError:
                    pass
            elif isinstance(value, (dict, list)):
                if validate_and_fix_nested_yaml(value):
                    changed = True
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            if isinstance(item, str):
                try:
                    nested = yaml.safe_load(item)
                    if nested is not None and isinstance(nested, (dict, list)):
                        data[idx] = yaml.safe_dump(nested, default_flow_style=False, sort_keys=False, indent=2).rstrip()
                        changed = True
                        print(f"Fixed nested YAML for list item at index: {idx}")
                except yaml.YAMLError:
                    pass
            elif isinstance(item, (dict, list)):
                if validate_and_fix_nested_yaml(item):
                    changed = True
    return changed

def process_question_files(questions_dir):
    processed = 0
    fixed = 0
    for fname in os.listdir(questions_dir):
        if not fname.endswith((".yaml", ".yml")):
            continue
        path = os.path.join(questions_dir, fname)
        processed += 1
        print(f"Processing {path}...")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            print(f"Skipping {fname}: invalid YAML ({e})")
            continue
        if validate_and_fix_nested_yaml(data):
            fixed += 1
            new_content = yaml.safe_dump(data, default_flow_style=False, sort_keys=False, indent=2)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Updated {path}")
        else:
            print(f"No changes for {path}")
    print(f"Processed {processed} files, fixed {fixed} files.")

if __name__ == "__main__":
    top = os.path.join(os.getcwd(), "questions")
    if not os.path.isdir(top):
        print(f"Questions directory not found: {top}")
        sys.exit(1)
    process_question_files(top)