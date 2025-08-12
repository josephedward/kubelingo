#!/usr/bin/env python3
"""
Single CLI to manage YAML files for Kubelingo, including backups, DB operations, and statistics.
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
import re
import time
import tempfile
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

# --- consolidate_unique_yaml_questions ---
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


# --- create_quizzes_from_yaml ---
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


# --- create_sqlite_db_from_yaml ---
class QuestionSkipped(Exception):
    def __init__(self, message: str, category: Optional[str] = None):
        self.message = message
        self.category = category
        super().__init__(self.message)

def _normalize_and_prepare_question_for_db(q_data: dict, category_to_source_file: dict, allowed_args: set) -> dict:
    q_dict = q_data.copy()
    if "metadata" in q_dict and isinstance(q_dict["metadata"], dict):
        metadata = q_dict.pop("metadata")
        for k, v in metadata.items():
            if k not in q_dict:
                q_dict[k] = v
    if "answer" in q_dict:
        q_dict["correct_yaml"] = q_dict.pop("answer")
    if "starting_yaml" in q_dict:
        q_dict["initial_files"] = {"manifest.yaml": q_dict.pop("starting_yaml")}
    if "question" in q_dict:
        q_dict["prompt"] = q_dict.pop("question")
    q_type = q_dict.get("type")
    if q_type in ("yaml_edit", "yaml_author"):
        if "answer" in q_dict and "correct_yaml" not in q_dict:
            q_dict["correct_yaml"] = q_dict.pop("answer")
        if "starting_yaml" in q_dict and "initial_files" not in q_dict:
            q_dict["initial_files"] = {"f.yaml": q_dict.pop("starting_yaml")}
    if "type" in q_dict:
        q_dict["question_type"] = q_dict.pop("type")
    if "subject" in q_dict:
        q_dict["subject_matter"] = q_dict.pop("subject")
    q_type = q_dict.get("question_type", "command")
    if q_type in ("yaml_edit", "yaml_author", "live_k8s_edit", "manifest"):
        q_dict["schema_category"] = "manifest"
    elif q_type in ("command", "kubectl"):
        q_dict["schema_category"] = "command"
    else:
        q_dict["schema_category"] = "basic"
    if not q_dict.get("category"):
        q_type = q_dict.get("question_type")
        if q_type in ("yaml_edit", "yaml_author"):
            q_dict["category"] = "YAML Authoring"
        elif q_dict.get("subject_matter"):
            q_dict["category"] = q_dict["subject_matter"]
        elif q_dict.get("source") == "AI" and q_dict.get("subject_matter"):
            subject = q_dict.get("subject_matter")
            q_dict["category"] = subject.capitalize()
    category = q_dict.get("category")
    source_file_from_category = category_to_source_file.get(category)
    if source_file_from_category:
        q_dict["source_file"] = source_file_from_category
    elif not q_dict.get("source_file"):
        if category:
            raise QuestionSkipped(f"Unmatched category: {category}", category=category)
        else:
            raise QuestionSkipped("Missing category and could not infer one.")
    q_dict.pop("solution_file", None)
    q_dict.pop("subject", None)
    q_dict.pop("type", None)
    return {k: v for k, v in q_dict.items() if k in allowed_args}

def _populate_db_from_yaml(yaml_files: list[Path], db_path: Optional[str] = None):
    if not yaml_files:
        print("No YAML files found to process.")
        return
    conn = get_db_connection(db_path=db_path)
    allowed_args = {
        "id", "prompt", "source_file", "response", "category", "source",
        "validation_steps", "validator", "review", "question_type",
        "schema_category", "answers", "correct_yaml", "difficulty",
        "explanation", "initial_files", "pre_shell_cmds", "subject_matter", "metadata",
    }
    category_to_source_file = ENABLED_QUIZZES
    unmatched_categories = set()
    skipped_no_category = 0
    question_count = 0
    try:
        for file_path in yaml_files:
            print(f"  - Processing '{file_path.name}'...")
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    questions_data = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    print(f"Error parsing YAML file {file_path}: {e}", file=sys.stderr)
                    continue
                if not questions_data: continue
                questions_list = questions_data
                if isinstance(questions_data, dict):
                    questions_list = questions_data.get("questions") or questions_data.get("entries")
                if not isinstance(questions_list, list): continue
                for q_data in questions_list:
                    try:
                        q_dict_for_db = _normalize_and_prepare_question_for_db(
                            q_data, category_to_source_file, allowed_args
                        )
                        add_question(conn=conn, **q_dict_for_db)
                        question_count += 1
                    except QuestionSkipped as e:
                        if e.category:
                            unmatched_categories.add(e.category)
                        else:
                            skipped_no_category += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error adding questions to database: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()
    if unmatched_categories:
        print("\nWarning: The following categories from the YAML file did not match any quiz. Questions in these categories were skipped:")
        for cat in sorted(list(unmatched_categories)):
            print(f"  - {cat}")
    if skipped_no_category > 0:
        print(f"\nWarning: Skipped {skipped_no_category} questions because they were missing a 'category' field.")
    print(f"\nSuccessfully populated database with {question_count} questions.")

def do_create_db(args):
    """Populate the SQLite database from YAML backup files."""
    if args.yaml_files:
        yaml_files = path_utils.find_yaml_files_from_paths(args.yaml_files)
    else:
        print("No input paths provided. Locating most recent YAML backup...")
        all_backups = path_utils.find_and_sort_files_by_mtime(
            YAML_BACKUP_DIRS, extensions=[".yaml", ".yml"]
        )
        if not all_backups:
            print(f"{Fore.RED}Error: No YAML backup files found in configured backup directories.{Style.RESET_ALL}")
            print(f"Searched in: {YAML_BACKUP_DIRS}")
            sys.exit(1)
        latest_backup = all_backups[0]
        print(f"Using most recent backup: {Fore.GREEN}{latest_backup}{Style.RESET_ALL}")
        yaml_files = [latest_backup]
    if not yaml_files:
        print("No YAML files found.")
        sys.exit(0)
    unique_files = sorted(list(set(yaml_files)))
    print(f"Found {len(unique_files)} YAML file(s) to process:")
    if len(unique_files) > 20:
        print("Showing first 10 files:")
        for f in unique_files[:10]: print(f"  - {f.name}")
        print(f"  ...and {len(unique_files) - 10} more.")
    else:
        for f in unique_files: print(f"  - {f.name}")
    db_path = args.db_path or get_live_db_path()
    init_db(clear=args.clear, db_path=db_path)
    print(f"\nPopulating database at: {db_path}")
    _populate_db_from_yaml(unique_files, db_path=db_path)


# --- deduplicate_yaml ---
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


# --- diff_yaml_backups ---
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


# --- export_db_to_yaml ---
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


# --- import_from_yaml_with_ai ---
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


# --- index_yaml_files ---
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


# --- initialize_from_yaml ---
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


# --- restore_yaml_to_db ---
def _restore_yaml_to_db_func(yaml_files: list[Path], clear_db: bool, db_path: Optional[str] = None):
    """Restores questions from a list of YAML files to the SQLite database."""
    console = Console()
    if clear_db:
        console.print("[bold yellow]Clearing existing database...[/bold yellow]")
        init_db(clear=True, db_path=db_path)
    else:
        init_db(clear=False, db_path=db_path)
    total_questions, errors = 0, 0
    conn = get_db_connection(db_path=db_path)
    try:
        for path in track(yaml_files, description="Processing YAML files..."):
            console.print(f"  - Processing '{path.name}'...")
            try:
                with open(path, "r") as f:
                    data = yaml.safe_load(f)
                if data is None: continue
                questions_list = []
                if isinstance(data, list): questions_list = data
                elif isinstance(data, dict):
                    if "questions" in data: questions_list = data.get("questions", [])
                    elif "id" in data: questions_list = [data]
                if not questions_list:
                    console.print(f"    [yellow]Skipping file with no questions: {path.name}[/yellow]")
                    continue
                for q_data in questions_list:
                    if not isinstance(q_data, dict): continue
                    try:
                        if "metadata" in q_data and isinstance(q_data.get("metadata"), dict):
                            for key, value in q_data["metadata"].items():
                                if key not in q_data: q_data[key] = value
                        if "question" in q_data and "prompt" not in q_data: q_data["prompt"] = q_data.pop("question")
                        if "answer" in q_data and "response" not in q_data: q_data["response"] = q_data.pop("answer")
                        if "citation" in q_data and "source" not in q_data: q_data["source"] = q_data.pop("citation")
                        if not all(k in q_data for k in ["id", "prompt"]):
                            console.print(f"[red]Error in {path.name}: Skipping question missing 'id' or 'prompt'. ID: {q_data.get('id', 'N/A')}[/red]")
                            errors += 1
                            continue
                        q_data["source_file"] = str(path)
                        if "type" in q_data: q_data["question_type"] = q_data.pop("type")
                        if "subject" in q_data: q_data["subject_matter"] = q_data.pop("subject")
                        valid_keys = {
                            "id", "prompt", "response", "category", "source", "validation_steps",
                            "validator", "source_file", "review", "explanation", "difficulty",
                            "pre_shell_cmds", "initial_files", "question_type", "answers",
                            "correct_yaml", "schema_category", "metadata", "subject_matter",
                        }
                        kwargs_for_add = {key: q_data[key] for key in valid_keys if key in q_data}
                        add_question(conn=conn, **kwargs_for_add)
                        total_questions += 1
                    except Exception as e:
                        console.print(f"[red]Error adding question from {path.name} ({q_data.get('id', 'N/A')}): {e}[/red]")
                        errors += 1
            except yaml.YAMLError as e:
                console.print(f"[red]Error parsing YAML file {path.name}: {e}[/red]")
                errors += 1
            except Exception as e:
                console.print(f"[red]An unexpected error occurred with file {path.name}: {e}[/red]")
                errors += 1
    finally:
        conn.close()
    console.print(f"\n[bold green]Restore complete.[/bold green]")
    console.print(f"  - Total questions added: {total_questions}")
    if errors > 0:
        console.print(f"  - Errors encountered: {errors}")

def do_restore(args):
    """Restore questions from YAML files into the SQLite database."""
    console = Console()
    if args.paths:
        yaml_files = find_yaml_files_from_paths(args.paths)
    else:
        console.print("No input paths provided. Scanning default question directories...")
        default_dirs = get_all_question_dirs()
        yaml_files = find_yaml_files_from_paths(default_dirs)
    if not yaml_files:
        console.print("[bold red]No YAML files found to process.[/bold red]")
        sys.exit(1)
    console.print(f"Found {len(yaml_files)} YAML file(s) to process.")
    _restore_yaml_to_db_func(
        yaml_files=sorted(list(yaml_files)), clear_db=args.clear, db_path=args.db_path
    )


# --- show_previous_yaml_backups & show_yaml_backups ---
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


# --- write_db_from_yaml & restore_db_from_yaml ---
def do_write(args):
    """Write DB from YAML backup, with an option to backup existing DB."""
    if not os.path.exists(args.yaml_file):
        print('File not found:', args.yaml_file, file=sys.stderr)
        sys.exit(1)
    if args.backup:
        backup_path = DATABASE_FILE + '.pre_restore.bak'
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy(DATABASE_FILE, backup_path)
        print(f'Backed up current database to {backup_path}')
    if args.overwrite:
        conn = get_db_connection()
        conn.execute('DELETE FROM questions')
        conn.commit()
        conn.close()
    with open(args.yaml_file) as f:
        data = yaml.safe_load(f) or []
    conn = get_db_connection()
    for q in data:
        try:
            add_question(conn=conn, **q)
        except Exception as e:
            print('Error importing question', q.get('id'), e, file=sys.stderr)
    conn.close()
    print(f'Loaded {len(data)} questions into the database.')


# --- yaml_backup_stats ---
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


# --- yaml_statistics ---
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


# --- group_backup_yaml_questions ---
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


# --- import_yaml_bak_questions ---
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


# --- migrate_all_yaml_questions ---
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


# --- migrate_from_yaml_bak ---
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

    # 3. Back up the newly populated database to the pristine location
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


# --- verify_yaml_import ---
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
                _restore_yaml_to_db_func([output_file], clear_db=False, db_path=db_path)

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
    parser = argparse.ArgumentParser(
        description="A tool for managing Kubelingo's YAML files and database.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # consolidate
    p_consolidate = subparsers.add_parser('consolidate', help="Consolidate unique YAML questions from across the repository into a single file.")
    p_consolidate.add_argument('-o', '--output', type=Path, help=f'Output file path for consolidated questions.')
    p_consolidate.set_defaults(func=do_consolidate)
    
    # create-quizzes
    p_create_quizzes = subparsers.add_parser('create-quizzes', help="Create quizzes from consolidated YAML backup.")
    p_create_quizzes.set_defaults(func=do_create_quizzes)
    
    # create-db
    p_create_db = subparsers.add_parser('create-db', help="Populate the SQLite database from YAML backup files.")
    p_create_db.add_argument("--yaml-files", nargs="*", type=str, help="Path(s) to input YAML file(s) or directories.")
    p_create_db.add_argument("--db-path", type=str, default=None, help="Path to the SQLite database file.")
    p_create_db.add_argument("--clear", action="store_true", help="Clear the database before populating.")
    p_create_db.set_defaults(func=do_create_db)
    
    # deduplicate
    p_deduplicate = subparsers.add_parser('deduplicate', help="Deduplicate YAML questions in a directory.")
    p_deduplicate.add_argument("directory", type=str, help="Directory containing YAML question files.")
    p_deduplicate.add_argument("-o", "--output-file", type=str, help="Output file for consolidated unique questions.")
    p_deduplicate.add_argument("--dry-run", action="store_true", help="Perform a dry run without writing files.")
    p_deduplicate.set_defaults(func=do_deduplicate)
    
    # diff
    p_diff = subparsers.add_parser('diff', help="Diff YAML backup files to track changes.")
    p_diff.add_argument('files', nargs='*', help="Two YAML files to compare. If not provided, compares all backups.")
    p_diff.add_argument("--range", help="Number of recent versions to diff (e.g., '5' for last 5). 'all' to diff all.", default="all")
    p_diff.set_defaults(func=do_diff)
    
    # export
    p_export = subparsers.add_parser('export', help="Export questions DB to YAML.")
    p_export.add_argument("-o", "--output", help="Output YAML file path.")
    p_export.set_defaults(func=do_export)

    # import-ai
    p_import_ai = subparsers.add_parser('import-ai', help="Import from YAML with AI categorization.")
    p_import_ai.add_argument("output_db", help="Path to the new SQLite database file to be created.")
    p_import_ai.add_argument("--search-dir", action='append', help="Directory to search for YAML files. Can be used multiple times.")
    p_import_ai.set_defaults(func=do_import_ai)

    # index
    p_index = subparsers.add_parser('index', help="Finds all YAML files and creates an index file with their metadata.")
    p_index.set_defaults(func=do_index)
    
    # init
    p_init = subparsers.add_parser('init', help="Initializes the database from consolidated YAML backups.")
    p_init.set_defaults(func=do_init)
    
    # restore
    p_restore = subparsers.add_parser('restore', help="Restore questions from YAML into the database.")
    p_restore.add_argument("paths", nargs='*', help="Paths to YAML files or directories. Scans default dirs if not provided.")
    p_restore.add_argument('--clear', action='store_true', help="Clear the existing database before restoring.")
    p_restore.add_argument('--db-path', type=str, default=None, help="Path to the SQLite database file.")
    p_restore.set_defaults(func=do_restore)

    # list-backups
    p_list_backups = subparsers.add_parser('list-backups', help='Finds and displays all YAML backup files.')
    p_list_backups.add_argument("--path-only", action="store_true", help="Only prints the paths of the files.")
    p_list_backups.set_defaults(func=do_list_backups)
    
    # write
    p_write = subparsers.add_parser('write', help="Write DB from YAML backup.")
    p_write.add_argument('yaml_file', help='YAML file to load.')
    p_write.add_argument('--overwrite', action='store_true', help='Overwrite existing questions.')
    p_write.add_argument('--backup', action='store_true', help='Backup current DB before writing.')
    p_write.set_defaults(func=do_write)

    # backup-stats
    p_backup_stats = subparsers.add_parser('backup-stats', help="Show stats for the latest YAML backup file.")
    p_backup_stats.add_argument('paths', nargs='*', help='Path(s) to YAML file(s) or directories.')
    p_backup_stats.add_argument('-p', '--pattern', help='Regex to filter filenames')
    p_backup_stats.add_argument('--json', action='store_true', help='Output stats in JSON format')
    p_backup_stats.set_defaults(func=do_backup_stats)
    
    # statistics
    p_stats = subparsers.add_parser('stats', help="Get statistics about questions in YAML files.")
    p_stats.add_argument("path", nargs='?', default=None, help="Path to a YAML file or directory.")
    p_stats.set_defaults(func=do_statistics)

    # group-backups
    p_group_backups = subparsers.add_parser('group-backups', help="Group legacy YAML backup quizzes into a single module.")
    p_group_backups.set_defaults(func=do_group_backups)

    # import-bak
    p_import_bak = subparsers.add_parser('import-bak', help="Import questions from legacy YAML backup directory.")
    p_import_bak.set_defaults(func=do_import_bak)

    # migrate-all
    p_migrate_all = subparsers.add_parser('migrate-all', help="Migrate all YAML questions from standard directories to DB.")
    p_migrate_all.set_defaults(func=do_migrate_all)

    # migrate-bak
    p_migrate_bak = subparsers.add_parser('migrate-bak', help="Clear DB and migrate from YAML backup directory.")
    p_migrate_bak.set_defaults(func=do_migrate_bak)

    # verify
    p_verify = subparsers.add_parser('verify', help="Verify YAML question import and loading.")
    p_verify.add_argument("paths", nargs='+', help="Path(s) to YAML file(s) or directories to verify.")
    p_verify.set_defaults(func=do_verify)

    # organize-generated
    p_organize = subparsers.add_parser('organize-generated', help="Consolidate, import, and clean up AI-generated YAML questions.")
    p_organize.add_argument('--source-dir', default='questions/generated_yaml', help="Directory with generated YAML files.")
    p_organize.add_argument('--output-file', default='questions/ai_generated_consolidated.yaml', help="Consolidated output YAML file.")
    p_organize.add_argument('--db-path', default=None, help="Path to the SQLite database file.")
    p_organize.add_argument('--no-cleanup', action='store_true', help="Do not delete original individual YAML files after consolidation.")
    p_organize.add_argument('--dry-run', action='store_true', help="Show what would be done without making changes.")
    p_organize.set_defaults(func=do_organize_generated)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    main()
