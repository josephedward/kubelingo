#!/usr/bin/env python3
"""
import_questions.py: import and normalize all question definitions from the
questions/stored directory into individual JSON files following the
canonical schema:
  id, topic, type, question, source, suggested_answer, user_answer, ai_feedback

Usage:
  python3 scripts/import_questions.py [raw_dir]
Defaults:
  raw_dir = 'questions/stored'
"""
import os
import sys
import json
import re
from collections import OrderedDict
try:
    import yaml
except ImportError:
    print("PyYAML is required to run this script. Please install pyyaml.")
    sys.exit(1)
from kubelingo.importer import format_question

def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)

def load_json(path):
    with open(path) as f:
        return json.load(f)

def flatten_suggestions(suggestions):
    parts = []
    for s in suggestions:
        if isinstance(s, str):
            parts.append(s.strip())
        else:
            parts.append(yaml.safe_dump(s, sort_keys=False).strip())
    return "\n\n".join(parts)

def detect_type(suggestions):
    has_yaml = any(not isinstance(s, str) for s in suggestions)
    has_cmd = any(isinstance(s, str) and s.strip().startswith('kubectl') for s in suggestions)
    if has_yaml:
        return 'declarative'
    if has_cmd:
        return 'imperative'
    return 'declarative'

def import_stored(raw_dir):
    if not os.path.isdir(raw_dir):
        print(f"Raw directory '{raw_dir}' not found.")
        sys.exit(1)
    # Gather raw files: YAML (.yaml/.yml) and JSON files not named as 8-hex IDs
    all_files = os.listdir(raw_dir)
    raw_files = []
    for fname in all_files:
        stem, ext = os.path.splitext(fname)
        ext = ext.lower()
        if ext in ('.yaml', '.yml'):
            raw_files.append(fname)
        elif ext == '.json' and not re.fullmatch(r'[0-9a-f]{8}', stem):
            raw_files.append(fname)
    # Process each raw file
    for fname in raw_files:
        fpath = os.path.join(raw_dir, fname)
        stem, ext = os.path.splitext(fname)
        ext = ext.lower()
        if ext in ('.yaml', '.yml'):
            data = load_yaml(fpath)
            if not isinstance(data, dict) or 'questions' not in data:
                print(f"Skipping {fname}: no 'questions' key")
                continue
            questions = data['questions']
        else:
            data = load_json(fpath)
            if isinstance(data, list):
                questions = data
            elif isinstance(data, dict) and 'questions' in data:
                questions = data['questions']
            else:
                print(f"Skipping {fname}: unexpected JSON structure")
                continue
        for q in questions:
            topic = stem
            qid = q.get('id')
            question_text = q.get('question', '').strip()
            source = q.get('source', '')
            suggestions = q.get('suggestions', [])
            suggested_answer = flatten_suggestions(suggestions) if suggestions else ''
            qtype = detect_type(suggestions)
            fq = format_question(topic, question_text, suggested_answer, source, qid=qid)
            # Build ordered dict with type field
            ordered = OrderedDict()
            for key in ['id', 'topic', 'type', 'question', 'source', 'suggested_answer', 'user_answer', 'ai_feedback']:
                if key == 'type':
                    ordered['type'] = qtype
                else:
                    ordered[key] = fq[key]
            out_path = os.path.join(raw_dir, f"{fq['id']}.json")
            with open(out_path, 'w') as f:
                json.dump(ordered, f, indent=2)
            print(f"Written {out_path}")
    # Remove raw files
    for fname in raw_files:
        try:
            os.remove(os.path.join(raw_dir, fname))
        except Exception as e:
            print(f"Error removing {fname}: {e}")

def main():
    raw_dir = sys.argv[1] if len(sys.argv) > 1 else 'questions/stored'
    import_stored(raw_dir)

if __name__ == '__main__':
    main()