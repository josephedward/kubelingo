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


def handle_build_index(args):
    """Handler for building/updating the question index from YAML files."""
    print("Building question index from YAML files...")
    question_dir = Path(args.directory)
    if not question_dir.is_dir():
        print(f"Error: Directory not found at {question_dir}", file=sys.stderr)
        sys.exit(1)

    yaml_files = list(question_dir.rglob('*.yaml')) + list(question_dir.rglob('*.yml'))
    
    if not yaml_files:
        print(f"No YAML files found in {question_dir}", file=sys.stderr)
        return

    conn = db_mod.get_db_connection()
    try:
        db_mod.index_yaml_files(yaml_files, conn, verbose=not args.quiet)
        print("Index build complete.")
    finally:
        conn.close()


# --- Main CLI Router ---
def main():
    """Main entry point for the question manager CLI."""
    parser = argparse.ArgumentParser(
        description="A unified CLI for managing Kubelingo questions.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', required=True, help='Action to perform')


    # Sub-parser for 'build-index'
    parser_build_index = subparsers.add_parser(
        'build-index',
        help='Builds or updates the question index from YAML files.',
        description="Scans YAML files in a directory, hashes them, and updates the SQLite question database."
    )
    parser_build_index.add_argument(
        'directory',
        default='yaml/questions',
        nargs='?',
        help='Path to the directory containing YAML question files. Defaults to "yaml/questions".'
    )
    parser_build_index.add_argument(
        '--quiet',
        action='store_true',
        help="Suppress progress output."
    )
    parser_build_index.set_defaults(func=handle_build_index)


    # Other subcommands...

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
