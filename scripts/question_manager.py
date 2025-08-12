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
except ImportError as e:
    print(f"Missing required packages. Please install them: pip install PyYAML tqdm. Error: {e}", file=sys.stderr)
    sys.exit(1)

# Kubelingo imports
from kubelingo.database import (
    get_db_connection, SUBJECT_MATTER, init_db, add_question
)
from kubelingo.question import Question, ValidationStep, QuestionCategory
from kubelingo.modules.ai_categorizer import AICategorizer
import kubelingo.utils.config as cfg
import kubelingo.database as db_mod
from kubelingo.utils.path_utils import get_all_yaml_files_in_repo, get_live_db_path
from kubelingo.utils.ui import Fore, Style


def _row_to_question_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Converts a sqlite3.Row from the questions table to a dictionary."""
    if not row:
        return {}
    q_dict = dict(row)
    # Fields that are stored as JSON strings in the DB
    for key in ['validation_steps', 'answers', 'tags', 'links']:
        if key in q_dict and q_dict[key] and isinstance(q_dict[key], str):
            try:
                q_dict[key] = json.loads(q_dict[key])
            except json.JSONDecodeError:
                # Keep as string if not valid JSON
                pass
    return q_dict


def get_all_questions(conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Fetches all questions from the database."""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions")
        rows = cursor.fetchall()
        questions = [_row_to_question_dict(row) for row in rows]
    finally:
        if close_conn:
            conn.close()

    return questions


# --- from: scripts/categorize_questions.py ---
def handle_categorize(args):
    """Categorize questions by subject."""
    conn = get_db_connection()
    cur = conn.cursor()

    if args.assign:
        rowid, subject = args.assign
        if subject not in SUBJECT_MATTER:
            print(f"Invalid subject. Must be one of: {SUBJECT_MATTER}")
            sys.exit(1)
        cur.execute('UPDATE questions SET subject_matter = ? WHERE rowid = ?', (subject, rowid))
        conn.commit()
        print(f"Assigned subject '{subject}' to question rowid {rowid}")
    else:
        cur.execute('SELECT rowid, id, prompt, subject_matter FROM questions')
        rows = cur.fetchall()
        missing = []
        for row in rows:
            subj = row[3]
            if subj not in SUBJECT_MATTER:
                missing.append(row)
        if not missing:
            print('All questions have valid subjects.')
        else:
            print('Questions with missing or invalid subjects:')
            for row in missing:
                print(f"[{row[0]}] id={row[1]} subject_matter={row[3]}\n  Prompt: {row[2]!r}\n")
    conn.close()


# --- from: scripts/consolidate_unique_yaml_questions.py ---
def consolidate_unique_yaml_questions(output_file: Path):
    """
    Finds all YAML quiz files, extracts unique questions based on their 'prompt',
    and consolidates them into a single YAML file.
    """
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
                # Support multi-document YAML files and single docs with a 'questions' key
                documents = yaml.safe_load_all(f)
                for data in documents:
                    if not data:
                        continue
                    # Handle structure { 'questions': [...] }
                    if isinstance(data, dict) and 'questions' in data and isinstance(data.get('questions'), list):
                        questions_in_file.extend(data['questions'])
                    # Handle structure [ {question1}, {question2} ]
                    elif isinstance(data, list):
                        questions_in_file.extend(data)

        except (yaml.YAMLError, IOError):
            continue  # Ignore files that can't be read or parsed

        if questions_in_file:
            files_with_questions_count += 1
            for question in questions_in_file:
                # Ensure question is a dict with a prompt
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
        # Save as a single document with a 'questions' key
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump({'questions': unique_questions}, f, sort_keys=False, indent=2)
        print(f"\n{Fore.GREEN}Successfully consolidated {len(unique_questions)} unique questions to:{Style.RESET_ALL}")
        print(str(output_file))
    except IOError as e:
        print(f"{Fore.RED}Error writing to output file {output_file}: {e}{Style.RESET_ALL}")


def handle_consolidate_unique_yaml(args):
    """Handler for consolidating unique YAML questions."""
    consolidate_unique_yaml_questions(args.output)


# --- from: scripts/deduplicate_questions.py ---
def find_duplicates(conn):
    """Finds questions with duplicate prompts in the database."""
    questions = get_all_questions(conn=conn)

    prompts = defaultdict(list)
    for q in questions:
        prompts[q['prompt']].append(q)

    duplicates = {}
    for prompt, q_list in prompts.items():
        if len(q_list) > 1:
            # Sort by ID descending to ensure the newest item is first
            q_list.sort(key=lambda x: x['id'], reverse=True)
            duplicates[prompt] = q_list

    return duplicates


def manage_duplicates(conn, duplicates, delete=False):
    """Lists or deletes duplicate questions."""
    if not duplicates:
        print("No duplicate questions found.")
        return

    print(f"Found {len(duplicates)} prompts with duplicate questions.")

    if delete:
        cursor = conn.cursor()
        deleted_count = 0
        print("\nDeleting duplicates (keeping the newest occurrence of each)...")
    else:
        print("\nListing duplicate questions (use --delete to remove):")

    for prompt, q_list in duplicates.items():
        print(f"\n- Prompt: \"{prompt}\"")
        print(f"  - Keeping: {q_list[0]['id']} (source: {q_list[0]['source_file']})")

        ids_to_delete = [q['id'] for q in q_list[1:]]

        for q in q_list[1:]:
            status = "Deleting" if delete else "Duplicate"
            print(f"  - {status}: {q['id']} (source: {q['source_file']})")

        if delete and ids_to_delete:
            placeholders = ', '.join('?' for _ in ids_to_delete)
            cursor.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", ids_to_delete)
            deleted_count += len(ids_to_delete)

    if delete:
        conn.commit()
        print(f"\nSuccessfully deleted {deleted_count} duplicate questions.")


def handle_deduplicate(args):
    """Handler for finding and removing duplicate questions."""
    db_path = args.db_path or get_live_db_path()
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = None
    try:
        conn = get_db_connection(db_path)
        duplicates = find_duplicates(conn)
        manage_duplicates(conn, duplicates, delete=args.delete)

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if conn:
            conn.close()


# --- from: scripts/fix_question_categories.py ---
def handle_fix_categories(args):
    """Interactively fix or assign schema_category for questions in the database."""
    questions = get_all_questions()
    to_fix = [q for q in questions if not q.get('schema_category')]
    if not to_fix:
        print("All questions have a schema_category assigned.")
        return
    print(f"Found {len(to_fix)} questions needing a schema_category.")

    conn = get_db_connection()
    try:
        for q in to_fix:
            print(f"\nID: {q.get('id')} | Current category: {q.get('schema_category')}\nPrompt: {q.get('prompt')[:80]}...")
            if args.list_only:
                continue
            new_cat = input("Enter new schema_category (or leave blank to skip): ").strip()
            if not new_cat:
                print("Skipped.")
                continue

            try:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE questions SET schema_category = ? WHERE id = ?",
                    (new_cat, q.get('id'))
                )
                conn.commit()
                print("Updated.")
            except Exception as e:
                print(f"Failed to update: {e}")
    finally:
        conn.close()
    print("Done fixing schema categories.")


# --- from: scripts/format_questions.py ---
def handle_format(args):
    """Reformat question YAML files for style consistency."""
    path = Path(args.directory)
    if not path.is_dir():
        print(f'Directory not found: {path}', file=sys.stderr)
        sys.exit(1)

    for file in path.rglob('*.yaml'):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            with open(file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, sort_keys=True, default_flow_style=False)
            print(f'Formatted {file}')
        except Exception as e:
            print(f"Could not format {file}: {e}", file=sys.stderr)


# --- from: scripts/lint_fix_question_format.py ---
def lint_dict(q, source=''):
    required = ['id', 'prompt', 'source_file']
    missing = [f for f in required if not q.get(f)]
    if missing:
        print(f"[{source}] Missing fields {missing} in question: {q.get('id')}")


def lint_yaml(path):
    try:
        data = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
        questions_to_lint = []
        if isinstance(data, dict) and 'questions' in data and isinstance(data.get('questions'), list):
            questions_to_lint = data['questions']
        elif isinstance(data, list):
            questions_to_lint = data
        else:
            print(f"[{path}] YAML root is not a list or a dict with a 'questions' key.")
            return

        for q in questions_to_lint:
            lint_dict(q, source=path)
    except (yaml.YAMLError, IOError) as e:
        print(f"Could not read or parse YAML file {path}: {e}")


def lint_db():
    qs = get_all_questions()
    for q in qs:
        lint_dict(q, source='DB')


def handle_lint(args):
    """Lint question structure in YAML or database."""
    if args.yaml_file:
        path = Path(args.yaml_file)
        if not path.is_file():
            print(f"File not found: {path}")
            sys.exit(1)
        lint_yaml(path)
    elif args.db:
        lint_db()


# --- from: scripts/reorganize_questions.py ---
def reorganize_by_ai(db_path: Optional[str] = None):
    """Categorize questions using an AI model."""
    try:
        categorizer = AICategorizer()
    except (ImportError, ValueError) as e:
        print(f"{Fore.RED}Failed to initialize AI Categorizer: {e}{Style.RESET_ALL}")
        print(f"{Fore.RED}Please ensure an AI provider is configured (e.g., set OPENAI_API_KEY).{Style.RESET_ALL}")
        return

    conn = get_db_connection(db_path=db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE category_id IS NULL OR subject_id IS NULL")
    rows = cursor.fetchall()

    if not rows:
        print(f"{Fore.GREEN}All questions are already categorized. No migration needed.{Style.RESET_ALL}")
        conn.close()
        return

    print(f"Found {len(rows)} questions to categorize using AI...")

    updated_count = 0
    with tqdm(rows, desc="Categorizing questions") as pbar:
        for row in pbar:
            q_dict = _row_to_question_dict(row)
            q_id = q_dict.get('id')

            result = categorizer.categorize_question(q_dict)

            if result:
                category_id_from_ai = result.get("exercise_category")
                subject_id = result.get("subject_matter")

                # Map AI output to the database schema for robustness
                exercise_category_map = {
                    "basic": "basic",
                    "command": "command",
                    "manifest": "manifest",
                    "Basic/Open-Ended": "basic",
                    "Command-Based/Syntax": "command",
                    "Manifests": "manifest",
                }
                category_id = exercise_category_map.get(category_id_from_ai)

                if category_id and subject_id:
                    cursor.execute(
                        "UPDATE questions SET category_id = ?, subject_id = ? WHERE id = ?",
                        (category_id, subject_id, q_id)
                    )
                    updated_count += 1
                    pbar.set_postfix(status="Success")
                else:
                    pbar.set_postfix(status=f"Invalid AI data for {q_id}")
            else:
                pbar.set_postfix(status=f"Failed: {q_id}")

    conn.commit()
    conn.close()

    print("\nAI reorganization complete.")
    print(f"  - Questions updated: {updated_count}")
    print(f"  - Questions failed/skipped: {len(rows) - updated_count}")


def map_type_to_schema(q_type: str) -> str:
    q = (q_type or '').lower()
    if q in ('yaml_author', 'yaml_edit', 'live_k8s_edit'):
        return QuestionCategory.MANIFEST.value
    if q in ('command', 'live_k8s'):
        return QuestionCategory.COMMAND.value
    if q == 'socratic':
        return QuestionCategory.OPEN_ENDED.value
    # default fallback
    return QuestionCategory.COMMAND.value


def reorganize_by_type_mapping(db_path: Optional[str] = None):
    """Reassign category_id based on the question_type column."""
    print("Reassigning exercise category (category_id) based on question_type...")
    conn = get_db_connection(db_path=db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, question_type FROM questions")
    rows = cursor.fetchall()
    total = len(rows)
    updated = 0
    for row in tqdm(rows, desc="Updating categories by type"):
        qid = row['id']
        q_type = row['question_type'] or ''
        new_cat = map_type_to_schema(q_type)
        cursor.execute(
            "UPDATE questions SET category_id = ? WHERE id = ?", (new_cat, qid)
        )
        if cursor.rowcount > 0:
            updated += 1
    conn.commit()
    conn.close()
    print(f"\nReassigned category_id for {updated}/{total} questions.")


def reorganize_by_dataclass_logic(db_path: Optional[str] = None):
    """
    Iterates through all questions, determines schema category using dataclass logic, and updates them.
    """
    print("Reorganizing question categories based on dataclass logic...")
    conn = get_db_connection(db_path=db_path)
    if not conn:
        print("Failed to connect to the database.")
        return

    all_questions = get_all_questions(conn=conn)
    print(f"Found {len(all_questions)} total questions to process.")

    updated_count = 0
    questions_by_source = {}

    cursor = conn.cursor()

    for q_dict in tqdm(all_questions, desc="Updating categories by dataclass logic"):
        try:
            q_copy = q_dict.copy()

            if q_copy.get('validation_steps'):
                q_copy['validation_steps'] = [
                    ValidationStep(**step) for step in q_copy['validation_steps'] if isinstance(step, dict)
                ]
            q_copy.pop('validation', None)

            question_obj = Question(**q_copy)

            new_category = question_obj.schema_category.value if question_obj.schema_category else None

            source_file = q_dict.get('source_file', 'unknown')
            if source_file not in questions_by_source:
                questions_by_source[source_file] = []
            questions_by_source[source_file].append(new_category)

            if new_category and new_category != q_dict.get('category_id'):
                cursor.execute(
                    "UPDATE questions SET category_id = ? WHERE id = ?",
                    (new_category, q_dict['id'])
                )
                updated_count += 1

        except Exception as e:
            print(f"  [ERROR] Could not process question ID {q_dict.get('id')}: {e}")

    conn.commit()
    conn.close()
    print(f"\nReorganization complete. Updated {updated_count} questions.")

    # Report on files with mixed content
    print("\nChecking for quiz files with mixed categories...")
    mixed_files = 0
    for source, categories in questions_by_source.items():
        unique_categories = set(c for c in categories if c)
        if len(unique_categories) > 1:
            print(f"  - File '{source}' contains multiple categories: {Counter(categories)}")
            mixed_files += 1

    if mixed_files == 0:
        print("No mixed-category quiz files found.")
    else:
        print(f"\nFound {mixed_files} files with mixed categories.")


def handle_reorganize(args):
    """Handler for reorganizing questions."""
    if args.method == 'ai':
        reorganize_by_ai(db_path=args.db_path)
    elif args.method == 'type-mapping':
        reorganize_by_type_mapping(db_path=args.db_path)
    elif args.method == 'dataclass':
        reorganize_by_dataclass_logic(db_path=args.db_path)


# --- from: scripts/verify_db_questions.py ---
def verify_questions(db_path: str):
    """
    Connects to the database and prints a summary of question counts per category.
    """
    if not Path(db_path).exists():
        print(f"Database file not found at: {db_path}")
        return

    print(f"Verifying database: {db_path}")
    conn = get_db_connection(db_path=db_path)

    try:
        cursor = conn.cursor()

        # Get total questions
        cursor.execute("SELECT COUNT(*) FROM questions")
        total_questions = cursor.fetchone()[0]
        print(f"\nTotal questions in database: {total_questions}")

        if total_questions == 0:
            return

        # Get counts per category
        print("\nQuestions per category:")
        cursor.execute("SELECT category, COUNT(*) FROM questions GROUP BY category ORDER BY category")
        rows = cursor.fetchall()

        if not rows:
            print("  No categories found.")
        else:
            for row in rows:
                category, count = row
                category_name = category if category else "Uncategorized"
                print(f"  - {category_name}: {count}")

        # Get counts per schema_category
        print("\nQuestions per schema_category:")
        cursor.execute("SELECT schema_category, COUNT(*) FROM questions GROUP BY schema_category ORDER BY schema_category")
        rows = cursor.fetchall()

        if not rows:
            print("  No schema_categories found.")
        else:
            for row in rows:
                schema_category, count = row
                schema_category_name = schema_category if schema_category else "Uncategorized"
                print(f"  - {schema_category_name}: {count}")

        print("\n--- Data Integrity Checks ---")
        all_questions = get_all_questions(conn=conn)

        uncategorized = [q for q in all_questions if not q.get('category')]
        if uncategorized:
            print(f"\nFound {len(uncategorized)} uncategorized questions. The app may ignore these.")
            print("Consider assigning a category to them:")
            for q in uncategorized[:10]:  # To avoid spamming, show first 10
                print(f"  - ID: {q.get('id')}, Source: {q.get('source_file')}")
            if len(uncategorized) > 10:
                print(f"  ... and {len(uncategorized) - 10} more.")
        else:
            print("\nAll questions have a category assigned.")

        no_schema = [q for q in all_questions if not q.get('schema_category')]
        if no_schema:
            print(f"\nFound {len(no_schema)} questions with no schema_category. The app may ignore these.")
            for q in no_schema[:10]:
                print(f"  - ID: {q.get('id')}, Source: {q.get('source_file')}")
            if len(no_schema) > 10:
                print(f"  ... and {len(no_schema) - 10} more.")
        else:
            print("All questions have a schema_category assigned.")

        no_prompt = [q for q in all_questions if not q.get('prompt')]
        if no_prompt:
            print(f"\nFound {len(no_prompt)} questions with no prompt.")
            for q in no_prompt:
                print(f"  - ID: {q.get('id')}, Source: {q.get('source_file')}")
        else:
            print("All questions have a prompt.")

        # Check for answerable questions
        unanswerable = []
        for q in all_questions:
            # A question is considered answerable if it has any of these fields with a non-empty value.
            if not (q.get('response') or
                    q.get('validator') or
                    q.get('validation_steps') or
                    q.get('correct_yaml') or
                    q.get('answer') or
                    q.get('answers')):
                unanswerable.append(q)

        if unanswerable:
            print(f"\nFound {len(unanswerable)} questions without a way to check answers.")
            print("Consider adding a `response`, `validator`, `validation_steps`, `correct_yaml`, or `answer`/`answers` field:")
            for q in unanswerable[:10]:
                print(f"  - ID: {q.get('id')}, Source: {q.get('source_file')}")
            if len(unanswerable) > 10:
                print(f"  ... and {len(unanswerable) - 10} more.")
        else:
            print("\nAll questions have a method for answer validation.")

    finally:
        conn.close()


def handle_verify(args):
    """Handler for verifying DB questions."""
    database_path = args.db_path or get_live_db_path()
    verify_questions(database_path)


# --- from: scripts/add_ui_config_questions.py ---
def handle_add_ui_config(args):
    """Add UI configuration questions into the database."""
    # This function's logic is from scripts/add_ui_config_questions.py
    # It ensures the user's local database is targeted.
    home_cfg_dir = os.path.expanduser('~/.kubelingo')
    os.makedirs(home_cfg_dir, exist_ok=True)
    cfg.APP_DIR = home_cfg_dir
    cfg.DATABASE_FILE = os.path.join(home_cfg_dir, 'kubelingo.db')
    db_mod.DATABASE_FILE = cfg.DATABASE_FILE

    # Initialize database schema and get connection
    init_db()
    conn = get_db_connection()

    try:
        # Define UI config footer question manually
        starting_yaml = (
            "footer:\n"
            "  version: \"CKAD Simulator Kubernetes 1.33\"\n"
            "  link: \"https://killer.sh\""
        )
        correct_yaml = (
            "footer:\n"
            "  version: \"CKAD Simulator Kubernetes 1.34\"\n"
            "  link: \"https://killer.sh\""
        )
        questions = [
            {
                'id': 'ui_config::footer::0',
                'prompt': 'Bump the version string in the footer from "CKAD Simulator Kubernetes 1.33" to "CKAD Simulator Kubernetes 1.34" in the UI configuration file.',
                'starting_yaml': starting_yaml,
                'correct_yaml': correct_yaml,
                'category': 'Footer',
            }
        ]

        source_file = 'ui_config_script'
        added = 0
        for q in questions:
            validator = {'type': 'yaml', 'expected': q['correct_yaml']}
            try:
                # Merged from script, fixing missing conn and adapting to db signature
                add_question(
                    conn=conn,
                    id=q['id'],
                    prompt=q['prompt'],
                    source_file=source_file,
                    response=None,
                    category_id=q.get('category'),
                    subject_id=None,
                    source='script',
                    raw=str(q),
                    validation_steps=[],
                    validator=validator
                )
                print(f"Added UI question {q['id']}")
                added += 1
            except Exception as e:
                print(f"Failed to add question {q['id']}: {e}")
        print(f"Total UI questions added: {added}")
    finally:
        conn.close()


# --- from: scripts/import_pdf_questions.py ---
def handle_import_pdf(args):
    """Import new quiz questions from a PDF file into the database."""
    # This logic is from scripts/import_pdf_questions.py
    init_db()

    pdf_path = Path(args.pdf_file)
    if not pdf_path.is_file():
        print(f"Error: PDF not found at {pdf_path}", file=sys.stderr)
        return

    # Convert PDF to text via pdftotext
    try:
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tmp:
            txt_path = tmp.name
        # Use capture_output to avoid printing stdout, but show stderr on error
        subprocess.run(['pdftotext', str(pdf_path), txt_path], check=True, capture_output=True, text=True)
        print("Successfully extracted text from PDF.")
    except FileNotFoundError:
        print("Error: 'pdftotext' command not found.", file=sys.stderr)
        print("Please install poppler-utils (e.g., 'sudo apt-get install poppler-utils' or 'brew install poppler').", file=sys.stderr)
        if 'txt_path' in locals() and os.path.exists(txt_path):
            os.remove(txt_path)
        return
    except subprocess.CalledProcessError as e:
        print(f"Failed to extract text from PDF: {e.stderr}", file=sys.stderr)
        if 'txt_path' in locals() and os.path.exists(txt_path):
            os.remove(txt_path)
        return

    with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
    os.remove(txt_path)

    parts = re.split(r"Question\s+(\d+)\s*\|", text)
    imported = 0
    conn = get_db_connection()
    try:
        for i in range(1, len(parts), 2):
            qnum = parts[i].strip()
            content = parts[i+1].strip()
            lines = content.splitlines()
            if not lines:
                continue
            title = lines[0].strip()
            body = '\n'.join(lines[1:]).strip()
            prompt = f"Simulator Question {qnum}: {title}\n{body}" if body else f"Simulator Question {qnum}: {title}"

            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM questions WHERE prompt LIKE ?", (f"%Simulator Question {qnum}:%",))
            if cursor.fetchone()[0] > 0:
                print(f"Skipping Question {qnum}, already in DB.")
                continue

            qid = f"sim_pdf::{qnum}"
            try:
                add_question(
                    conn=conn, id=qid, prompt=prompt, source_file='pdf_simulator', response=None,
                    category_id='Simulator', subject_id=None, source='pdf', raw=prompt,
                    validation_steps=[], validator=None
                )
                print(f"Added Question {qnum} to DB.")
                imported += 1
            except Exception as e:
                print(f"Failed to add Question {qnum}: {e}")
    finally:
        conn.close()

    print(f"Imported {imported} new questions from PDF.")

    if imported > 0 and not args.no_backup:
        try:
            live_db_path = cfg.DATABASE_FILE
            backup_db_path = cfg.BACKUP_DATABASE_FILE
            if not live_db_path or not backup_db_path:
                print("DATABASE_FILE or BACKUP_DATABASE_FILE not configured, skipping backup.", file=sys.stderr)
                return
            shutil.copy2(live_db_path, backup_db_path)
            print(f"Backed up live DB to {backup_db_path}")
        except Exception as e:
            print(f"Failed to backup DB: {e}", file=sys.stderr)


# --- Main CLI Router ---
def main():
    """Main entry point for the question manager CLI."""
    parser = argparse.ArgumentParser(
        description="A unified CLI for managing Kubelingo questions.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', required=True, help='Action to perform')

    # Sub-parser for 'categorize'
    parser_categorize = subparsers.add_parser('categorize', help='Identify and assign subjects to questions.', description="Identify questions with missing or invalid subjects and optionally assign one.")
    parser_categorize.add_argument('--assign', nargs=2, metavar=('ROWID', 'SUBJECT'), help='Assign SUBJECT to the question with the given ROWID.')
    parser_categorize.set_defaults(func=handle_categorize)

    # Sub-parser for 'consolidate-unique-yaml'
    parser_consolidate = subparsers.add_parser('consolidate-unique-yaml', help='Consolidate unique questions from all YAML files into a single backup file.', description="Finds all YAML quiz files, extracts unique questions based on their 'prompt', and consolidates them into a single YAML file.")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_filename = f'consolidated_unique_questions_{timestamp}.yaml'
    default_path = Path(project_root) / 'backups' / 'yaml' / default_filename
    parser_consolidate.add_argument('-o', '--output', type=Path, default=default_path, help=f'Output file path for consolidated questions. Default: {default_path}')
    parser_consolidate.set_defaults(func=handle_consolidate_unique_yaml)

    # Sub-parser for 'deduplicate'
    parser_deduplicate = subparsers.add_parser('deduplicate', help='Find and optionally remove duplicate questions from the database.', description="Finds and optionally removes duplicate questions from the database based on prompt text.")
    parser_deduplicate.add_argument("--db-path", default=None, help="Path to the SQLite database file. Defaults to the live application database.")
    parser_deduplicate.add_argument("--delete", action="store_true", help="Delete duplicate questions, keeping only the newest occurrence of each.")
    parser_deduplicate.set_defaults(func=handle_deduplicate)

    # Sub-parser for 'fix-categories'
    parser_fix = subparsers.add_parser('fix-categories', help='Interactively fix or assign schema_category for questions.', description="Interactively fix or assign schema_category for questions in the database.")
    parser_fix.add_argument('--list-only', action='store_true', help='Only list questions that need a category, without prompting for changes.')
    parser_fix.set_defaults(func=handle_fix_categories)

    # Sub-parser for 'format'
    parser_format = subparsers.add_parser('format', help='Reformat question YAML files for style consistency.', description="Lint and reformat question YAML files for style consistency.")
    parser_format.add_argument('directory', nargs='?', default='question-data/questions', help='Directory of YAML question files to reformat.')
    parser_format.set_defaults(func=handle_format)

    # Sub-parser for 'lint'
    parser_lint = subparsers.add_parser('lint', help='Lint question structure in YAML files or the database.', description="Lint and report missing or malformed fields in question definitions (YAML or DB).")
    group = parser_lint.add_mutually_exclusive_group(required=True)
    group.add_argument('--yaml-file', help='Path to a YAML file of questions to lint.')
    group.add_argument('--db', action='store_true', help='Lint all questions in the database.')
    parser_lint.set_defaults(func=handle_lint)

    # Sub-parser for 'reorganize'
    parser_reorganize = subparsers.add_parser('reorganize', help='Reorganize question categories and subjects using various methods.', description="This script reorganizes all questions in the database by assigning them to a schema category and a subject matter area.")
    parser_reorganize.add_argument("-m", "--method", choices=['ai', 'type-mapping', 'dataclass'], default='ai', help="Choose the reorganization method:\n- ai: Use an AI model (default).\n- type-mapping: Use rules to map `question_type` to `schema_category`.\n- dataclass: Use Question dataclass logic to determine `schema_category`.")
    parser_reorganize.add_argument("--db-path", type=str, default=None, help="Path to the SQLite database file. Defaults to the live application database.")
    parser_reorganize.set_defaults(func=handle_reorganize)

    # Sub-parser for 'verify'
    parser_verify = subparsers.add_parser('verify', help='Verify data integrity and counts of questions in a database.', description="Connects to the database and prints a summary of question counts per category and runs data integrity checks.")
    parser_verify.add_argument("db_path", nargs="?", default=None, help="Path to the SQLite database file. If not provided, uses the live database.")
    parser_verify.set_defaults(func=handle_verify)

    # Sub-parser for 'add-ui-config'
    parser_add_ui = subparsers.add_parser('add-ui-config', help='Add hardcoded UI configuration questions to the database.', description="Adds a predefined set of UI configuration questions to the user's local database.")
    parser_add_ui.set_defaults(func=handle_add_ui_config)

    # Sub-parser for 'import-pdf'
    parser_import_pdf = subparsers.add_parser('import-pdf', help='Import questions from a PDF file.', description="Import new quiz questions from the 'Killer Shell - Exam Simulators.pdf' into the Kubelingo database.")
    default_pdf_path = os.path.join(project_root, 'Killer Shell - Exam Simulators.pdf')
    parser_import_pdf.add_argument('pdf_file', nargs='?', default=default_pdf_path, help=f"Path to the PDF file to import questions from. Default: {default_pdf_path}")
    parser_import_pdf.add_argument('--no-backup', action='store_true', help="Do not back up the database after importing questions.")
    parser_import_pdf.set_defaults(func=handle_import_pdf)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
