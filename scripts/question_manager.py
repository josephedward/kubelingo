#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A unified command-line interface for managing and maintaining Kubelingo questions.

This script consolidates the functionality of multiple question management scripts
into a single, subcommand-based tool.
"""
import argparse
import os
import sys
import sqlite3
import json
import re
import subprocess
import tempfile
import shutil
import hashlib
import logging
import difflib
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Set, Optional

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Third-party imports
try:
    import yaml
    from tqdm import tqdm
    import requests
    import openai
    import google.generativeai as genai
except ImportError as e:
    print(f"Missing required packages. Please install them: pip install PyYAML tqdm requests openai google-generativeai. Error: {e}", file=sys.stderr)
    sys.exit(1)

# AI packages are optional for AI-related subcommands
try:
    import openai
except ImportError:
    openai = None
try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Kubelingo imports
from kubelingo.database import (
    get_all_questions, get_db_connection, SUBJECT_MATTER, init_db,
    _row_to_question_dict
)
from kubelingo.question import Question, ValidationStep, QuestionCategory, QuestionSubject
# from kubelingo.modules.ai_categorizer import AICategorizer # NOTE: This is now handled locally
import kubelingo.utils.config as cfg
import kubelingo.database as db_mod
from kubelingo.utils.path_utils import get_all_yaml_files_in_repo, get_live_db_path, load_yaml_files
from kubelingo.utils.validation import find_duplicate_answers
from kubelingo.utils.ui import Fore, Style


def sha256_checksum(file_path: Path, block_size=65536) -> str:
    """Calculates the SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256.update(block)
    return sha256.hexdigest()


def find_duplicate_files_by_checksum(file_paths: List[Path]) -> Dict[str, List[Path]]:
    """Finds duplicate files from a list of Paths based on their content."""
    checksums = defaultdict(list)
    for file_path in file_paths:
        if file_path.is_file():
            try:
                checksum = sha256_checksum(file_path)
                checksums[checksum].append(file_path)
            except IOError as e:
                print(f"Warning: Could not read file {file_path}: {e}", file=sys.stderr)

    return {k: v for k, v in checksums.items() if len(v) > 1}


def find_duplicate_question_groups_by_answer(file_paths: List[Path]) -> List[List[Dict[str, Any]]]:
    """
    Finds groups of questions with identical answers from a list of YAML file paths.
    """
    answers_map = defaultdict(list)
    for file_path in file_paths:
        if not file_path.is_file():
            continue
        try:
            with file_path.open('r', encoding='utf-8') as f:
                # Support multi-document YAML files. Use UnsafeLoader to handle python-specific tags.
                # WARNING: Using UnsafeLoader is a security risk if the files are not from a trusted source.
                data_docs = yaml.load_all(f, Loader=yaml.UnsafeLoader)
                for data in data_docs:
                    if not data:
                        continue
                    qs_in_doc = []
                    if isinstance(data, dict) and 'questions' in data:
                        qs_in_doc = data.get('questions', [])
                    elif isinstance(data, list):
                        qs_in_doc = data

                    for q in qs_in_doc:
                        if isinstance(q, dict):
                            # Prioritize 'response' field, but also check for 'answer' as a fallback.
                            answer = q.get('response') or q.get('answer')
                            if isinstance(answer, list):
                                answer = " ".join(map(str, answer))

                            if answer and isinstance(answer, str):
                                answers_map[answer.strip()].append({
                                    'file_path': file_path,
                                    'prompt': q.get('prompt', ''), # Keep prompt for context in reporting
                                    'answer': answer.strip(),
                                    'question_data': q
                                })
        except Exception as e:
            print(f"Warning: Could not process file {file_path}: {e}", file=sys.stderr)

    # Filter for answers that have more than one question associated with them.
    duplicate_groups = [group for group in answers_map.values() if len(group) > 1]
    return duplicate_groups


def handle_deduplicate_files(args):
    """Handler for finding and reporting duplicate files."""
    file_paths = [Path(f) for f in args.files]

    if args.method == 'answer':
        # --- Deduplicate by exact answer content ---
        duplicate_question_groups = find_duplicate_question_groups_by_answer(file_paths)
        if not duplicate_question_groups:
            print("No duplicate questions found based on answer content.", file=sys.stderr)
            return

        print(f"# Found {len(duplicate_question_groups)} groups of questions with duplicate answers.")
        print("# It keeps the first file in each group (sorted by path) and suggests removing the others.")
        print("# Please review carefully before running the generated commands.")

        files_to_remove = set()
        for i, group in enumerate(duplicate_question_groups):
            group.sort(key=lambda x: str(x['file_path']))
            file_to_keep_info = group[0]
            print(f"\n# --- Group {i+1} ---")
            answer_to_show = str(file_to_keep_info.get('answer', '')).strip()
            print(f"# Answer: \"{answer_to_show}\"")
            print(f"# Keeping file: '{file_to_keep_info['file_path']}'")

            for item in group[1:]:
                file_to_delete = item['file_path']
                if file_to_delete != file_to_keep_info['file_path']:
                    files_to_remove.add(file_to_delete)
                    print(f"# Suggest removing file: '{file_to_delete}'")

        if not files_to_remove:
            print("\n# No files to suggest for removal (duplicate questions might be in the same file).")
            return

        print("\n\n# --- Suggested git rm commands ---")
        for p in sorted(list(files_to_remove)):
            print(f"git rm '{p}'")
        print(f"\n# Total files to be removed: {len(files_to_remove)}", file=sys.stderr)

    elif args.method == 'checksum':
        # --- Deduplicate by file content checksum ---
        duplicates = find_duplicate_files_by_checksum(file_paths)
        if not duplicates:
            print("No duplicate files found based on content checksum.", file=sys.stderr)
            return

        print("# Found duplicate files. Run the following commands to remove them:")
        files_to_remove = set()
        for checksum, paths in duplicates.items():
            paths.sort()
            file_to_keep = paths[0]
            print(f"\n# Duplicates with checksum {checksum} (keeping '{file_to_keep}')")
            for p in paths[1:]:
                files_to_remove.add(p)
                print(f"# Suggest removing file: '{p}'")

        if not files_to_remove:
            print("\n# No files to suggest for removal.")
            return

        print("\n\n# --- Suggested git rm commands ---")
        for p in sorted(list(files_to_remove)):
            print(f"git rm '{p}'")
        print(f"\n# Total files to be removed: {len(files_to_remove)}", file=sys.stderr)


# --- Main CLI Router ---
def main():
    """Main entry point for the question manager CLI."""
    parser = argparse.ArgumentParser(
        description="A unified CLI for managing Kubelingo questions.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', required=True, help='Action to perform')

    # Sub-parser for 'deduplicate-files'
    parser_deduplicate_files = subparsers.add_parser(
        'deduplicate-files',
        help='Find and report duplicate question files by content or by answer.',
        description="Finds duplicate files using different methods and suggests `git rm` commands."
    )
    parser_deduplicate_files.add_argument('files', nargs='+', help='File paths or glob patterns to check for duplicates (e.g., "questions/ai_generated/*.yaml").')
    parser_deduplicate_files.add_argument(
        '--method',
        choices=['checksum', 'answer'],
        default='checksum',
        help="Deduplication method:\n"
             " - checksum: Find files with identical content (fast, exact matches).\n"
             " - answer: Find questions with identical answers inside YAML files (slower, requires parsing).\n"
             "Default: checksum"
    )
    parser_deduplicate_files.set_defaults(func=handle_deduplicate_files)

    # Other subcommands...

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
