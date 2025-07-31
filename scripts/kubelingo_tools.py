#!/usr/bin/env python3
"""Kubelingo Tools: Unified script for question-data management, quiz manifest generation,
CKAD spec management, and interactive CLI quiz runner."""

import argparse
import sys
import subprocess
import shutil
import json
import re
import os
from pathlib import Path

# Determine directories
scripts_dir = Path(__file__).resolve().parent
repo_root = scripts_dir.parent

# Load shared context for AI prompts
shared_context_path = repo_root / 'shared_context.md'
if shared_context_path.exists():
    SHARED_CONTEXT = shared_context_path.read_text(encoding='utf-8')
else:
    SHARED_CONTEXT = ''

# Adjust sys.path to import local helper modules
sys.path.insert(0, str(scripts_dir))

def run_quiz(args):
    """Run the interactive CLI quiz."""
    # Forward remaining args to kubelingo CLI
    sys.argv = ['kubelingo'] + args.quiz_args
    from kubelingo.cli import main as kubelingo_main
    kubelingo_main()

def manage_organize(args):
    """Archive legacy stubs and rename core question-data files."""
    root = repo_root / 'question-data'
    dry_run = args.dry_run
    archive = root / '_archive'
    # Prepare archive subdirs
    for sub in ['json', 'yaml', 'csv', 'md']:
        (archive / sub).mkdir(parents=True, exist_ok=True)
    actions = []
    # Stubs to archive
    for name in ['ckad_questions.json', 'killercoda_ckad.json']:
        src = root / 'json' / name
        if src.exists():
            actions.append((src, archive / 'json' / name))
    for name in ['ckad_questions.yaml', 'ckad_questions.yml']:
        src = root / 'yaml' / name
        if src.exists():
            actions.append((src, archive / 'yaml' / name))
    # CSV files
    for f in (root / 'csv').glob('*'):
        if f.is_file():
            actions.append((f, archive / 'csv' / f.name))
    # Markdown: strip letter prefixes and archive Killercoda cheat sheet
    md_dir = root / 'md'
    if md_dir.is_dir():
        for p in md_dir.iterdir():
            if not p.is_file():
                continue
            if p.name.lower().startswith('killercoda'):
                actions.append((p, archive / 'md' / p.name))
            else:
                m = re.match(r'^[a-z]\.(.+)', p.name)
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
    for old_name, new_name in rename_map.items():
        src = root / 'json' / old_name
        dst = root / 'json' / new_name
        if src.exists():
            actions.append((src, dst))
    # Execute actions
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
                try:
                    d.rmdir()
                    print(f"Removed empty dir: {d}")
                except OSError:
                    pass

def manage_enrich(args):
    """Deduplicate questions and generate AI explanations for missing ones."""
    try:
        import manage_questions as mq
    except ImportError:
        print("Error: manage_questions module not found.", file=sys.stderr)
        return
    mq.enrich_and_dedup(
        args.source_dir,
        args.output_file,
        args.format,
        args.model,
        args.dry_run
    )

def manage_validate(args):
    """Generate validation_steps via AI for questions missing them in a JSON file."""
    try:
        from organize_question_data import generate_validation_steps
    except ImportError:
        print("Error: organize_question_data module not found.", file=sys.stderr)
        return
    file_path = args.file
    model = args.model
    dry_run = args.dry_run
    # Load data
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Flatten nested or flat list
    key = None
    if isinstance(data, list) and data and isinstance(data[0], dict):
        if 'questions' in data[0]:
            key = 'questions'
        elif 'prompts' in data[0]:
            key = 'prompts'
    if key:
        question_list = []
        for cat in data:
            question_list.extend(cat.get(key, []))
    else:
        question_list = data
    to_update = [q for q in question_list if not q.get('validation_steps')]
    if not to_update:
        print("No questions need validation steps.")
        return
    updated = 0
    for q in to_update:
        steps = generate_validation_steps(q, model=model, dry_run=dry_run)
        if steps:
            q['validation_steps'] = steps
            updated += 1
            print(f"Generated validation steps for: {q.get('prompt','')[:50]}...")
    if updated and not dry_run:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"Updated {updated} questions in {file_path}")

def generate_operations(args):
    """Generate the Kubectl operations quiz manifest (delegates to existing script)."""
    script = scripts_dir / 'generate_kubectl_operations_quiz.py'
    subprocess.run([sys.executable, str(script)], check=True)

def generate_reference(args):
    """Generate the Resource Reference quiz manifest (delegates to existing script)."""
    script = scripts_dir / 'generate_resource_reference_quiz.py'
    subprocess.run([sys.executable, str(script)], check=True)

def generate_manifests(args):
    """Generate quiz manifests and solutions from JSON quiz data (delegates to existing script)."""
    script = scripts_dir / 'generate_manifests.py'
    subprocess.run([sys.executable, str(script)], check=True)

def ckad_export(args):
    """Export CKAD spec CSV to JSON and YAML (delegates to existing script)."""
    script = scripts_dir / 'ckad.py'
    cmd = [sys.executable, str(script), 'export', '--csv', args.csv, '--json', args.json, '--yaml', args.yaml]
    subprocess.run(cmd, check=True)

def ckad_import(args):
    """Import CKAD spec JSON/YAML to CSV (delegates to existing script)."""
    script = scripts_dir / 'ckad.py'
    cmd = [sys.executable, str(script), 'import', '--json', args.json, '--yaml', args.yaml, '--csv', args.csv]
    subprocess.run(cmd, check=True)

def ckad_normalize(args):
    """Normalize CKAD CSV (delegates to existing script)."""
    script = scripts_dir / 'ckad.py'
    cmd = [sys.executable, str(script), 'normalize', '--input', args.input, '--output', args.output]
    subprocess.run(cmd, check=True)

def main():
    parser = argparse.ArgumentParser(description='Kubelingo umbrella tools')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # quiz
    quiz_parser = subparsers.add_parser('quiz', help='Run the interactive CLI quiz')
    quiz_parser.add_argument('quiz_args', nargs=argparse.REMAINDER, help='Arguments forwarded to kubelingo CLI')
    quiz_parser.set_defaults(func=run_quiz)

    # manage
    manage_parser = subparsers.add_parser('manage', help='Manage question-data')
    manage_sub = manage_parser.add_subparsers(dest='subcommand', required=True)
    org_p = manage_sub.add_parser('organize', help='Archive and rename question-data files')
    org_p.add_argument('--dry-run', action='store_true', help='Preview changes without writing files')
    org_p.set_defaults(func=manage_organize)
    enr_p = manage_sub.add_parser('enrich', help='Dedupe and AI-enrich question-data')
    enr_p.add_argument('source_dir', type=Path, help='Source directory of question files')
    enr_p.add_argument('output_file', type=Path, help='Output file for enriched questions')
    enr_p.add_argument('--format', choices=['json','yaml'], default='json', help='Output format')
    enr_p.add_argument('--model', default='gpt-3.5-turbo', help='AI model for explanations')
    enr_p.add_argument('--dry-run', action='store_true', help='Preview API calls and no file writes')
    enr_p.set_defaults(func=manage_enrich)
    val_p = manage_sub.add_parser('validate', help='Generate AI-based validation steps')
    val_p.add_argument('file', type=Path, help='Question file (JSON or nested)')
    val_p.add_argument('--model', default='gpt-4-turbo', help='AI model for validation steps')
    val_p.add_argument('--dry-run', action='store_true', help='Preview API calls')
    val_p.set_defaults(func=manage_validate)

    # generate
    gen_parser = subparsers.add_parser('generate', help='Generate quiz manifests')
    gen_sub = gen_parser.add_subparsers(dest='subcommand', required=True)
    gen_ops = gen_sub.add_parser('operations', help='Generate Kubectl operations quiz')
    gen_ops.set_defaults(func=generate_operations)
    gen_ref = gen_sub.add_parser('reference', help='Generate Resource Reference quiz')
    gen_ref.set_defaults(func=generate_reference)
    gen_man = gen_sub.add_parser('manifests', help='Generate manifests and solutions from JSON quiz data')
    gen_man.set_defaults(func=generate_manifests)

    # ckad
    ckad_parser = subparsers.add_parser('ckad', help='CKAD CSV/JSON/YAML spec management')
    ckad_sub = ckad_parser.add_subparsers(dest='subcommand', required=True)
    exp = ckad_sub.add_parser('export', help='Export CSV to JSON and YAML spec')
    exp.add_argument('--csv', default=str(repo_root / 'killercoda-ckad_072425.csv'), help='Input CSV path')
    exp.add_argument('--json', default=str(scripts_dir / 'ckad_questions.json'), help='Output JSON path')
    exp.add_argument('--yaml', default=str(scripts_dir / 'ckad_questions.yaml'), help='Output YAML path')
    exp.set_defaults(func=ckad_export)
    imp = ckad_sub.add_parser('import', help='Import spec to regenerate CSV')
    imp.add_argument('--json', default=str(scripts_dir / 'ckad_questions.json'), help='Input JSON path')
    imp.add_argument('--yaml', default=str(scripts_dir / 'ckad_questions.yaml'), help='Input YAML path')
    imp.add_argument('--csv', default=str(repo_root / 'killercoda-ckad_072425.csv'), help='Output CSV path')
    imp.set_defaults(func=ckad_import)
    norm = ckad_sub.add_parser('normalize', help='Normalize CSV (flatten prompts, extract YAML answers)')
    norm.add_argument('--input', default=str(repo_root / 'killercoda-ckad_072425.csv'), help='Input CSV path')
    norm.add_argument('--output', default=str(repo_root / 'killercoda-ckad_normalized.csv'), help='Output CSV path')
    norm.set_defaults(func=ckad_normalize)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()