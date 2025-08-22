#!/usr/bin/env python3
"""
Enhance question YAMLs by rewriting questions with all relevant details using OpenAI.
For each YAML in the questions/ directory, send the original question and its solution to the OpenAI API,
and generate a rewritten question that includes any important details from the solution that were missing.

Usage:
  python3 scripts/enhance_questions.py [--write] [--dir questions]
  --write: apply changes to files (otherwise only report)
"""
import os
import re
import argparse
import yaml
import openai
openai.api_key = os.getenv("OPENAI_API_KEY")

def enhance_question_with_ai(question_text, solution_text):
    if not openai.api_key:
        raise RuntimeError("OpenAI API key not set. Please set the OPENAI_API_KEY environment variable")
    prompt = f"""You are a helpful assistant that rewrites user questions to include any details present in the solution but missing from the question.

Original question:
```
{question_text}
```

Solution:
```
{solution_text}
```

Return only the rewritten question text. If no changes are needed, return the original question unchanged."""
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Rewrite questions to include missing solution details."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content.strip()

# Patterns mapping solution features to required question phrasing
PATTERNS = [
    {
        'pattern': re.compile(r'--dry-run\b'),
        'checks': [re.compile(r'without creating', re.IGNORECASE), re.compile(r'dry-run', re.IGNORECASE)],
        'append': ' without creating the resource'
    },
    {
        'pattern': re.compile(r'-o\s+yaml'),
        'checks': [re.compile(r'\bYAML\b', re.IGNORECASE)],
        'append': ' and output in YAML format'
    },
    {
        'pattern': re.compile(r'>\s*(?P<file>\S+)'),
        'checks': [re.compile(r'\bsave\b', re.IGNORECASE), re.compile(r'\bfile\b', re.IGNORECASE)],
        'append_template': ' and save it to a file named "{file}"'
    },
    {
        'pattern': re.compile(r'--replicas(?:=|\s+)(?P<num>\d+)'),
        'checks': [re.compile(r'\breplicas\b', re.IGNORECASE)],
        'append_template': ' with {num} replicas'
    },
]

def find_missing_details(question_text, solution_text):
    """Return list of phrases that should be appended to question_text."""
    missing = []
    for pat in PATTERNS:
        m = pat['pattern'].search(solution_text)
        if not m:
            continue
        # if any check phrase already in question, skip
        if any(ch.search(question_text) for ch in pat.get('checks', [])):
            continue
        # prepare append text
        if 'append' in pat:
            missing.append(pat['append'])
        elif 'append_template' in pat:
            gd = m.groupdict()
            try:
                missing.append(pat['append_template'].format(**gd))
            except Exception:
                missing.append(pat['append_template'])
    # Handle namespace in YAML solutions
    if '\n' in solution_text and 'apiVersion' in solution_text:
        try:
            manifest = yaml.safe_load(solution_text)
            ns = manifest.get('metadata', {}).get('namespace')
            if ns and not re.search(r'\bnamespace\b', question_text, re.IGNORECASE):
                missing.append(f' in the "{ns}" namespace')
        except Exception:
            pass
    return missing

def process_file(path, write=False):
    with open(path) as f:
        data = yaml.safe_load(f)
    if not data or 'questions' not in data:
        return
    updated = False
    for q in data['questions']:
        q_text = q.get('question', '') or ''
        sol = q.get('solution', '') or ''
        try:
            new_q = enhance_question_with_ai(q_text, sol)
            if new_q and new_q != q_text:
                q['question'] = new_q
                updated = True
        except Exception as e:
            print(f"Error enhancing {path}: {e}")
    if updated:
        if write:
            with open(path, 'w') as f:
                yaml.safe_dump(data, f, sort_keys=False)
            print(f'Updated {path}')
        else:
            print(f'{path} requires enhancements')

def main():
    parser = argparse.ArgumentParser(
        description='Detect and append missing details to question YAMLs'
    )
    parser.add_argument(
        '--write', action='store_true', help='Write updates back to files'
    )
    parser.add_argument(
        '--dir', default='questions', help='Directory of question YAML files'
    )
    args = parser.parse_args()
    for fn in sorted(os.listdir(args.dir)):
        if fn.endswith('.yaml'):
            process_file(os.path.join(args.dir, fn), write=args.write)

if __name__ == '__main__':
    main()