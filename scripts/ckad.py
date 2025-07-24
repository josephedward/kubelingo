#!/usr/bin/env python3
"""
CKAD CSV/JSON/YAML Spec Management Tool

Subcommands:
  export     Export CSV to JSON and YAML spec files.
  import     Import JSON or YAML spec to regenerate CSV.
  normalize  Normalize CSV (flatten prompts, extract YAML answers).
"""
import argparse
import os
import sys
import csv
import json

def export_spec(input_csv, output_json, output_yaml):
    if not os.path.exists(input_csv):
        print(f"Error: CSV not found at {input_csv}", file=sys.stderr)
        sys.exit(1)
    items = []
    with open(input_csv, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            prompt = row[1].strip()
            raw_answer = row[2].strip()
            if raw_answer.startswith("'") and raw_answer.endswith("'"):
                raw_answer = raw_answer[1:-1].strip()
            idx = raw_answer.find('apiVersion')
            if idx == -1:
                idx = raw_answer.find('kind:')
            answer = raw_answer[idx:].strip() if idx != -1 else raw_answer
            if prompt and answer:
                items.append({'prompt': prompt, 'answer': answer})
    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    with open(output_json, 'w', encoding='utf-8') as jf:
        json.dump(items, jf, indent=2)
    print(f"Wrote {len(items)} questions to JSON: {output_json}")
    try:
        import yaml
    except ImportError:
        print("PyYAML not installed; skipping YAML export")
    else:
        with open(output_yaml, 'w', encoding='utf-8') as yf:
            yaml.safe_dump(items, yf, sort_keys=False)
        print(f"Wrote {len(items)} questions to YAML: {output_yaml}")

def import_spec(input_json, input_yaml, output_csv):
    if input_yaml and os.path.exists(input_yaml):
        try:
            import yaml
        except ImportError:
            print(f"Error: PyYAML required to load YAML spec: {input_yaml}", file=sys.stderr)
            sys.exit(1)
        questions = yaml.safe_load(open(input_yaml, encoding='utf-8'))
    elif input_json and os.path.exists(input_json):
        questions = json.load(open(input_json, encoding='utf-8'))
    else:
        print(f"Error: Spec not found at {input_yaml} or {input_json}", file=sys.stderr)
        sys.exit(1)
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for q in questions:
            prompt = q.get('prompt', '').replace('\r', '')
            answer = q.get('answer', '').replace('\r', '')
            writer.writerow(['', prompt, answer])
    print(f"Wrote {len(questions)} questions to CSV: {output_csv}")

def normalize_csv(input_csv, output_csv):
    if not os.path.exists(input_csv):
        print(f"Error: CSV not found at {input_csv}", file=sys.stderr)
        sys.exit(1)
    rows = []
    with open(input_csv, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            prompt = ' '.join(line.strip() for line in row[1].splitlines() if line.strip())
            raw_ans = row[2].strip()
            if raw_ans.startswith("'") and raw_ans.endswith("'"):
                raw_ans = raw_ans[1:-1].strip()
            idx = raw_ans.find('apiVersion')
            if idx == -1:
                idx = raw_ans.find('kind:')
            ans = raw_ans[idx:].strip() if idx != -1 else raw_ans
            rows.append(['', prompt, ans])
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for r in rows:
            writer.writerow(r)
    print(f"Wrote {len(rows)} normalized rows to CSV: {output_csv}")

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    default_csv = os.path.join(base_dir, 'killercoda-ckad_072425.csv')
    default_json = os.path.join(os.path.dirname(__file__), 'ckad_questions.json')
    default_yaml = os.path.join(os.path.dirname(__file__), 'ckad_questions.yaml')
    default_norm = os.path.join(base_dir, 'killercoda-ckad_normalized.csv')

    parser = argparse.ArgumentParser(prog='ckad', description='Manage CKAD quiz CSV/JSON/YAML spec')
    sub = parser.add_subparsers(dest='cmd')

    exp = sub.add_parser('export', help='Export CSV to JSON/YAML spec')
    exp.add_argument('--csv', default=default_csv, help='Input CSV path')
    exp.add_argument('--json', default=default_json, help='Output JSON spec path')
    exp.add_argument('--yaml', default=default_yaml, help='Output YAML spec path')

    imp = sub.add_parser('import', help='Import spec to regenerate CSV')
    imp.add_argument('--json', default=default_json, help='Input JSON spec path')
    imp.add_argument('--yaml', default=default_yaml, help='Input YAML spec path')
    imp.add_argument('--csv', default=default_csv, help='Output CSV path')

    norm = sub.add_parser('normalize', help='Normalize CSV (flatten prompts, extract YAML)')
    norm.add_argument('--input', default=default_csv, help='Input CSV path')
    norm.add_argument('--output', default=default_norm, help='Output normalized CSV path')

    args = parser.parse_args()
    if args.cmd == 'export':
        export_spec(args.csv, args.json, args.yaml)
    elif args.cmd == 'import':
        import_spec(args.json, args.yaml, args.csv)
    elif args.cmd == 'normalize':
        normalize_csv(args.input, args.output)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()