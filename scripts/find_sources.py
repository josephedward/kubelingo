#!/usr/bin/env python3
"""
Interactive tool to manage 'source' fields for Kubernetes questions.
Supports adding sources from a consolidated file, checking for missing sources,
and interactively searching and assigning sources to questions.
"""
import os
import sys
import yaml
import argparse
import webbrowser
from thefuzz import fuzz
try:
    from googlesearch import search
except ImportError:
    search = None

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
    parser = argparse.ArgumentParser(description="Manage question sources.")
    parser.add_argument("--consolidated", help="Consolidated YAML with sources for add mode.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--add", action="store_true", help="Add missing sources from consolidated file.")
    group.add_argument("--check", action="store_true", help="Check for missing sources.")
    group.add_argument("--interactive", action="store_true", help="Interactively find and assign sources.")
    parser.add_argument("--auto-approve", action="store_true",
                        help="In interactive mode, auto-assign first search result.")
    args = parser.parse_args()
    qdir = "questions"
    if args.add:
        if not args.consolidated:
            print("Error: --consolidated PATH is required for --add.")
            sys.exit(1)
        add_sources(args.consolidated, qdir)
    elif args.check:
        check_sources(qdir)
    elif args.interactive:
        interactive(qdir, args.auto_approve)

if __name__ == '__main__':
    main()