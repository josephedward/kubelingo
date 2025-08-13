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


def interactive_question_manager_menu():
    """Interactive menu for question manager script."""
    try:
        import questionary
    except ImportError:
        print("Error: Required packages are missing. Please install them using: pip install questionary", file=sys.stderr)
        sys.exit(1)
        
    class MockArgs:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    while True:
        choice = questionary.select(
            "Select a command:",
            choices=["build-index", "list-triage", "triage-question", "untriage-question", "Exit"],
        ).ask()

        if choice == "Exit" or choice is None:
            print("Exiting question manager.")
            break
        elif choice == "build-index":
            directory = questionary.text('Path to the directory containing YAML question files?', default='yaml/questions').ask()
            if not directory: continue
            quiet = questionary.confirm("Suppress progress output?", default=False).ask()
            handle_build_index(MockArgs(directory=directory, quiet=quiet))
        elif choice == "list-triage":
            handle_list_triaged(MockArgs())
        elif choice == "triage-question":
            qid = questionary.text("Enter the ID of the question to triage:").ask()
            if qid: handle_set_triage_status(MockArgs(question_id=qid, un_triage=False))
        elif choice == "untriage-question":
            qid = questionary.text("Enter the ID of the question to un-triage:").ask()
            if qid: handle_set_triage_status(MockArgs(question_id=qid, un_triage=True))

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


def handle_list_triaged(args):
    """Lists all questions marked for triage."""
    conn = db_mod.get_db_connection()
    if not conn:
        print("Could not connect to database.", file=sys.stderr)
        sys.exit(1)
    try:
        # Assuming triage is a boolean column
        cursor = conn.cursor()
        # I am assuming a `triage` column exists based on the design document.
        cursor.execute("SELECT id, prompt FROM questions WHERE triage = 1")
        rows = cursor.fetchall()
        if not rows:
            print("No triaged questions found.")
        else:
            print(f"Found {len(rows)} triaged questions:")
            for row in rows:
                print(f"  - ID: {row[0]}\n    Prompt: {row[1][:100]}...")
    except Exception as e:
        print(f"Error listing triaged questions: {e}", file=sys.stderr)
        # Suggest a possible fix if the column is missing
        if "no such column: triage" in str(e):
            print("Hint: The 'triage' column might be missing. You may need to update your database schema.", file=sys.stderr)
    finally:
        conn.close()


def handle_set_triage_status(args):
    """Sets the triage status for a given question ID."""
    conn = db_mod.get_db_connection()
    if not conn:
        print("Could not connect to database.", file=sys.stderr)
        sys.exit(1)
    
    status_bool = not args.un_triage # True for triage, False for un-triage

    try:
        cursor = conn.cursor()
        # I am assuming a `triage` column exists based on the design document.
        cursor.execute("UPDATE questions SET triage = ? WHERE id = ?", (status_bool, args.question_id))
        if cursor.rowcount == 0:
            print(f"Error: Question with ID '{args.question_id}' not found.")
        else:
            conn.commit()
            action = "Triaged" if status_bool else "Un-triaged"
            print(f"Successfully {action} question with ID '{args.question_id}'.")
    except Exception as e:
        print(f"Error updating triage status: {e}", file=sys.stderr)
        if "no such column: triage" in str(e):
            print("Hint: The 'triage' column might be missing. You may need to update your database schema.", file=sys.stderr)
    finally:
        conn.close()


# --- Main CLI Router ---
def main():
    """Main entry point for the question manager CLI."""
    if len(sys.argv) > 1:
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

        # Sub-parser for 'list-triage'
        parser_list_triage = subparsers.add_parser('list-triage', help='Lists all questions marked for triage.')
        parser_list_triage.set_defaults(func=handle_list_triaged)

        # Sub-parser for 'triage'
        parser_triage = subparsers.add_parser('triage', help='Marks a question for triage.')
        parser_triage.add_argument('question_id', help='The ID of the question to triage.')
        parser_triage.set_defaults(func=handle_set_triage_status, un_triage=False)

        # Sub-parser for 'untriage'
        parser_untriage = subparsers.add_parser('untriage', help='Removes a question from triage.')
        parser_untriage.add_argument('question_id', help='The ID of the question to un-triage.')
        parser_untriage.set_defaults(func=handle_set_triage_status, un_triage=True)


        args = parser.parse_args()
        if hasattr(args, 'func'):
            args.func(args)
        else:
            parser.print_help()
    else:
        interactive_question_manager_menu()


if __name__ == '__main__':
    main()
