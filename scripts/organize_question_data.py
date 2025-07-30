#!/usr/bin/env python3
"""
Script to organize, deduplicate, and rename question-data files for Kubelingo.
Moves legacy stubs and killercoda files to an archive,
renames core quiz JSON files for clarity, and simplifies Markdown filenames.
"""
import argparse
import shutil
import re
from pathlib import Path

def organize(root: Path, dry_run: bool = False):
    archive = root / '_archive'
    actions = []
    # Prepare archive subdirs
    for sub in ['json', 'yaml', 'csv', 'md']:
        (archive / sub).mkdir(parents=True, exist_ok=True)

    # 1. Remove legacy stub JSON files
    stub_json = ['ckad_questions.json', 'killercoda_ckad.json']
    for name in stub_json:
        src = root / 'json' / name
        if src.exists():
            dst = archive / 'json' / name
            actions.append((src, dst))

    # 2. Remove legacy stub YAML files
    stub_yaml = ['ckad_questions.yaml', 'ckad_questions.yml']
    for name in stub_yaml:
        src = root / 'yaml' / name
        if src.exists():
            dst = archive / 'yaml' / name
            actions.append((src, dst))

    # 3. Archive CSV files (e.g., killercoda data)
    csv_dir = root / 'csv'
    if csv_dir.exists() and csv_dir.is_dir():
        for f in csv_dir.iterdir():
            if f.is_file():
                dst = archive / 'csv' / f.name
                actions.append((f, dst))

    # 4. Rename Markdown files: strip leading letter prefix
    md_dir = root / 'md'
    if md_dir.exists() and md_dir.is_dir():
        for p in md_dir.iterdir():
            if not p.is_file():
                continue
            # move killercoda cheat sheet to archive
            if p.name.lower().startswith('killercoda'):
                dst = archive / 'md' / p.name
                actions.append((p, dst))
                continue
            m = re.match(r'^[a-z]\.(.+)\.md$', p.name)
            if m:
                new_name = f"{m.group(1)}.md"
                dst = md_dir / new_name
                actions.append((p, dst))

    # 5. Rename core JSON quiz files for clarity
    rename_map = {
        'ckad_quiz_data.json': 'kubernetes.json',
        'ckad_quiz_data_with_explanations.json': 'kubernetes_with_explanations.json',
        'yaml_edit_questions.json': 'yaml_edit.json',
        'vim_quiz_data.json': 'vim.json',
    }
    json_dir = root / 'json'
    for src_name, dst_name in rename_map.items():
        src = json_dir / src_name
        dst = json_dir / dst_name
        if src.exists():
            actions.append((src, dst))

    # Execute or preview actions
    for src, dst in actions:
        if dry_run:
            print(f"Would move: {src} -> {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            print(f"Moved: {src} -> {dst}")

    # Cleanup empty directories
    for sub in ['json', 'yaml', 'csv', 'md']:
        d = root / sub
        try:
            if d.exists() and d.is_dir() and not any(d.iterdir()):
                if dry_run:
                    print(f"Would remove empty directory: {d}")
                else:
                    d.rmdir()
                    print(f"Removed empty directory: {d}")
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(
        description='Organize question-data directory by archiving stubs and renaming files.'
    )
    parser.add_argument(
        '--dry-run', action='store_true', help='Show actions without making changes.'
    )
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    qd = repo_root / 'question-data'
    if not qd.exists():
        print(f"Error: question-data directory not found at {qd}")
        return
    organize(qd, dry_run=args.dry_run)

if __name__ == '__main__':
    main()