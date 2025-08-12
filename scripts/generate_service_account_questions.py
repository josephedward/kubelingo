#!/usr/bin/env python3
"""
Generate static Kubernetes ServiceAccount questions in JSON format and optionally add them to the local kubelingo database.
"""
import os
import sys
import json
import argparse

# Ensure project root is on path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from kubelingo.database import init_db, add_question

def generate_questions():
    """Return a list of question dicts in unified format."""
    questions = []
    # Question 0: Simple ServiceAccount in default namespace
    ans0 = (
        "apiVersion: v1\n"
        "kind: ServiceAccount\n"
        "metadata:\n"
        "  name: sa-reader\n"
        "  namespace: default"
    )
    questions.append({
        "id": "service_accounts::0",
        "prompt": "Create a ServiceAccount named 'sa-reader' in the 'default' namespace.",
        "type": "command",
        "pre_shell_cmds": [],
        "initial_files": {},
        "validation_steps": [
            {"cmd": ans0, "matcher": {"exit_code": 0}}
        ],
        "explanation": None,
        "categories": ["Service Account"],
        "difficulty": None,
        "metadata": {"answer": ans0}
    })
    # Question 1: ServiceAccount in custom namespace
    ans1 = (
        "apiVersion: v1\n"
        "kind: ServiceAccount\n"
        "metadata:\n"
        "  name: sa-deployer\n"
        "  namespace: dev-namespace"
    )
    questions.append({
        "id": "service_accounts::1",
        "prompt": "Create a ServiceAccount named 'sa-deployer' in the 'dev-namespace' namespace.",
        "type": "command",
        "pre_shell_cmds": [],
        "initial_files": {},
        "validation_steps": [
            {"cmd": ans1, "matcher": {"exit_code": 0}}
        ],
        "explanation": None,
        "categories": ["Service Account"],
        "difficulty": None,
        "metadata": {"answer": ans1}
    })
    # Question 2: ServiceAccount with imagePullSecrets
    ans2 = (
        "apiVersion: v1\n"
        "kind: ServiceAccount\n"
        "metadata:\n"
        "  name: sa-db\n"
        "  namespace: prod\n"
        "imagePullSecrets:\n"
        "- name: db-secret"
    )
    questions.append({
        "id": "service_accounts::2",
        "prompt": "Create a ServiceAccount named 'sa-db' in the 'prod' namespace with imagePullSecret 'db-secret'.",  # noqa: E501
        "type": "command",
        "pre_shell_cmds": [],
        "initial_files": {},
        "validation_steps": [
            {"cmd": ans2, "matcher": {"exit_code": 0}}
        ],
        "explanation": None,
        "categories": ["Service Account"],
        "difficulty": None,
        "metadata": {"answer": ans2}
    })
    return questions

def main():
    parser = argparse.ArgumentParser(
        description="Generate ServiceAccount quiz questions and optionally add to kubelingo DB"
    )
    parser.add_argument(
        '--to-db', action='store_true',
        help='Initialize DB and add generated questions to the kubelingo database'
    )
    parser.add_argument(
        '-n', '--num', type=int, default=0,
        help='Number of questions to output (default: all)'
    )
    parser.add_argument(
        '-o', '--output', type=str,
        help='Write generated questions to a JSON file'
    )
    args = parser.parse_args()
    questions = generate_questions()
    if args.num and args.num > 0:
        questions = questions[:args.num]
    # Output JSON
    json_out = json.dumps(questions, indent=2)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(json_out)
        print(f"Wrote {len(questions)} questions to {args.output}")
    else:
        print(json_out)
    # Add to DB if requested
    if args.to_db:
        init_db()
        added = 0
        for q in questions:
            try:
                add_question(
                    id=q['id'],
                    prompt=q['prompt'],
                    source_file='service_accounts',
                    response=q['metadata']['answer'],
                    category=q.get('categories', [None])[0],
                    source='script',
                    validation_steps=q.get('validation_steps'),
                    validator=None
                )
                added += 1
            except Exception as e:
                print(f"Warning: could not add question '{q['id']}' to DB: {e}")
        print(f"Requested to add {len(questions)} questions; successfully added {added} to the kubelingo database.")

if __name__ == '__main__':  # pragma: no cover
    main()