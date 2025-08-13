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


def find_duplicate_yaml_files(directory: str) -> List[str]:
    """
    Finds duplicate YAML files in the specified directory based on the "answer" field.

    Args:
        directory: Path to the directory containing YAML files.

    Returns:
        A list of file paths to remove.
    """
    # Find all YAML files in the directory
    yaml_files = [str(p) for p in Path(directory).glob("*.yaml")]

    # Load YAML content
    yaml_data = load_yaml_files(yaml_files)

    # Find duplicates
    duplicates = find_duplicate_answers(yaml_data)
    files_to_remove = []

    # Collect duplicates for removal, keeping one file per set
    for duplicate_set in duplicates:
        # Keep the first file, mark the rest for removal
        files_to_remove.extend(duplicate_set[1:])

    return files_to_remove


def handle_deduplicate_files(args):
    """Handler for finding and suggesting removal of duplicate YAML files."""
    files_to_remove = find_duplicate_yaml_files(args.directory)

    if not files_to_remove:
        print("No duplicate files found.", file=sys.stderr)
        return

    print("# Found duplicate YAML files. To remove them, run the following commands:")
    # Use a set to handle any potential duplicates in the list, then sort for deterministic output
    unique_files_to_remove = sorted(list(set(files_to_remove)))
    for file_path in unique_files_to_remove:
        print(f"git rm '{file_path}'")

    print(f"\n# Total files to be removed: {len(unique_files_to_remove)}", file=sys.stderr)


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
        description="Scans a directory for YAML files with duplicate answers and prints 'git rm' commands for them."
    )
    parser_deduplicate_files.add_argument(
        'directory',
        help='Path to the directory containing YAML files to scan for duplicates.'
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
