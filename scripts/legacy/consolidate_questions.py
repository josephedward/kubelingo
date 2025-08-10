#!/usr/bin/env python3
"""
Performs a one-time consolidation of all scattered question source files (JSON,
Markdown, YAML) into a single, organized directory of category-based YAML files,
and archives the original files.
"""
import os
import sys
import json
import shutil
from pathlib import Path
from dataclasses import asdict, fields
from collections import defaultdict
import uuid

# Add project root to path to allow importing kubelingo modules
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# All Question logic is self-contained, so this is safe.
from kubelingo.question import Question

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Please install it using: pip install pyyaml")
    sys.exit(1)


# --- Self-Contained Loaders ---

def load_json_file(path: str) -> list[Question]:
    """Loads questions from a single JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    questions = []
    # Handle both list of questions and section-based format
    if isinstance(data, list):
        items = data
        category = Path(path).stem
    elif isinstance(data, dict) and 'questions' in data:
        items = data.get('questions', [])
        category = data.get('category', Path(path).stem)
    else: # Assuming sections
        items = []
        category = Path(path).stem
        for section in data:
            cat = section.get('category', category)
            for prompt in section.get('prompts', []):
                prompt['category'] = cat
                items.append(prompt)

    for item in items:
        # Ensure a unique ID
        if 'id' not in item or not item['id']:
            item['id'] = str(uuid.uuid4())
        item.setdefault('source_file', Path(path).name)
        # The `type` field is sometimes called `question_type` in old formats.
        if 'question_type' in item and 'type' not in item:
            item['type'] = item.pop('question_type')
        try:
            questions.append(Question(**item))
        except TypeError as e:
            print(f"  - Warning: Skipping question in {Path(path).name} due to invalid field: {e}")
    return questions


def load_md_file(path: str) -> list[Question]:
    """Loads questions from a single Markdown file with YAML frontmatter."""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    parts = content.split('---')
    if len(parts) < 3:
        return []

    frontmatter = yaml.safe_load(parts[1])
    if not frontmatter or not isinstance(frontmatter.get('questions'), list):
        return []

    questions = []
    for item in frontmatter['questions']:
        if 'id' not in item or not item['id']:
            item['id'] = str(uuid.uuid4())
        item.setdefault('source_file', Path(path).name)
        if 'question_type' in item and 'type' not in item:
            item['type'] = item.pop('question_type')
        try:
            questions.append(Question(**item))
        except TypeError as e:
            print(f"  - Warning: Skipping question in {Path(path).name} due to invalid field: {e}")
    return questions


def load_yaml_file(path: str) -> list[Question]:
    """Loads questions from a single YAML file."""
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    if not data:
        return []

    questions = []
    # The YAML files can be a list of questions or a dict with a 'questions' key.
    items = data if isinstance(data, list) else data.get('questions', [])
    
    for item in items:
        if not isinstance(item, dict):
            continue
        if 'id' not in item or not item['id']:
            item['id'] = str(uuid.uuid4())
        item.setdefault('source_file', Path(path).name)
        if 'question_type' in item and 'type' not in item:
            item['type'] = item.pop('question_type')
        try:
            questions.append(Question(**item))
        except TypeError as e:
            print(f"  - Warning: Skipping question in {Path(path).name} due to invalid field: {e}")
            
    return questions


def main():
    """This script is deprecated."""
    print("This script is deprecated and should not be used.")
    print("The application now loads questions directly from individual YAML files.")


if __name__ == "__main__":
    main()
