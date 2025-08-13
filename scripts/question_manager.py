#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A unified command-line interface for managing and maintaining Kubelingo questions and YAML files.
"""
import argparse
import os
import sys
import sqlite3
import datetime
import shutil
import logging
import uuid
import subprocess
import json
import time
import tempfile
import re
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Dict, Any, Set, Tuple

# Add project root to path to allow imports from kubelingo
try:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    import yaml
    from tqdm import tqdm
    from rich.console import Console
    from rich.progress import track
    import llm
    import questionary

    # Kubelingo imports
    import kubelingo.database as db_mod
    from kubelingo.database import (
        get_db_connection, add_question, init_db, _row_to_question_dict, get_all_questions
    )
    from kubelingo.question import Question
    from kubelingo.modules.db_loader import DBLoader
    from kubelingo.modules.yaml_loader import YAMLLoader
    from kubelingo.modules.ai_categorizer import AICategorizer
    from kubelingo.utils import path_utils
    from kubelingo.utils.path_utils import (
        get_project_root, get_live_db_path, find_yaml_files_from_paths,
        get_all_question_dirs, get_all_yaml_files_in_repo, find_and_sort_files_by_mtime,
        find_yaml_files
    )
    from kubelingo.utils.config import (
        YAML_BACKUP_DIRS, DATABASE_FILE, ENABLED_QUIZZES, QUESTION_DIRS
    )
    from kubelingo.utils.ui import Fore, Style

    # Define a default backup file path, similar to other manager scripts.
    BACKUP_DATABASE_FILE = project_root / "backups" / "kubelingo.db"
    YAML_QUIZ_BACKUP_DIR = project_root / "question-data" / "yaml-bak"
except ImportError as e:
    print(f"Error: A required module is not available: {e}. "
          "Please ensure all dependencies are installed and you run this from the project root.", file=sys.stderr)
    sys.exit(1)


# --- Handlers from original question_manager.py ---

def interactive_question_manager_menu():
    """Interactive menu for question manager script."""
    class MockArgs:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    while True:
        choice = questionary.select(
            "Select a command:",
            choices=["build-index", "list-triage", "triage-question", "untriage-question", "remove-question", "Exit"],
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
        elif choice == "remove-question":
            qid = questionary.text("Enter the ID of the question to remove:").ask()
            if qid: handle_remove_question(MockArgs(question_id=qid))


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
        cursor = conn.cursor()
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

def handle_remove_question(args):
    """Deletes a question from the database by its ID."""
    conn = db_mod.get_db_connection()
    if not conn:
        print("Could not connect to database.", file=sys.stderr)
        sys.exit(1)
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT prompt FROM questions WHERE id = ?", (args.question_id,))
        row = cursor.fetchone()
        if not row:
            print(f"Error: Question with ID '{args.question_id}' not found.")
            return

        confirm = questionary.confirm(f"Are you sure you want to delete question '{args.question_id}' ({row[0][:50]}...)?").ask()
        if not confirm:
            print("Deletion cancelled.")
            return

        cursor.execute("DELETE FROM questions WHERE id = ?", (args.question_id,))
        if cursor.rowcount == 0:
            print(f"Error: Question with ID '{args.question_id}' not found during deletion.")
        else:
            conn.commit()
            print(f"Successfully deleted question with ID '{args.question_id}'.")
    except Exception as e:
        print(f"Error deleting question: {e}", file=sys.stderr)
    finally:
        conn.close()


# --- Functions from original yaml_manager.py ---

def do_consolidate(args):
    """
    Finds all YAML quiz files, extracts unique questions based on their 'prompt',
    and consolidates them into a single YAML file.
    """
    output_file = Path(args.output) if args.output else \
        Path(project_root) / 'backups' / 'yaml' / f'consolidated_unique_questions_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.yaml'

    print(f"{Fore.CYAN}--- Consolidating unique YAML questions ---{Style.RESET_ALL}")

    try:
        all_yaml_files = get_all_yaml_files_in_repo()
        print(f"Found {len(all_yaml_files)} YAML files to scan in the repository.")
    except Exception as e:
        print(f"{Fore.RED}Error finding YAML files: {e}{Style.RESET_ALL}")
        return

    unique_questions: List[Dict[str, Any]] = []
    seen_prompts: Set[str] = set()
    total_questions_count = 0
    files_with_questions_count = 0

    for file_path in all_yaml_files:
        questions_in_file = []
        try:
            with file_path.open('r', encoding='utf-8') as f:
                documents = yaml.safe_load_all(f)
                for data in documents:
                    if not data:
                        continue
                    if isinstance(data, dict) and 'questions' in data and isinstance(data.get('questions'), list):
                        questions_in_file.extend(data['questions'])
                    elif isinstance(data, list):
                        questions_in_file.extend(data)

        except (yaml.YAMLError, IOError):
            continue

        if questions_in_file:
            files_with_questions_count += 1
            for question in questions_in_file:
                if isinstance(question, dict) and 'prompt' in question:
                    total_questions_count += 1
                    prompt = question.get('prompt')
                    if prompt and prompt not in seen_prompts:
                        seen_prompts.add(prompt)
                        unique_questions.append(question)

    print(f"Scanned {len(all_yaml_files)} YAML files.")
    print(f"Processed {files_with_questions_count} files containing questions.")
    print(f"Found {total_questions_count} questions in total, with {len(unique_questions)} being unique.")

    if not unique_questions:
        print(f"{Fore.YELLOW}No unique questions found to consolidate.{Style.RESET_ALL}")
        return

    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump({'questions': unique_questions}, f, sort_keys=False, indent=2)
        print(f"\n{Fore.GREEN}Successfully consolidated {len(unique_questions)} unique questions to:{Style.RESET_ALL}")
        print(str(output_file))
    except IOError as e:
        print(f"{Fore.RED}Error writing to output file {output_file}: {e}{Style.RESET_ALL}")


def _process_with_gemini(prompt, model="gemini-2.0-flash"):
    """Uses the llm-gemini plugin to process a prompt with the specified model."""
    try:
        model_instance = llm.get_model(model)
        response = model_instance.prompt(prompt)
        return response.text().strip()
    except Exception as e:
        logging.error(f"Error processing with Gemini: {e}")
        return None

def _add_question_for_create_quizzes(conn, id, prompt, source_file, response, category, source, validation_steps, validator, review):
    """Adds a question to the database, handling JSON serialization for complex fields."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO questions (
                id, prompt, source_file, response, category, source,
                validation_steps, validator, review
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                prompt=excluded.prompt,
                source_file=excluded.source_file,
                response=excluded.response,
                category=excluded.category,
                source=excluded.source,
                validation_steps=excluded.validation_steps,
                validator=excluded.validator,
                review=excluded.review;
        """, (
            id, prompt, str(source_file), response, category, source,
            json.dumps(validation_steps) if validation_steps is not None else None,
            json.dumps(validator) if validator is not None else None,
            review
        ))
    except sqlite3.Error as e:
        logging.error(f"Failed to add question {id}: {e}")

def do_create_quizzes(args):
    """Indexes YAML files from a consolidated backup and populates the database."""
    logging.info("Starting to create quizzes from consolidated YAML backup.")
    
    proj_root = get_project_root()
    yaml_dir = proj_root / 'yaml'

    logging.info(f"Looking for consolidated question files in: {yaml_dir}")

    if not yaml_dir.is_dir():
        logging.error(f"YAML directory not found at: {yaml_dir}")
        return

    logging.info("Scanning for latest consolidated question file...")
    consolidated_files = sorted(yaml_dir.glob('consolidated_unique_questions_*.yaml'), reverse=True)

    if not consolidated_files:
        logging.warning(f"No 'consolidated_unique_questions_*.yaml' files found in '{yaml_dir}'.")
        return
    
    latest_file = consolidated_files[0]
    yaml_files = [latest_file]

    logging.info(f"Found latest consolidated file. Processing: {latest_file}")
    
    db_path = ":memory:"
    conn = get_db_connection(db_path)
    init_db(db_path=db_path, clear=True)
    logging.info("In-memory database initialized and schema created.")

    question_count = 0
    
    for yaml_file in yaml_files:
        logging.info(f"Processing file: {yaml_file}")
        try:
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)

            if isinstance(data, dict):
                questions_data = data.get('questions')
            else:
                questions_data = data

            if not isinstance(questions_data, list):
                logging.error(f"Skipping file {yaml_file}: Expected a list of questions, but got {type(questions_data)}.")
                continue

            for q_data in questions_data:
                q_id = q_data.get('id')
                q_type = q_data.get('type')
                
                exercise_category = q_type
                if not exercise_category:
                    logging.warning(f"Skipping question {q_id} in {yaml_file}: missing type.")
                    continue
                
                prompt = q_data.get('prompt')
                if not prompt:
                    logging.warning(f"Skipping question {q_id}: Missing 'prompt'.")
                    continue

                if q_type == 'manifest':
                    if 'vim' not in q_data.get('tools', []):
                        logging.warning(f"Skipping manifest question {q_id}: 'vim' tool is required.")
                        continue
                    if 'kubectl apply' not in q_data.get('validation', []):
                        logging.warning(f"Skipping manifest question {q_id}: 'kubectl apply' validation is required.")
                        continue

                _add_question_for_create_quizzes(
                    conn=conn, id=q_id, prompt=prompt, source_file=str(yaml_file),
                    response=q_data.get('response'), category=exercise_category,
                    source=q_data.get('source'), validation_steps=q_data.get('validation'),
                    validator=q_data.get('validator'), review=q_data.get('review', False)
                )
                question_count += 1
                logging.info(f"Added question ID: {q_id} with category '{exercise_category}'.")

        except yaml.YAMLError as e:
            logging.error(f"Error parsing YAML file {yaml_file}: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while processing {yaml_file}: {e}")
    
    if question_count > 0:
        conn.commit()
        logging.info(f"Successfully added {question_count} questions to the in-memory database.")

        live_db_path = Path(get_live_db_path())
        dump_filename = f"quiz_dump_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        dump_path = live_db_path.parent / dump_filename
        
        with open(dump_path, 'w') as f:
            for line in conn.iterdump():
                f.write(f'{line}\n')
        
        logging.info(f"Database dump created at: {dump_path}")
        logging.info(f"To load this dump into your main database, run:")
        logging.info(f"sqlite3 '{live_db_path}' < '{dump_path}'")
    else:
        logging.info("No new questions were added to the database.")
        
    conn.close()
    logging.info("Quiz creation process finished.")

def _question_to_key(q: Question) -> str:
    """Creates a canonical, hashable key from a Question object for deduplication."""
    d = asdict(q)
    d.pop('id', None)
    d.pop('source_file', None)
    cleaned_dict = {k: v for k, v in d.items() if v is not None}
    return json.dumps(cleaned_dict, sort_keys=True, default=str)

def do_deduplicate(args):
    """Deduplicate YAML questions in a directory and consolidate them."""
    source_dir = Path(args.directory)
    if not source_dir.is_dir():
        print(f"Error: Directory not found at '{source_dir}'")
        exit(1)
    output_file = Path(args.output_file) if args.output_file else source_dir / "unique_questions.yaml"
    loader = YAMLLoader()
    yaml_files = list(source_dir.rglob("*.yaml")) + list(source_dir.rglob("*.yml"))
    if not yaml_files:
        print(f"No YAML files found in '{source_dir}'.")
        return
    print(f"Found {len(yaml_files)} YAML files to process...")
    unique_questions: Dict[str, Question] = {}
    total_questions = 0
    duplicates_found = 0
    for file_path in yaml_files:
        try:
            questions = loader.load_file(str(file_path))
            total_questions += len(questions)
            for q in questions:
                key = _question_to_key(q)
                if key not in unique_questions:
                    unique_questions[key] = q
                else:
                    duplicates_found += 1
        except Exception as e:
            print(f"Warning: Could not process file {file_path}: {e}")
            continue
    print("\nScan complete.")
    print(f"  - Total questions found: {total_questions}")
    print(f"  - Duplicate questions found: {duplicates_found}")
    print(f"  - Unique questions: {len(unique_questions)}")
    if args.dry_run:
        print("\nDry run enabled. No files will be written.")
        return
    questions_for_yaml = [asdict(q) for q in unique_questions.values()]
    cleaned_questions_for_yaml = []
    for q_dict in questions_for_yaml:
        cleaned_questions_for_yaml.append({k: v for k, v in q_dict.items() if v is not None})
    output_data = {"questions": cleaned_questions_for_yaml}
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(output_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        print(f"\nSuccessfully wrote {len(unique_questions)} unique questions to '{output_file}'.")
    except IOError as e:
        print(f"\nError writing to output file '{output_file}': {e}")
        exit(1)

def _compare_questions(questions1: List[Question], questions2: List[Question]):
    """Compares two lists of Question objects and prints the differences."""
    q1_map = {q.id: q for q in questions1}
    q2_map = {q.id: q for q in questions2}
    added_ids = q2_map.keys() - q1_map.keys()
    removed_ids = q1_map.keys() - q2_map.keys()
    common_ids = q1_map.keys() & q2_map.keys()
    modified_ids = []
    for q_id in common_ids:
        if str(q1_map[q_id]) != str(q2_map[q_id]):
            modified_ids.append(q_id)
    if added_ids:
        print(f"--- Added ({len(added_ids)}) ---")
        for q_id in sorted(list(added_ids)): print(f"  + {q_id}")
    if removed_ids:
        print(f"--- Removed ({len(removed_ids)}) ---")
        for q_id in sorted(list(removed_ids)): print(f"  - {q_id}")
    if modified_ids:
        print(f"--- Modified ({len(modified_ids)}) ---")
        for q_id in sorted(modified_ids): print(f"  ~ {q_id}")
    if not any([added_ids, removed_ids, modified_ids]):
        print("No changes detected.")
    print("-" * 20)

def do_diff(args):
    """Diff YAML backup files to track changes in questions."""
    loader = YAMLLoader()
    if len(args.files) == 2:
        path1, path2 = Path(args.files[0]), Path(args.files[1])
        if not path1.is_file() or not path2.is_file():
            print("Error: One or both files not found.", file=sys.stderr)
            sys.exit(1)
        print(f"Comparing {path1.name} to {path2.name}...")
        questions1 = loader.load_file(str(path1))
        questions2 = loader.load_file(str(path2))
        _compare_questions(questions1, questions2)
    elif len(args.files) == 0:
        print(f"No files specified. Discovering backups in: {', '.join(YAML_BACKUP_DIRS)}")
        try:
            all_files = find_yaml_files_from_paths(YAML_BACKUP_DIRS)
        except Exception as e:
            print(f"Error scanning directories: {e}", file=sys.stderr)
            sys.exit(1)
        if len(all_files) < 2:
            print("Not enough backup files found to compare.", file=sys.stderr)
            sys.exit(1)
        sorted_files = sorted(all_files, key=lambda p: p.stat().st_mtime)
        files_to_compare = sorted_files
        if args.range.lower() != 'all':
            try:
                num = int(args.range)
                if num < 1: raise ValueError
                if len(sorted_files) > num: files_to_compare = sorted_files[-(num + 1):]
            except (ValueError, TypeError):
                print(f"Invalid range: '{args.range}'. Please provide a positive integer or 'all'.", file=sys.stderr)
                sys.exit(1)
        if len(files_to_compare) < 2:
            print("Not enough backup files in the specified range to compare.", file=sys.stderr)
            sys.exit(1)
        print(f"Found {len(sorted_files)} backups. Comparing {len(files_to_compare) - 1} version(s) sequentially...")
        for i in range(len(files_to_compare) - 1):
            path1, path2 = files_to_compare[i], files_to_compare[i + 1]
            print(f"\nComparing {path1.name} -> {path2.name}")
            questions1 = loader.load_file(str(path1))
            questions2 = loader.load_file(str(path2))
            _compare_questions(questions1, questions2)
    else:
        print("Please provide either two files to compare, or no files to compare all backups.", file=sys.stderr)
        sys.exit(1)

def _export_db_to_yaml_func(output_file: str, db_path: Optional[str] = None) -> int:
    """Exports questions from the database to a YAML file."""
    conn = get_db_connection(db_path=db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM questions")
    rows = cur.fetchall()
    conn.close()
    data = [_row_to_question_dict(row) for row in rows]
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
    print(f"Exported {len(data)} questions to {output_file}")
    return len(data)

def do_export(args):
    """Export questions DB to YAML."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.output:
        out_file = args.output
    else:
        out_dir = YAML_BACKUP_DIRS[0] if YAML_BACKUP_DIRS else "backups"
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, f"questions_{timestamp}.yaml")
    _export_db_to_yaml_func(out_file)

def do_import_ai(args):
    """Import questions from YAML files into a new SQLite database with AI-powered categorization."""
    if os.path.exists(args.output_db):
        overwrite = input(f"{Fore.YELLOW}Warning: Output database '{args.output_db}' already exists. Overwrite? (y/n): {Style.RESET_ALL}").lower()
        if overwrite != 'y':
            print("Operation cancelled.")
            return
        os.remove(args.output_db)
    try:
        categorizer = AICategorizer()
    except (ImportError, ValueError) as e:
        print(f"{Fore.RED}Failed to initialize AI Categorizer: {e}{Style.RESET_ALL}")
        sys.exit(1)
    print(f"Initializing new database at: {args.output_db}")
    init_db(db_path=args.output_db)
    conn = get_db_connection(db_path=args.output_db)
    search_dirs = args.search_dir or get_all_question_dirs()
    yaml_files = find_yaml_files(search_dirs)
    if not yaml_files:
        print(f"{Fore.YELLOW}No YAML files found in the specified directories.{Style.RESET_ALL}")
        return
    print(f"Found {len(yaml_files)} YAML file(s) to process...")
    all_questions = []
    loader = YAMLLoader()
    for file_path in yaml_files:
        try:
            questions = loader.load_file(str(file_path))
            all_questions.extend(questions)
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not process file '{file_path}': {e}{Style.RESET_ALL}")
    unique_questions: Dict[str, Question] = {}
    for q in all_questions:
        if q.prompt and q.prompt not in unique_questions:
            unique_questions[q.prompt] = q
    print(f"Found {len(unique_questions)} unique questions. Categorizing with AI...")
    processed_count = 0
    try:
        cursor = conn.cursor()
        with tqdm(total=len(unique_questions), desc="Categorizing Questions") as pbar:
            for question in unique_questions.values():
                q_dict = asdict(question)
                q_id = q_dict.get('id')
                prompt = q_dict.get('prompt')
                ai_categories = categorizer.categorize_question(q_dict)
                category_id = None
                subject_id = q_dict.get('category')
                if ai_categories:
                    category_id = ai_categories.get('exercise_category', category_id)
                    subject_id = ai_categories.get('subject_matter', subject_id)
                add_question(
                    conn=conn, id=q_id, prompt=prompt, source_file=q_dict.get('source_file'),
                    response=q_dict.get('response'), category=subject_id, source=q_dict.get('source'),
                    validation_steps=q_dict.get('validation_steps'), validator=q_dict.get('validator'),
                    review=q_dict.get('review', False)
                )
                if category_id:
                    cursor.execute("UPDATE questions SET category_id = ? WHERE id = ?", (category_id, q_id))
                processed_count += 1
                pbar.update(1)
        conn.commit()
    finally:
        if conn: conn.close()
    print(f"\n{Fore.GREEN}Successfully processed and added {processed_count} questions to '{args.output_db}'.{Style.RESET_ALL}")

INDEX_FILE_PATH = project_root / "backups" / "index.yaml"

def _get_file_metadata(path: Path) -> dict:
    """Gathers metadata for a given file."""
    stat = path.stat()
    return {
        "path": str(path.relative_to(project_root)), "size_bytes": stat.st_size,
        "last_modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }

def do_index(args):
    """Finds all YAML files and creates an index file with their metadata."""
    print(f"{Fore.CYAN}--- Indexing all YAML files in repository ---{Style.RESET_ALL}")
    try:
        all_files = find_yaml_files(QUESTION_DIRS)
        if not all_files:
            all_files = get_all_yaml_files_in_repo()
        print("Directories scanned for YAML files:")
        for d in QUESTION_DIRS: print(f"  {d}")
        print("YAML files to index:")
        for p in all_files: print(f"  {p}")
        if not all_files:
            print(f"{Fore.YELLOW}No YAML files found to index in QUESTION_DIRS or repository.{Style.RESET_ALL}")
            return
        print(f"Found {len(all_files)} YAML files to index.")
        index_data = {
            "last_updated": datetime.datetime.now().isoformat(),
            "files": [_get_file_metadata(p) for p in all_files],
        }
        INDEX_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(INDEX_FILE_PATH, "w") as f:
            yaml.safe_dump(index_data, f, indent=2)
        print(f"{Fore.GREEN}Successfully created YAML index at: {INDEX_FILE_PATH}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")

def _categorize_with_gemini(prompt: str) -> dict:
    """Uses llm-gemini to categorize a question."""
    try:
        result = subprocess.run(
            ["llm", "-m", "gemini-2.0-flash", "-o", "json_object", f"Categorize: {prompt}"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return json.loads(result.stdout)
    except Exception as e:
        logging.error(f"Error categorizing with llm-gemini: {e}")
        return {}

def do_init(args):
    """Initializes the application database from consolidated YAML backups."""
    logging.info("Starting database initialization from consolidated YAML backups...")
    try:
        root = get_project_root()
        conn = get_db_connection()
    except Exception as e:
        logging.error(f"Error during initial setup: {e}")
        return
    backup_dir = root / 'yaml' / 'consolidated_backup'
    if not backup_dir.is_dir():
        logging.warning(f"Consolidated backup directory not found: {backup_dir}")
        return
    yaml_files = sorted(list(backup_dir.glob('**/*.yaml')) + list(backup_dir.glob('**/*.yml')))
    if not yaml_files:
        logging.info(f"No YAML files found in {backup_dir}.")
        return
    logging.info(f"Found {len(yaml_files)} YAML files to process in {backup_dir}.")
    cursor = conn.cursor()
    try:
        logging.info("Clearing existing questions from the database.")
        retry_count = 0
        while retry_count < 5:
            try:
                cursor.execute("DELETE FROM questions")
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    logging.warning("Database is locked. Retrying...")
                    retry_count += 1
                    time.sleep(1)
                else: raise
        else:
            logging.error("Failed to clear 'questions' table after multiple retries. Aborting.")
            conn.close()
            return
    except sqlite3.Error as e:
        logging.error(f"Failed to clear 'questions' table: {e}. Aborting.")
        conn.close()
        return
    question_count = 0
    for yaml_file in yaml_files:
        relative_path = yaml_file.relative_to(root)
        logging.info(f"Processing file: {relative_path}")
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if not isinstance(data, list):
                logging.warning(f"YAML file {relative_path} does not contain a list of questions. Skipping.")
                continue
            for question_data in data:
                if not isinstance(question_data, dict):
                    logging.warning(f"Skipping non-dictionary item in {relative_path}")
                    continue
                prompt = question_data.get('prompt')
                if not prompt:
                    logging.warning(f"Skipping question with no prompt in {relative_path}")
                    continue
                logging.info(f"Categorizing question with llm-gemini: '{prompt[:70]}...'")
                categories = _categorize_with_gemini(prompt)
                exercise_category = categories.get('exercise_category', 'custom')
                subject_matter = categories.get('subject_matter', 'Unknown')
                q_id = question_data.get('id', str(uuid.uuid4()))
                sql = "INSERT INTO questions (id, prompt, response, source_file, category_id, subject_id) VALUES (?, ?, ?, ?, ?, ?)"
                params = (q_id, prompt, question_data.get('response'), str(relative_path), exercise_category, subject_matter)
                retry_count = 0
                while retry_count < 5:
                    try:
                        cursor.execute(sql, params)
                        break
                    except sqlite3.OperationalError as e:
                        if "database is locked" in str(e):
                            logging.warning("Database is locked. Retrying...")
                            retry_count += 1
                            time.sleep(1)
                        else: raise
                else:
                    logging.error(f"Failed to insert question {q_id} after multiple retries. Skipping.")
                    continue
                question_count += 1
        except yaml.YAMLError as e:
            logging.error(f"Error parsing YAML file {relative_path}: {e}")
        except sqlite3.Error as e:
            logging.error(f"Database error while processing a question from {relative_path}: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while processing {relative_path}: {e}")
    conn.commit()
    conn.close()
    logging.info(f"Database initialization complete. Loaded {question_count} questions.")

def do_list_backups(args):
    """Finds and prints all YAML backup files."""
    backup_dirs = YAML_BACKUP_DIRS
    if not backup_dirs:
        if not args.path_only:
            print("No YAML backup directories are configured.", file=sys.stderr)
        sys.exit(1)
    try:
        backup_files = find_and_sort_files_by_mtime(backup_dirs, [".yaml", ".yml"])
    except Exception as e:
        if not args.path_only:
            print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)
    if not backup_files:
        if not args.path_only:
            print("No YAML backup files found.")
        sys.exit(0)
    if args.path_only:
        for f in backup_files:
            print(f)
    else:
        print(f"Searching for YAML backup files in: {', '.join(backup_dirs)}...")
        print(f"\nFound {len(backup_files)} backup file(s), sorted by most recent:\n")
        for f in backup_files:
            mod_time = f.stat().st_mtime
            mod_time_str = datetime.datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
            print(f"- {mod_time_str} | {f.name} ({f.parent})")

EXERCISE_TYPE_TO_CATEGORY = {
    "socratic": "Basic", "command": "Command", "yaml_author": "Manifest",
    "yaml_edit": "Manifest", "live_k8s_edit": "Manifest",
}

def _analyze_file(path):
    """Analyzes a single YAML file and returns statistics about its questions."""
    loader = YAMLLoader()
    try:
        questions = loader.load_file(str(path))
    except Exception as e:
        return {'file': str(path), 'error': f'parse error: {e}'}
    total = len(questions)
    breakdown = {"Basic": Counter(), "Command": Counter(), "Manifest": Counter(), "Unknown": Counter()}
    for q in questions:
        ex_type = getattr(q, "type", "Unknown Type") or "Unknown"
        subject = (getattr(q, 'metadata', None) or {}).get('category', "Uncategorized") or "Uncategorized"
        if subject == "Uncategorized": subject = "Vim"
        major_category = EXERCISE_TYPE_TO_CATEGORY.get(ex_type, "Unknown")
        if subject in ["Resource Reference", "Kubectl Operations"]: major_category = "Basic"
        breakdown[major_category][subject] += 1
    breakdown = {k: v for k, v in breakdown.items() if v}
    breakdown_dict = {k: dict(v) for k, v in breakdown.items()}
    category_counts = {cat: sum(counts.values()) for cat, counts in breakdown.items()}
    size = path.stat().st_size
    mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(path.stat().st_mtime))
    return {
        'file': str(path), 'size': size, 'mtime': mtime, 'total': total,
        'category_counts': category_counts, 'breakdown': breakdown_dict,
    }

def do_backup_stats(args):
    """Show stats for the latest YAML backup file found in the given paths."""
    scan_paths = args.paths or YAML_BACKUP_DIRS
    try:
        files = find_yaml_files_from_paths(scan_paths)
    except Exception as e:
        print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)
    if args.pattern:
        regex = re.compile(args.pattern)
        files = [f for f in files if regex.search(str(f))]
    if not files:
        print(f"No YAML files found in {', '.join(scan_paths)}")
        sys.exit(0)
    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    if not args.json:
        print(f"Found {len(files)} backup files. Analyzing latest: {latest_file}", file=sys.stderr)
    stats = [_analyze_file(latest_file)]
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        for s in stats:
            if 'error' in s:
                print(f"{s['file']}: {s['error']}")
            else:
                print(f"File: {s['file']}")
                print(f" Size: {s['size']} bytes  Modified: {s['mtime']}")
                print(f" Total questions: {s['total']}")
                print(" Questions by Exercise Category:")
                for category, count in sorted(s['category_counts'].items(), key=lambda x: -x[1]):
                    print(f"  {category}: {count}")
                    subject_counts = s.get('breakdown', {}).get(category, {})
                    for subject, sub_count in sorted(subject_counts.items(), key=lambda x: -x[1]):
                        print(f"    - {subject}: {sub_count}")
                print()

def do_statistics(args):
    """Calculates and prints statistics about questions in YAML files."""
    loader = YAMLLoader()
    yaml_files: List[Path] = []
    if args.path:
        target_path = Path(args.path)
        if not target_path.exists():
            print(f"Error: Path does not exist: {target_path}", file=sys.stderr)
            sys.exit(1)
        if target_path.is_dir():
            print(f"Scanning for YAML files in: {target_path}")
            yaml_files = find_yaml_files([str(target_path)])
        elif target_path.is_file():
            if target_path.suffix.lower() not in ['.yaml', '.yml']:
                print(f"Error: Specified file is not a YAML file: {target_path}", file=sys.stderr)
                sys.exit(1)
            yaml_files = [target_path]
    else:
        search_dirs = QUESTION_DIRS
        print(f"No path specified. Searching in default question directories: {', '.join(search_dirs)}")
        yaml_files = find_yaml_files(search_dirs)
    if not yaml_files:
        print("No YAML files found to analyze.")
        return
    all_questions: List[Question] = []
    print(f"Found {len(yaml_files)} YAML file(s). Loading questions...")
    for file_path in yaml_files:
        try:
            questions_from_file = loader.load_file(str(file_path))
            if questions_from_file:
                all_questions.extend(questions_from_file)
        except Exception as e:
            print(f"Warning: Could not load or parse {file_path}: {e}", file=sys.stderr)
            continue
    if not all_questions:
        print("No questions could be loaded from the specified YAML files.")
        return
    type_counts = Counter(q.type for q in all_questions if hasattr(q, 'type') and q.type)
    category_counts = Counter(q.category for q in all_questions if hasattr(q, 'category') and q.category)
    print(f"\n--- YAML Question Statistics ---")
    print(f"Total Questions Found: {len(all_questions)}")
    print("\n--- Questions by Exercise Type ---")
    if type_counts:
        for q_type, count in type_counts.most_common(): print(f"  - {q_type:<20} {count}")
    else:
        print("  No questions with 'type' field found.")
    print("\n--- Questions by Subject Matter (Category) ---")
    if category_counts:
        for category, count in category_counts.most_common(): print(f"  - {category:<30} {count}")
    else:
        print("  No questions with 'category' field found.")

def do_group_backups(args):
    """
    Group all legacy YAML backup quizzes into a single "legacy_yaml" module.
    """
    conn = get_db_connection() # Uses live DB by default
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM questions WHERE source = 'backup'")
    total = cursor.fetchone()[0]
    if total == 0:
        print("No backup YAML questions found to group.")
        conn.close()
        return
    cursor.execute(
        "UPDATE questions SET source_file = 'legacy_yaml' WHERE source = 'backup'"
    )
    conn.commit()
    conn.close()
    print(f"Grouped {total} backup YAML questions into module 'legacy_yaml'.")
    try:
        shutil.copy2(DATABASE_FILE, BACKUP_DATABASE_FILE)
        print(f"Database backup updated at: {BACKUP_DATABASE_FILE}")
    except Exception as e:
        print(f"Failed to backup database: {e}")

def do_import_bak(args):
    """
    Import all YAML-backed quiz questions into the live Kubelingo database.
    """
    init_db()
    yaml_bak_dir = project_root / 'question-data' / 'yaml-bak'
    if not yaml_bak_dir.is_dir():
        print(f"Backup YAML directory not found: {yaml_bak_dir}")
        return

    loader = YAMLLoader()
    total = 0
    conn = get_db_connection()
    try:
        for pattern in ('*.yaml', '*.yml'):
            for path in sorted(yaml_bak_dir.glob(pattern)):
                print(f"Importing questions from: {path.name}")
                try:
                    questions = loader.load_file(str(path))
                except Exception as e:
                    print(f"  Failed to load {path.name}: {e}")
                    continue
                for q in questions:
                    steps = [asdict(s) for s in getattr(q, 'validation_steps', [])]
                    validator = None
                    metadata = getattr(q, 'metadata', {}) or {}
                    expected = metadata.get('correct_yaml')
                    if expected:
                        validator = {'type': 'yaml', 'expected': expected}
                    try:
                        add_question(
                            conn=conn,
                            id=q.id,
                            prompt=q.prompt,
                            source_file=path.name,
                            response=getattr(q, 'response', None),
                            category=(q.categories[0] if getattr(q, 'categories', None) else getattr(q, 'category', None)),
                            source='backup',
                            validation_steps=steps,
                            validator=validator,
                        )
                        total += 1
                    except Exception as e:
                        print(f"  Could not add {q.id}: {e}")
    finally:
        if conn:
            conn.close()

    print(f"Imported {total} questions from YAML backup into the DB.")

    try:
        shutil.copy2(DATABASE_FILE, BACKUP_DATABASE_FILE)
        print(f"Database backup created at: {BACKUP_DATABASE_FILE}")
    except Exception as e:
        print(f"Failed to backup database: {e}")

def do_migrate_all(args):
    """
    Migrate all YAML-based quiz questions into the Kubelingo SQLite database.
    """
    init_db()
    loader = YAMLLoader()
    dirs = [Path(d) for d in QUESTION_DIRS]
    total_added = 0
    conn = get_db_connection()
    try:
        for yaml_dir in dirs:
            if not yaml_dir.is_dir():
                continue
            print(f"Processing YAML directory: {yaml_dir}")
            patterns = ['*.yaml', '*.yml', '*.yaml.bak']
            for pat in patterns:
                for path in sorted(yaml_dir.glob(pat)):
                    try:
                        questions = loader.load_file(str(path))
                    except Exception as e:
                        print(f"Failed to load {path}: {e}")
                        continue
                    if not questions:
                        continue
                    source_file = path.name
                    for q in questions:
                        vs = []
                        for step in getattr(q, 'validation_steps', []):
                            vs.append(asdict(step))
                        validator = None
                        metadata = getattr(q, 'metadata', {}) or {}
                        expected = metadata.get('correct_yaml')
                        if expected:
                            validator = {'type': 'yaml', 'expected': expected}
                        try:
                            add_question(
                                conn=conn,
                                id=q.id,
                                prompt=q.prompt,
                                source_file=source_file,
                                response=None,
                                category=(q.categories[0] if getattr(q, 'categories', None) else None),
                                source=getattr(q, 'source', None),
                                validation_steps=vs,
                                validator=validator,
                                # Preserve full question schema
                                question_type=getattr(q, 'type', None),
                                answers=getattr(q, 'answers', None),
                                correct_yaml=getattr(q, 'correct_yaml', None),
                                pre_shell_cmds=getattr(q, 'pre_shell_cmds', None),
                                initial_files=getattr(q, 'initial_files', None),
                                explanation=getattr(q, 'explanation', None),
                                difficulty=getattr(q, 'difficulty', None),
                                schema_category=getattr(getattr(q, 'schema_category', None), 'value', None),
                            )
                            total_added += 1
                        except Exception as e:
                            print(f"Failed to add {q.id} from {source_file}: {e}")
    finally:
        if conn:
            conn.close()
    print(f"Migration complete: {total_added} YAML questions added to database.")

def do_migrate_bak(args):
    """
    Clears the database, loads all questions from YAML files in the backup
    directory, saves them to the database, and then creates a new pristine
    backup of the populated database.
    """
    print("Starting migration of questions from 'yaml-bak' directory to database...")

    # 1. Clear the existing database
    print("Clearing the database to ensure a fresh import...")
    init_db(clear=True)
    conn = get_db_connection()

    # 2. Load questions from yaml-bak
    print(f"Searching for YAML files in: {YAML_QUIZ_BACKUP_DIR}")
    if not os.path.isdir(YAML_QUIZ_BACKUP_DIR):
        print(f"Error: Backup directory not found at '{YAML_QUIZ_BACKUP_DIR}'")
        sys.exit(1)

    yaml_loader = YAMLLoader()
    total_questions_added = 0

    try:
        for filename in sorted(os.listdir(YAML_QUIZ_BACKUP_DIR)):
            if not filename.endswith(('.yaml', '.yml')):
                continue

            file_path = os.path.join(YAML_QUIZ_BACKUP_DIR, filename)
            print(f"  -> Processing file: {filename}")
            try:
                questions = yaml_loader.load_file(file_path)
                if not questions:
                    print(f"     No questions found in {filename}.")
                    continue

                intended_source_file = file_path.replace(os.sep + 'yaml-bak' + os.sep, os.sep + 'yaml' + os.sep)

                for q in questions:
                    add_question(
                        conn=conn,
                        id=q.id,
                        prompt=q.prompt,
                        source_file=intended_source_file,
                        response=getattr(q, 'response', None),
                        category=getattr(q, 'category', None),
                        source=getattr(q, 'source', "https://kubernetes.io/docs/home/"),
                        validation_steps=[asdict(vs) for vs in getattr(q, 'validation_steps', [])],
                        validator=getattr(q, 'validator', None),
                        explanation=getattr(q, 'explanation', None)
                    )
                total_questions_added += len(questions)
                print(f"     Added {len(questions)} questions from {filename}.")

            except Exception as e:
                print(f"     Error processing {filename}: {e}")
    finally:
        if conn:
            conn.close()

    print(f"\nTotal questions added to the database: {total_questions_added}")

    if total_questions_added == 0:
        print("\nNo questions were added. Aborting backup.")
        return

    print(f"\nBacking up new database to '{BACKUP_DATABASE_FILE}'...")
    try:
        backup_dir = os.path.dirname(BACKUP_DATABASE_FILE)
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        shutil.copyfile(DATABASE_FILE, BACKUP_DATABASE_FILE)
        print("Backup successful.")
        print(f"Pristine database at '{BACKUP_DATABASE_FILE}' has been updated.")
    except Exception as e:
        print(f"Error creating backup: {e}")

def _create_db_schema_for_verify(conn: sqlite3.Connection):
    """Creates the questions table in the SQLite database for verification."""
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id TEXT PRIMARY KEY,
        prompt TEXT,
        source_file TEXT,
        response TEXT,
        category TEXT,
        source TEXT,
        validation_steps TEXT,
        validator TEXT,
        review BOOLEAN,
        question_type TEXT,
        type TEXT,
        subject_matter TEXT,
        metadata TEXT,
        categories TEXT,
        difficulty TEXT,
        pre_shell_cmds TEXT,
        initial_files TEXT,
        explanation TEXT
    )
    """)
    conn.commit()

def _import_yaml_to_db_for_verify(yaml_path: str, conn: sqlite3.Connection):
    """
    Reads questions from a YAML file and imports them into the DB.
    """
    try:
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: YAML file not found at {yaml_path}", file=sys.stderr)
        return 0
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}", file=sys.stderr)
        return 0

    questions = data.get('questions', [])
    if not questions:
        print(f"Info: No questions found in {os.path.basename(yaml_path)}.")
        return 0

    source_file = os.path.basename(yaml_path)
    cursor = conn.cursor()
    
    inserted_count = 0
    questions_to_process = [q for q in questions if q.get('id')]
    num_skipped_no_id = len(questions) - len(questions_to_process)

    if num_skipped_no_id > 0:
        print(f"Info: In {source_file}, skipping {num_skipped_no_id} questions that have no ID.")

    for q in questions_to_process:
        params = {
            'id': q.get('id'),
            'prompt': q.get('prompt', ''),
            'source_file': source_file,
            'response': q.get('response'),
            'category': q.get('category'), # Legacy field
            'source': q.get('source'),
            'validation_steps': json.dumps(q.get('validation_steps', [])),
            'validator': json.dumps(q.get('validator', {})),
            'review': q.get('review', False),
            'question_type': q.get('type') or q.get('question_type', 'command'),
            'type': q.get('type'), # Legacy field
            'subject_matter': q.get('subject_matter'),
            'metadata': json.dumps(q.get('metadata', {})),
            'categories': json.dumps(q.get('categories', [])),
            'difficulty': q.get('difficulty'),
            'pre_shell_cmds': json.dumps(q.get('pre_shell_cmds', [])),
            'initial_files': json.dumps(q.get('initial_files', {})),
            'explanation': q.get('explanation')
        }
        
        columns = ', '.join(params.keys())
        placeholders = ', '.join(':' + key for key in params.keys())
        sql = f"INSERT OR IGNORE INTO questions ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, params)
        if cursor.rowcount > 0:
            inserted_count += 1

    conn.commit()
    skipped_duplicates = len(questions_to_process) - inserted_count
    print(f"Imported from {source_file}: Inserted {inserted_count} new questions, skipped {skipped_duplicates} duplicates.")
    return inserted_count

def do_verify(args):
    """Verify YAML question import to SQLite and loading via DBLoader."""
    yaml_files = find_yaml_files_from_paths(args.paths)

    if not yaml_files:
        print("Error: No YAML files found in the provided paths.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(yaml_files)} YAML file(s) to process.")
    
    tmp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp_db_file.name
    tmp_db_file.close()

    try:
        print(f"Using temporary database: {db_path}")
        
        conn = sqlite3.connect(db_path)
        _create_db_schema_for_verify(conn)

        total_imported = 0
        imported_files_map = {}  # basename -> count

        for yaml_file in yaml_files:
            num_imported = _import_yaml_to_db_for_verify(str(yaml_file), conn)
            total_imported += num_imported
            imported_files_map[os.path.basename(str(yaml_file))] = num_imported
        
        conn.close()

        if total_imported == 0:
            print("No questions found in any YAML file. Exiting.")
            return

        print(f"\nTotal questions imported: {total_imported}")
        print("\nVerifying import using DBLoader...")
        loader = DBLoader(db_path=db_path)
        
        source_files_in_db = loader.discover()
        
        imported_basenames = set(imported_files_map.keys())
        discovered_basenames = set(source_files_in_db)

        if not imported_basenames.issubset(discovered_basenames):
            missing = sorted(list(imported_basenames - discovered_basenames))
            print(f"ERROR: DBLoader did not discover the following source file(s): {', '.join(missing)}", file=sys.stderr)
            print(f"Discovered files in DB: {sorted(list(discovered_basenames))}", file=sys.stderr)
            sys.exit(1)
            
        print(f"Successfully discovered all {len(imported_files_map)} source file(s).")
        print("\nVerifying question counts...")

        total_loaded = 0
        mismatched_files = []
        for basename, num_imported in sorted(imported_files_map.items()):
            loaded_questions = loader.load_file(basename)
            num_loaded = len(loaded_questions)
            total_loaded += num_loaded
            
            if num_loaded == num_imported:
                print(f"  ✅ '{basename}': Imported {num_imported}, DBLoader loaded {num_loaded}.")
            else:
                print(f"  ❌ '{basename}': Imported {num_imported}, DBLoader loaded {num_loaded}.")
                mismatched_files.append(basename)
        
        print("-" * 20)
        print(f"Total Imported: {total_imported}, Total Loaded: {total_loaded}")

        if not mismatched_files and total_imported == total_loaded:
            print("\nSUCCESS: The number of loaded questions matches the number of imported questions for all files.")
        else:
            print(f"\nERROR: Mismatch in question count detected for one or more files.", file=sys.stderr)
            sys.exit(1)

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"Temporary database {db_path} cleaned up.")

def do_organize_generated(args):
    """Consolidate, import, and clean up AI-generated YAML questions."""
    source_dir = Path(args.source_dir)
    output_file = Path(args.output_file)

    if not source_dir.is_dir():
        print(f"Error: Source directory not found at '{source_dir}'", file=sys.stderr)
        sys.exit(1)

    print(f"--- Organizing generated questions from: {source_dir} ---")

    # 1. Deduplicate and consolidate
    print(f"Step 1: Consolidating unique questions into {output_file}...")

    loader = YAMLLoader()
    yaml_files = list(source_dir.rglob("*.yaml")) + list(source_dir.rglob("*.yml"))

    if not yaml_files:
        print("No YAML files found to organize.")
        return

    unique_questions: Dict[str, Question] = {}
    total_questions = 0
    duplicates_found = 0
    for file_path in yaml_files:
        try:
            questions = loader.load_file(str(file_path))
            total_questions += len(questions)
            for q in questions:
                key = _question_to_key(q)
                if key not in unique_questions:
                    unique_questions[key] = q
                else:
                    duplicates_found += 1
        except Exception as e:
            print(f"Warning: Could not process file {file_path}: {e}", file=sys.stderr)
            continue

    print(f"Scan complete. Found {total_questions} total questions, {duplicates_found} duplicates. Consolidating {len(unique_questions)} unique questions.")

    if not unique_questions:
        print("No valid questions found to process.")
        return

    if args.dry_run:
        print(f"[DRY RUN] Would write {len(unique_questions)} unique questions to '{output_file}'.")
    else:
        questions_for_yaml = [asdict(q) for q in unique_questions.values()]
        # clean up None values for cleaner YAML
        cleaned_questions_for_yaml = []
        for q_dict in questions_for_yaml:
            cleaned_questions_for_yaml.append({k: v for k, v in q_dict.items() if v is not None})
        
        output_data = {"questions": cleaned_questions_for_yaml}
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(output_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            print(f"Successfully wrote {len(unique_questions)} unique questions to '{output_file}'.")
        except IOError as e:
            print(f"Error writing to output file '{output_file}': {e}", file=sys.stderr)
            sys.exit(1)

    # 2. Update database
    print("\nStep 2: Updating database...")
    db_path = args.db_path or get_live_db_path()
    
    if not Path(db_path).exists() and not args.dry_run:
        print(f"Warning: Database not found at {db_path}. Skipping database operations.")
    else:
        conn = get_db_connection(db_path=db_path)
        try:
            # Delete old questions
            source_dir_pattern = str(source_dir) + '/%'
            print(f"Deleting questions from DB where source_file LIKE '{source_dir_pattern}'...")
            
            cursor = conn.cursor()
            if args.dry_run:
                if Path(db_path).exists():
                    cursor.execute("SELECT COUNT(*) FROM questions WHERE source_file LIKE ?", (source_dir_pattern,))
                    count = cursor.fetchone()[0]
                    print(f"[DRY RUN] Would delete {count} questions from the database.")
                else:
                    print(f"[DRY RUN] Database does not exist, would skip deletion.")

            else:
                cursor.execute("DELETE FROM questions WHERE source_file LIKE ?", (source_dir_pattern,))
                print(f"Deleted {cursor.rowcount} questions.")
                conn.commit()

            # Import new consolidated questions
            print(f"Importing questions from '{output_file}'...")
            if args.dry_run:
                print(f"[DRY RUN] Would import {len(unique_questions)} questions into the database.")
            else:
                # Call sqlite_manager to import the consolidated file
                sqlite_manager_path = project_root / 'scripts' / 'sqlite_manager.py'
                cmd = [
                    sys.executable,
                    str(sqlite_manager_path),
                    'create-from-yaml',
                    '--db-path', db_path,
                    '--yaml-files', str(output_file)
                ]
                # create-from-yaml will append to the DB if --clear is not used.
                try:
                    subprocess.run(cmd, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Error calling sqlite_manager.py: {e}", file=sys.stderr)
                    sys.exit(1)

        finally:
            if conn: conn.close()

    # 3. Clean up original files
    if not args.no_cleanup:
        print(f"\nStep 3: Cleaning up original files in {source_dir}...")
        if args.dry_run:
            print(f"[DRY RUN] Would delete {len(yaml_files)} original YAML files.")
        else:
            deleted_count = 0
            for file_path in yaml_files:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}", file=sys.stderr)
            print(f"Deleted {deleted_count} original YAML files.")

    print("\nOrganization complete.")

def main():
    """Main CLI entrypoint."""
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(
            description="A unified tool for managing Kubelingo's questions and YAML files.",
            formatter_class=argparse.RawTextHelpFormatter,
        )
        subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

        # --- Sub-parsers from original question_manager.py ---
        p_build_index = subparsers.add_parser('build-index', help='Builds or updates the question index from YAML files.', description="Scans YAML files in a directory, hashes them, and updates the SQLite question database.")
        p_build_index.add_argument('directory', default='yaml/questions', nargs='?', help='Path to the directory containing YAML question files. Defaults to "yaml/questions".')
        p_build_index.add_argument('--quiet', action='store_true', help="Suppress progress output.")
        p_build_index.set_defaults(func=handle_build_index)

        p_list_triage = subparsers.add_parser('list-triage', help='Lists all questions marked for triage.')
        p_list_triage.set_defaults(func=handle_list_triaged)

        p_triage = subparsers.add_parser('triage', help='Marks a question for triage.')
        p_triage.add_argument('question_id', help='The ID of the question to triage.')
        p_triage.set_defaults(func=handle_set_triage_status, un_triage=False)

        p_untriage = subparsers.add_parser('untriage', help='Removes a question from triage.')
        p_untriage.add_argument('question_id', help='The ID of the question to un-triage.')
        p_untriage.set_defaults(func=handle_set_triage_status, un_triage=True)

        p_remove = subparsers.add_parser('remove', help='Removes a question from the database by ID.')
        p_remove.add_argument('question_id', help='The ID of the question to remove.')
        p_remove.set_defaults(func=handle_remove_question)

        # --- Sub-parsers from original yaml_manager.py ---
        p_consolidate = subparsers.add_parser('consolidate', help="Consolidate unique YAML questions from across the repository into a single file.")
        p_consolidate.add_argument('-o', '--output', type=Path, help=f'Output file path for consolidated questions.')
        p_consolidate.set_defaults(func=do_consolidate)
        
        p_create_quizzes = subparsers.add_parser('create-quizzes', help="Create quizzes from consolidated YAML backup.")
        p_create_quizzes.set_defaults(func=do_create_quizzes)
        
        p_deduplicate = subparsers.add_parser('deduplicate', help="Deduplicate YAML questions in a directory.")
        p_deduplicate.add_argument("directory", type=str, help="Directory containing YAML question files.")
        p_deduplicate.add_argument("-o", "--output-file", type=str, help="Output file for consolidated unique questions.")
        p_deduplicate.add_argument("--dry-run", action="store_true", help="Perform a dry run without writing files.")
        p_deduplicate.set_defaults(func=do_deduplicate)
        
        p_diff = subparsers.add_parser('diff', help="Diff YAML backup files to track changes.")
        p_diff.add_argument('files', nargs='*', help="Two YAML files to compare. If not provided, compares all backups.")
        p_diff.add_argument("--range", help="Number of recent versions to diff (e.g., '5' for last 5). 'all' to diff all.", default="all")
        p_diff.set_defaults(func=do_diff)
        
        p_export = subparsers.add_parser('export', help="Export questions DB to YAML.")
        p_export.add_argument("-o", "--output", help="Output YAML file path.")
        p_export.set_defaults(func=do_export)

        p_import_ai = subparsers.add_parser('import-ai', help="Import from YAML with AI categorization.")
        p_import_ai.add_argument("output_db", help="Path to the new SQLite database file to be created.")
        p_import_ai.add_argument("--search-dir", action='append', help="Directory to search for YAML files. Can be used multiple times.")
        p_import_ai.set_defaults(func=do_import_ai)

        p_index = subparsers.add_parser('index', help="Finds all YAML files and creates an index file with their metadata.")
        p_index.set_defaults(func=do_index)
        
        p_init = subparsers.add_parser('init', help="Initializes the database from consolidated YAML backups.")
        p_init.set_defaults(func=do_init)
        
        p_list_backups = subparsers.add_parser('list-backups', help='Finds and displays all YAML backup files.')
        p_list_backups.add_argument("--path-only", action="store_true", help="Only prints the paths of the files.")
        p_list_backups.set_defaults(func=do_list_backups)
        
        p_backup_stats = subparsers.add_parser('backup-stats', help="Show stats for the latest YAML backup file.")
        p_backup_stats.add_argument('paths', nargs='*', help='Path(s) to YAML file(s) or directories.')
        p_backup_stats.add_argument('-p', '--pattern', help='Regex to filter filenames')
        p_backup_stats.add_argument('--json', action='store_true', help='Output stats in JSON format')
        p_backup_stats.set_defaults(func=do_backup_stats)
        
        p_stats = subparsers.add_parser('stats', help="Get statistics about questions in YAML files.")
        p_stats.add_argument("path", nargs='?', default=None, help="Path to a YAML file or directory.")
        p_stats.set_defaults(func=do_statistics)

        p_group_backups = subparsers.add_parser('group-backups', help="Group legacy YAML backup quizzes into a single module.")
        p_group_backups.set_defaults(func=do_group_backups)

        p_import_bak = subparsers.add_parser('import-bak', help="Import questions from legacy YAML backup directory.")
        p_import_bak.set_defaults(func=do_import_bak)

        p_migrate_all = subparsers.add_parser('migrate-all', help="Migrate all YAML questions from standard directories to DB.")
        p_migrate_all.set_defaults(func=do_migrate_all)

        p_migrate_bak = subparsers.add_parser('migrate-bak', help="Clear DB and migrate from YAML backup directory.")
        p_migrate_bak.set_defaults(func=do_migrate_bak)

        p_verify = subparsers.add_parser('verify', help="Verify YAML question import and loading.")
        p_verify.add_argument("paths", nargs='+', help="Path(s) to YAML file(s) or directories to verify.")
        p_verify.set_defaults(func=do_verify)

        p_organize = subparsers.add_parser('organize-generated', help="Consolidate, import, and clean up AI-generated YAML questions.")
        p_organize.add_argument('--source-dir', default='questions/generated_yaml', help="Directory with generated YAML files.")
        p_organize.add_argument('--output-file', default='questions/ai_generated_consolidated.yaml', help="Consolidated output YAML file.")
        p_organize.add_argument('--db-path', default=None, help="Path to the SQLite database file.")
        p_organize.add_argument('--no-cleanup', action='store_true', help="Do not delete original individual YAML files after consolidation.")
        p_organize.add_argument('--dry-run', action='store_true', help="Show what would be done without making changes.")
        p_organize.set_defaults(func=do_organize_generated)

        args = parser.parse_args()
        if hasattr(args, 'func'):
            args.func(args)
        else:
            parser.print_help()
    else:
        interactive_question_manager_menu()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    main()
