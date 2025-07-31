#!/usr/bin/env python3
"""
Manage Kubelingo question-data: organization, deduplication, and AI-driven enrichment.

Based on Kubelingo’s Phase 1 Unified Shell Experience (see shared_context.md),
this tool:
  • Organizes and archives legacy question files (stubs, Killercoda data).
  • Deduplicates prompts across JSON, YAML, and Markdown quiz sources.
  • Generates concise AI explanations for questions lacking them.

Usage:
  scripts/manage_questions.py organize [--dry-run]
    Organize question-data directory: archive stubs, rename files per best practices.

  scripts/manage_questions.py enrich <source_dir> <output_file> [--format json|yaml] [--model MODEL] [--dry-run]
    Load all quiz files under <source_dir>, dedupe prompts, and fill missing explanations
    via OpenAI (Chat Completions). Writes unified question set to <output_file>.
"""
import argparse
import os
import sys
import shutil
import re
import json
import urllib.request
import urllib.error
from pathlib import Path

# Data model imports for enrichment
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kubelingo.question import Question, ValidationStep
from kubelingo.modules.json_loader import JSONLoader
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.modules.md_loader import MDLoader
from dataclasses import asdict
# Load shared AI prompt context from root shared_context.md
shared_context_path = Path(__file__).resolve().parent.parent / 'shared_context.md'
if shared_context_path.exists():
    SHARED_CONTEXT = shared_context_path.read_text(encoding='utf-8')
else:
    SHARED_CONTEXT = ''

def organize_question_data(root: Path, dry_run: bool = False):
    """Archive legacy stubs and rename core quiz files under question-data."""
    archive = root / '_archive'
    actions = []
    # Prepare archive subdirs
    for sub in ['json', 'yaml', 'csv', 'md']:
        (archive / sub).mkdir(parents=True, exist_ok=True)
    # Stubs to archive
    for name in ['ckad_questions.json', 'killercoda_ckad.json']:
        src = root / 'json' / name
        if src.exists(): actions.append((src, archive / 'json' / name))
    for name in ['ckad_questions.yaml', 'ckad_questions.yml']:
        src = root / 'yaml' / name
        if src.exists(): actions.append((src, archive / 'yaml' / name))
    # CSV files
    for f in (root / 'csv').glob('*'):  # type: ignore
        if f.is_file(): actions.append((f, archive / 'csv' / f.name))
    # Markdown: strip letter prefixes and archive Killercoda cheat sheet
    md_dir = root / 'md'
    if md_dir.is_dir():
        for p in md_dir.iterdir():
            if not p.is_file(): continue
            if p.name.lower().startswith('killercoda'):
                actions.append((p, archive / 'md' / p.name))
            else:
                m = re.match(r'^[a-z]\.([^.].+)', p.name)
                if m:
                    dst = md_dir / m.group(1)
                    actions.append((p, dst))
    # Rename core JSON quizzes
    rename_map = {
        'ckad_quiz_data.json': 'kubernetes.json',
        'ckad_quiz_data_with_explanations.json': 'kubernetes_with_explanations.json',
        'yaml_edit_questions.json': 'yaml_edit.json',
        'vim_quiz_data.json': 'vim.json',
    }
    for src_name, dst_name in rename_map.items():
        src = root / 'json' / src_name
        dst = root / 'json' / dst_name
        if src.exists(): actions.append((src, dst))
    # Execute or preview
    for src, dst in actions:
        if dry_run:
            print(f"[DRY-RUN] Move: {src} -> {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            print(f"Moved: {src} -> {dst}")
    # Remove empty dirs
    for sub in ['json', 'yaml', 'csv', 'md']:
        d = root / sub
        if d.is_dir() and not any(d.iterdir()):
            if dry_run:
                print(f"[DRY-RUN] Remove empty dir: {d}")
            else:
                d.rmdir()
                print(f"Removed empty dir: {d}")

def load_questions_from_dir(source_dir: Path):
    """Load all Question objects under a directory via JSON/YAML/MD loaders."""
    questions = []
    json_loader, yaml_loader, md_loader = JSONLoader(), YAMLLoader(), MDLoader()
    for ext, loader in (('json', json_loader), ('yml', yaml_loader), ('yaml', yaml_loader), ('md', md_loader)):
        for path in source_dir.rglob(f'*.{ext}'):
            if '_archive' in path.parts: continue
            try:
                questions.extend(loader.load_file(str(path)))
            except Exception:
                continue
    return [q for q in questions if q.prompt and q.prompt.strip()]

def normalize_prompt(prompt: str) -> str:
    return ' '.join(prompt.lower().split())

def generate_explanation(prompt: str, model: str = 'gpt-3.5-turbo') -> str:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key: raise RuntimeError('OPENAI_API_KEY not set')
    url = 'https://api.openai.com/v1/chat/completions'
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    # Build system message with shared context
    system_message = SHARED_CONTEXT + "\n\nYou are an expert educator. Provide a concise explanation."
    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_message},
            {'role': 'user', 'content': f'Question: "{prompt}"'}
        ],
        'max_tokens': 256,
        'temperature': 0.7
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            return data['choices'][0]['message']['content'].strip()
    except urllib.error.HTTPError as e:
        error = e.read().decode()
        raise RuntimeError(f'HTTP {e.code}: {error}')

def enrich_and_dedup(source_dir: Path, output_file: Path, fmt: str, model: str, dry_run: bool):
    questions = load_questions_from_dir(source_dir)
    if not questions:
        print(f'Error: no questions found in {source_dir}')
        return
    # dedupe by normalized prompt
    unique = {}
    for q in questions:
        key = normalize_prompt(q.prompt)
        if key not in unique or (not unique[key].explanation and q.explanation):
            unique[key] = q
    merged = list(unique.values())
    print(f'Loaded {len(questions)} questions, deduped to {len(merged)}.')
    # generate missing explanations
    missing = [q for q in merged if not q.explanation]
    print(f'{len(missing)} questions missing explanations.')
    if not dry_run:
        for q in missing:
            try:
                q.explanation = generate_explanation(q.prompt, model)
                print(f'Explained: {q.prompt[:50]}...')
            except Exception as e:
                print(f'Error for "{q.prompt[:50]}...": {e}')
    # serialize
    data = [asdict(q) for q in merged]
    if dry_run:
        print(f'[DRY-RUN] Would write {len(data)} to {output_file}')
        return
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if fmt == 'json':
        with open(output_file, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)
    else:
        try:
            import yaml
            with open(output_file, 'w', encoding='utf-8') as f: yaml.safe_dump(data, f)
        except ImportError:
            raise RuntimeError('PyYAML required for YAML output')
    print(f'Wrote {len(data)} questions to {output_file}')

def main():
    parser = argparse.ArgumentParser(description='Manage Kubelingo question-data')
    sub = parser.add_subparsers(dest='cmd')
    org = sub.add_parser('organize', help='Archive and rename question-data files')
    org.add_argument('--dry-run', action='store_true')
    enr = sub.add_parser('enrich', help='Dedup and enrich questions with AI explanations')
    enr.add_argument('source_dir', type=Path)
    enr.add_argument('output_file', type=Path)
    enr.add_argument('--format', choices=['json','yaml'], default='json')
    enr.add_argument('--model', default='gpt-3.5-turbo')
    enr.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.cmd == 'organize':
        qd = Path(__file__).resolve().parent.parent / 'question-data'
        organize_question_data(qd, dry_run=args.dry_run)
    elif args.cmd == 'enrich':
        enrich_and_dedup(args.source_dir, args.output_file, args.format, args.model, args.dry_run)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()