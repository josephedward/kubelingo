#!/usr/bin/env python3
import os
import re
import argparse
import yaml
import openai
import sys
import webbrowser
from thefuzz import fuzz
try:
    from googlesearch import search
except ImportError:
    search = None

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
        'pattern': re.compile(r'--replicas(?:=|

)(?P<num>\d+)'),
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
    # Handle namespace in YAML suggestions
    if '\n' in solution_text and 'apiVersion' in solution_text:
        try:
            manifest = yaml.safe_load(solution_text)
            ns = manifest.get('metadata', {}).get('namespace')
            if ns and not re.search(r'\bnamespace\b', question_text, re.IGNORECASE):
                missing.append(f' in the "{ns}" namespace')
        except Exception:
            pass
    return missing

def process_file_for_enhancement(path, write=False):
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

def get_source_from_consolidated(item):
    metadata = item.get('metadata', {}) or {}
    for key in ('links', 'source', 'citation'):
        if key in metadata and metadata[key]:
            val = metadata[key]
            # links may be a list
            return val[0] if isinstance(val, list) else val
    return None

def add_sources(consolidated_file, questions_dir):
    print(f"Loading consolidated questions from '{consolidated_file}'...")
    data = yaml.safe_load(open(consolidated_file)) or {}
    mapping = {}
    for item in data.get('questions', []):
        prompt = item.get('prompt') or item.get('question')
        src = get_source_from_consolidated(item)
        if prompt and src:
            mapping[prompt.strip()] = src
    print(f"Found {len(mapping)} source mappings.")
    # Update each question file
    for fname in os.listdir(questions_dir):
        if not fname.endswith('.yaml'):
            continue
        path = os.path.join(questions_dir, fname)
        topic = yaml.safe_load(open(path)) or {}
        qs = topic.get('questions') or []
        updated = 0
        for q in qs:
            if 'source' in q and q['source']:
                continue
            text = q.get('question','').strip()
            best, score = None, 0
            for prompt, src in mapping.items():
                r = fuzz.ratio(text, prompt)
                if r > score:
                    best, score = src, r
            if score > 95:
                q['source'] = best
                updated += 1
                print(f"  + Added source to '{text[:50]}...' -> {best}")
        if updated:
            yaml.dump(topic, open(path,'w'), sort_keys=False)
            print(f"Updated {updated} entries in {fname}.")
    print("Done adding sources.")

def check_sources(questions_dir):
    missing = 0
    for fname in os.listdir(questions_dir):
        if not fname.endswith('.yaml'):
            continue
        path = os.path.join(questions_dir, fname)
        data = yaml.safe_load(open(path)) or {}
        for i, q in enumerate(data.get('questions', []), start=1):
            if not q.get('source'):
                print(f"{fname}: question {i} missing 'source': {q.get('question','')[:80]}")
                missing += 1
    if missing == 0:
        print("All questions have a source.")
    else:
        print(f"{missing} questions missing sources.")

def interactive(questions_dir, auto_approve=False):
    for fname in os.listdir(questions_dir):
        if not fname.endswith('.yaml'):
            continue
        path = os.path.join(questions_dir, fname)
        data = yaml.safe_load(open(path)) or {}
        qs = data.get('questions', [])
        modified = False
        for idx, q in enumerate(qs, start=1):
            if q.get('source'):
                continue
            text = q.get('question','').strip()
            print(f"\nFile: {fname} | Question {idx}: {text}")
            if auto_approve:
                if not search:
                    print("  googlesearch not available.")
                    continue
                try:
                    results = list(search(f"kubernetes {text}", num_results=1))
                except Exception as e:
                    print(f"  Search error: {e}")
                    continue
                if results:
                    q['source'] = results[0]
                    print(f"  Auto-set source: {results[0]}")
                    modified = True
                continue
            # manual interactive search
            print("  Searching online for sources...")
            if not search:
                print("  Install googlesearch-python to enable search.")
                return
            try:
                results = list(search(f"kubernetes {text}", num_results=5))
            except Exception as e:
                print(f"  Search error: {e}")
                continue
            if not results:
                print("  No results found.")
                continue
            for i, url in enumerate(results, start=1):
                print(f"    {i}. {url}")
            choice = input("  Choose default [1] or enter number, [o]pen all, [s]kip: ").strip().lower()
            if choice == 'o':
                for url in results:
                    webbrowser.open(url)
                choice = '1'
            if choice.isdigit() and 1 <= int(choice) <= len(results):
                sel = results[int(choice)-1]
                q['source'] = sel
                print(f"  Selected source: {sel}")
                modified = True
        if modified:
            yaml.dump(data, open(path,'w'), sort_keys=False)
            print(f"Saved updates to {fname}.")
    print("Interactive session complete.")

def main():
    parser = argparse.ArgumentParser(
        description='Manage Kubernetes questions: enhance with AI or manage sources.'
    )
    parser.add_argument(
        '--dir', default='questions', help='Directory of question YAML files'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Subparser for enhancement
    enhance_parser = subparsers.add_parser(
        'enhance', help='Enhance questions with AI'
    )
    enhance_parser.add_argument(
        '--write', action='store_true', help='Write updates back to files'
    )

    # Subparser for source management
    source_parser = subparsers.add_parser(
        'source', help='Manage question sources'
    )
    source_parser.add_argument(
        '--consolidated', help='Consolidated YAML with sources for add mode.'
    )
    source_group = source_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        '--add', action='store_true', help='Add missing sources from consolidated file.'
    )
    source_group.add_argument(
        '--check', action='store_true', help='Check for missing sources.'
    )
    source_group.add_argument(
        '--interactive', action='store_true', help='Interactively find and assign sources.'
    )
    source_parser.add_argument(
        '--auto-approve', action='store_true',
        help='In interactive mode, auto-assign first search result.'
    )

    args = parser.parse_args()
    qdir = args.dir

    if args.command == 'enhance':
        for fn in sorted(os.listdir(qdir)):
            if fn.endswith('.yaml'):
                process_file_for_enhancement(os.path.join(qdir, fn), write=args.write)
    elif args.command == 'source':
        if args.add:
            if not args.consolidated:
                print("Error: --consolidated PATH is required for --add.")
                sys.exit(1)
            add_sources(args.consolidated, qdir)
        elif args.check:
            check_sources(qdir)
        elif args.interactive:
            interactive(qdir, args.auto_approve)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()