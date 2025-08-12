#!/usr/bin/env python3
"""
Generates YAML quiz manifests and solution files from question-data JSON.

This can be imported and called as a library function or run as a standalone script.
"""
import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'question-data')
JSON_DIR = os.path.join(DATA_DIR, 'json')
MANIFEST_DIR = os.path.join(DATA_DIR, 'yaml', 'manifests')
SOLUTIONS_DIR = os.path.join(DATA_DIR, 'yaml', 'solutions')

os.makedirs(MANIFEST_DIR, exist_ok=True)
os.makedirs(SOLUTIONS_DIR, exist_ok=True)

def process_json_file(fname):
    path = os.path.join(JSON_DIR, fname)
    with open(path) as f:
        data = json.load(f)
    base = os.path.splitext(fname)[0]
    # prepare manifest entries
    entries = []
    sol_dir = os.path.join(SOLUTIONS_DIR, base)
    os.makedirs(sol_dir, exist_ok=True)
    for idx, item in enumerate(data):
        qid = f"{base}::{idx}"
        question = item.get('prompt') or item.get('prompts', [{}])[0].get('prompt') or item.get('question')
        # determine solution YAML
        # single prompt items
        if 'prompt' in item:
            qid = f"{base}::{idx}"
            question = item['prompt']
            sol = (item.get('answer') or item.get('response') or
                   item.get('correct_yaml') or item.get('metadata', {}).get('answer') or
                   item.get('metadata', {}).get('response'))
            if not sol:
                continue
            # determine extension based on content
            ext = '.yaml' if sol.strip().startswith(('apiVersion', 'kind', '{', '<')) else '.sh'
            sol_path = os.path.join(sol_dir, f"{idx}{ext}")
            with open(sol_path, 'w') as sf:
                sf.write(sol.strip() + '\n')
            entries.append((qid, question, os.path.relpath(sol_path, BASE_DIR)))
        # multi-prompt items inside 'prompts'
        elif 'prompts' in item:
            for jdx, sp in enumerate(item['prompts']):
                qid = f"{base}::{idx}-{jdx}"
                question = sp.get('prompt')
                # support different solution sources
                sol = sp.get('correct_yaml') or sp.get('response')
                if not sol:
                    steps = sp.get('validation_steps', [])
                    sol = '\n'.join(s.get('cmd', '') for s in steps if 'cmd' in s).strip()
                if not sol:
                    continue
                ext = '.yaml' if sol.splitlines()[0].strip().startswith(('apiVersion', 'kind', '{', '<')) else '.sh'
                sol_path = os.path.join(sol_dir, f"{idx}-{jdx}{ext}")
                with open(sol_path, 'w') as sf:
                    sf.write(sol + '\n')
                entries.append((qid, question, os.path.relpath(sol_path, BASE_DIR)))
        else:
            continue
    # write manifest file
    manifest_path = os.path.join(MANIFEST_DIR, f"{base}.yaml")
    with open(manifest_path, 'w') as mf:
        mf.write('"""\nGenerated from ' + fname + '\n"""\n---\n')
        for qid, question, solfile in entries:
            mf.write(f"- id: {qid}\n  question: \"{question}\"\n  solution_file: \"{solfile}\"\n  source: \"https://kubernetes.io/docs/reference/kubectl/cheatsheet/\"\n")
    print(f"Generated {manifest_path}: {len(entries)} entries")

def generate():
    """Generates manifests and solutions from all JSON files in the quiz data directory."""
    for fname in os.listdir(JSON_DIR):
        if fname.endswith('.json'):
            process_json_file(fname)

if __name__ == '__main__':
    generate()
