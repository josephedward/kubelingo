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
from kubelingo.utils.path_utils import get_all_yaml_files_in_repo, get_live_db_path
from kubelingo.utils.validation import find_duplicate_answers
from kubelingo.utils.ui import Fore, Style


def handle_deduplicate_files(args):
    """
    Handler for finding and suggesting removal of duplicate YAML files based on answer content.
    """
    # Use a set for paths to automatically handle duplicates within the same file.
    answers_map = defaultdict(set)
    file_paths = [Path(f) for f in args.files]

    for file_path in file_paths:
        if not file_path.is_file():
            continue
        try:
            with file_path.open('r', encoding='utf-8') as f:
                # Use UnsafeLoader to handle python-specific tags, which are present in the YAML files.
                # WARNING: This is a security risk if the files are not from a trusted source.
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
                            # Check for 'answers', 'response', or 'answer' fields.
                            answer_val = q.get('answers') or q.get('response') or q.get('answer')
                            
                            answer_str = ""
                            if isinstance(answer_val, list):
                                # Strip each item before joining to handle whitespace variations
                                answer_str = " ".join(str(item).strip() for item in answer_val)
                            elif answer_val is not None:
                                answer_str = str(answer_val).strip()

                            if answer_str:
                                answers_map[answer_str].add(str(file_path))
        except Exception as e:
            print(f"Warning: Could not process file {file_path}: {e}", file=sys.stderr)

    files_to_remove = set()
    # A group is a duplicate if the same answer appears in more than one file.
    duplicate_groups = {k: v for k, v in answers_map.items() if len(v) > 1}

    if not duplicate_groups:
        print("No duplicate questions found based on answer content.", file=sys.stderr)
        return

    print(f"# Found {len(duplicate_groups)} groups of questions with duplicate answers.")
    print("# This tool suggests which files to remove based on exact answer matches.")
    print("# It keeps the first file in each group (sorted alphabetically) and suggests removing the others.")
    print("# Please review carefully before running the generated commands.")

    for answer, paths_set in duplicate_groups.items():
        # Sort for deterministic behavior
        paths = sorted(list(paths_set))
        file_to_keep = paths[0]
        print(f"\n# Answer: \"{answer}\"")
        print(f"#   Keeping: {file_to_keep}")
        
        for path_to_remove in paths[1:]:
            files_to_remove.add(path_to_remove)
            print(f"#   Removing: {path_to_remove}")

    if not files_to_remove:
        # This case can happen if duplicates are found but they are all in the same file.
        print("\n# No duplicate files to suggest for removal.")
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
        help='Find duplicate YAML files by answer and suggest removal commands.',
        description="Scans a list of YAML files for duplicate answers and prints 'git rm' commands for them."
    )
    parser_deduplicate_files.add_argument(
        'files',
        nargs='+',
        help='List of file paths or glob patterns to check for duplicates (e.g., "questions/ai_generated/*.yaml").'
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
