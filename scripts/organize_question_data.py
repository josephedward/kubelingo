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
    main()import os
import shutil
import argparse
import json
import logging
from pathlib import Path
import sys
import re

try:
    import openai
except ImportError:
    print("OpenAI Python client is not installed. Please run 'pip install openai'")
    sys.exit(1)

# Add project root to path to allow importing kubelingo modules
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.modules.kubernetes.session import load_questions

# --- Constants ---
QUESTION_DATA_DIR = project_root / 'question-data'
ARCHIVE_DIR = QUESTION_DATA_DIR / '_archive'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- AI Helper ---

def get_openai_client():
    """Initializes and returns the OpenAI client, checking for the API key."""
    if "OPENAI_API_KEY" not in os.environ:
        logging.warning("OPENAI_API_KEY environment variable not found.")
        return None
    return openai.OpenAI()

def generate_explanation(client, question):
    """Generates a concise explanation for a given question using an AI model."""
    prompt = question.get('prompt', '')
    response = question.get('response', '') or question.get('answer', '')

    if not prompt or not response:
        return None

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a Kubernetes expert who provides concise, one-sentence explanations for `kubectl` commands. The explanation should describe what the command does and why it's useful in a real-world scenario."
                },
                {
                    "role": "user",
                    "content": f"Question: \"{prompt}\"\nCommand: `{response}`\n\nExplanation:"
                }
            ],
            model="gpt-3.5-turbo",
            max_tokens=100,
            temperature=0.3,
        )
        explanation = chat_completion.choices[0].message.content.strip()
        # Clean up the explanation
        explanation = explanation.replace('"', '').strip()
        return explanation
    except Exception as e:
        logging.error(f"Error generating explanation for prompt '{prompt}': {e}")
        return None

# --- File Operations ---

def _move_to_archive(src_path, dry_run=False):
    if not src_path.exists():
        return
    dest_path = ARCHIVE_DIR / src_path.name
    logging.info(f"Archiving '{src_path}' to '{dest_path}'")
    if not dry_run:
        shutil.move(str(src_path), str(dest_path))

def organize_files(dry_run=False):
    """Organizes question data files as per the project specification."""
    logging.info("--- Starting file organization ---")
    if not dry_run:
        ARCHIVE_DIR.mkdir(exist_ok=True)

    # 1. Archive legacy stub files
    legacy_files = [
        "ckad_questions.yml",
        "killercoda_ckad_all.json", "killercoda_ckad_all.csv"
    ]
    for filename in legacy_files:
        _move_to_archive(QUESTION_DATA_DIR / "json" / filename, dry_run)
        _move_to_archive(QUESTION_DATA_DIR / "yaml" / filename, dry_run)
        _move_to_archive(QUESTION_DATA_DIR / "csv" / filename, dry_run)
        _move_to_archive(QUESTION_DATA_DIR / filename, dry_run)


    # 2. Strip prefixes from markdown files
    md_dir = QUESTION_DATA_DIR / "md"
    if md_dir.exists():
        for md_file in md_dir.glob("*.md"):
            if re.match(r'^[a-z]\.', md_file.name):
                new_name = re.sub(r'^[a-z]\.', '', md_file.name)
                new_path = md_dir / new_name
                logging.info(f"Renaming '{md_file.name}' to '{new_name}'")
                if not dry_run:
                    md_file.rename(new_path)

    # 3. Rename core JSON quizzes
    json_dir = QUESTION_DATA_DIR / "json"
    if json_dir.exists():
        rename_map = {
            "ckad_quiz_data.json": "kubernetes.json",
            "ckad_quiz_data_with_explanations.json": "kubernetes_with_explanations.json",
            "yaml_edit_questions.json": "yaml_edit.json",
            "vim_quiz_data.json": "vim.json"
        }
        for old_name, new_name in rename_map.items():
            old_path = json_dir / old_name
            new_path = json_dir / new_name
            if old_path.exists():
                logging.info(f"Renaming '{old_name}' to '{new_name}'")
                if not dry_run:
                    old_path.rename(new_path)

    # 4. Clean up empty subdirectories
    for subdir in QUESTION_DATA_DIR.iterdir():
        if subdir.is_dir() and not any(subdir.iterdir()) and subdir.name != '_archive':
            logging.info(f"Removing empty directory: '{subdir}'")
            if not dry_run:
                try:
                    shutil.rmtree(subdir)
                except OSError:
                    pass

    logging.info("--- File organization complete ---")

def enrich_and_deduplicate(target_file_path, ref_file_path, dry_run=False):
    """Enriches questions with AI explanations and de-duplicates them."""
    logging.info("--- Starting question enrichment and de-duplication ---")

    client = get_openai_client()
    if not client:
        logging.warning("Skipping enrichment as OpenAI client is not available.")
        return

    if not target_file_path.exists():
        logging.error(f"Target file not found: '{target_file_path}'.")
        return

    explained_prompts = set()
    if ref_file_path and ref_file_path.exists():
        ref_questions = load_questions(str(ref_file_path))
        explained_prompts = {q.get('prompt', '').strip() for q in ref_questions if q.get('explanation')}
        logging.info(f"Loaded {len(explained_prompts)} prompts with existing explanations from '{ref_file_path.name}'")
    else:
        logging.warning(f"Reference file '{ref_file_path}' not found. Skipping de-duplication.")

    with open(target_file_path, 'r', encoding='utf-8') as f:
        target_data_raw = json.load(f)

    is_nested = isinstance(target_data_raw, list) and target_data_raw and isinstance(target_data_raw[0], dict) and 'prompts' in target_data_raw[0]

    enriched_count = 0
    deduplicated_count = 0

    if is_nested:
        final_data = []
        for category_group in target_data_raw:
            prompts_to_keep = []
            for question in category_group.get('prompts', []):
                prompt_text = question.get('prompt', '').strip()
                if prompt_text in explained_prompts:
                    deduplicated_count += 1
                    logging.info(f"De-duplicating question (already has explanation): \"{prompt_text[:50]}...\"")
                    continue
                if not question.get('explanation'):
                    logging.info(f"Generating explanation for: \"{prompt_text[:50]}...\"")
                    if not dry_run:
                        explanation = generate_explanation(client, question)
                        if explanation:
                            question['explanation'] = explanation
                            enriched_count += 1
                    else:
                        enriched_count += 1
                prompts_to_keep.append(question)
            category_group['prompts'] = prompts_to_keep
            if prompts_to_keep:
                final_data.append(category_group)
    else: # Flat structure
        final_data = []
        for question in target_data_raw:
            prompt_text = question.get('prompt', '').strip()
            if prompt_text in explained_prompts:
                deduplicated_count += 1
                logging.info(f"De-duplicating question (already has explanation): \"{prompt_text[:50]}...\"")
                continue
            if not question.get('explanation'):
                logging.info(f"Generating explanation for: \"{prompt_text[:50]}...\"")
                if not dry_run:
                    explanation = generate_explanation(client, question)
                    if explanation:
                        question['explanation'] = explanation
                        enriched_count += 1
                else:
                    enriched_count += 1
            final_data.append(question)

    logging.info(f"Enriched {enriched_count} questions with new explanations.")
    logging.info(f"Removed {deduplicated_count} duplicate questions.")

    if not dry_run:
        with open(target_file_path, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2)
        logging.info(f"Successfully updated '{target_file_path}'")

    logging.info("--- Question enrichment and de-duplication complete ---")

def main():
    parser = argparse.ArgumentParser(description="Organize and enrich Kubelingo question data.")
    parser.add_argument('--dry-run', action='store_true', help="Show what would be done, but don't make changes.")
    parser.add_argument('--organize-only', action='store_true', help="Only perform file organization.")
    parser.add_argument('--enrich-only', action='store_true', help="Only perform AI enrichment and de-duplication.")
    parser.add_argument('--enrich-file', type=Path, help="Path to a specific JSON question file to enrich.")
    parser.add_argument('--dedupe-ref-file', type=Path, help="Reference file with explanations for de-duplication.")
    args = parser.parse_args()

    run_organize = not args.enrich_only
    run_enrich = not args.organize_only

    if run_organize:
        organize_files(dry_run=args.dry_run)

    if run_enrich:
        json_dir = QUESTION_DATA_DIR / "json"
        target_file = args.enrich_file if args.enrich_file else json_dir / "kubernetes.json"
        ref_file = args.dedupe_ref_file if args.dedupe_ref_file else json_dir / "kubernetes_with_explanations.json"

        enrich_and_deduplicate(target_file, ref_file, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
