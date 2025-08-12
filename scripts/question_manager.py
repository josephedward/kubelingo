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
    import requests
except ImportError as e:
    print(f"Missing required packages. Please install them: pip install PyYAML tqdm requests. Error: {e}", file=sys.stderr)
    sys.exit(1)

# Kubelingo imports
from kubelingo.database import (
    get_db_connection, SUBJECT_MATTER, init_db,
    _row_to_question_dict, import_questions_from_yaml_files
)
from kubelingo.question import Question, ValidationStep, QuestionCategory
from kubelingo.modules.ai_categorizer import AICategorizer
from kubelingo.modules.question_generator import AIQuestionGenerator
import kubelingo.utils.config as cfg
import kubelingo.database as db_mod
from kubelingo.utils.path_utils import get_all_yaml_files_in_repo, get_live_db_path
from kubelingo.utils.ui import Fore, Style


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text content from a PDF using pdftotext."""
    try:
        result = subprocess.run(
            ["pdftotext", pdf_path, "-"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except FileNotFoundError:
        print("Error: 'pdftotext' command not found.", file=sys.stderr)
        print("Please install poppler-utils (e.g., 'sudo apt-get install poppler-utils' or 'brew install poppler').", file=sys.stderr)
        return ""
    except subprocess.CalledProcessError as e:
        print(f"Error extracting text from PDF: {e.stderr}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"An unexpected error occurred during PDF text extraction: {e}", file=sys.stderr)
        return ""




def get_existing_prompts(conn) -> Set[str]:
    """Fetch all unique question prompts from the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT prompt FROM questions")
    return {row[0] for row in cursor.fetchall()}


def backup_database(source_db_path: str):
    """Creates a timestamped backup of the database file."""
    if not os.path.exists(source_db_path):
        print(f"Source database {source_db_path} not found. Skipping backup.", file=sys.stderr)
        return

    # Use a consistent backup directory structure
    backup_dir = Path(project_root) / 'backups' / 'db'
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = Path(source_db_path).stem + f"_backup_{timestamp}.db"
    backup_path = backup_dir / backup_filename

    try:
        shutil.copy2(source_db_path, backup_path)
        print(f"Database backed up to {backup_path}")
    except Exception as e:
        print(f"Failed to backup database: {e}", file=sys.stderr)


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


# --- from: scripts/build_question_db.py ---
def handle_build_db(args):
    """Handler for building the database from YAML files."""
    db_path = args.db_path or get_live_db_path()

    if args.clear:
        if os.path.exists(db_path):
            if not args.no_backup:
                print("Backing up existing database before clearing...")
                backup_database(db_path)
            os.remove(db_path)
            print(f"Removed existing database at {db_path}")

    conn = get_db_connection(db_path)
    init_db(conn=conn)

    if args.files:
        files_to_import = [Path(f) for f in args.files]
    else:
        print("No specific files provided, scanning repo for all YAML question files...")
        files_to_import = get_all_yaml_files_in_repo()

    if not files_to_import:
        print("No YAML files found to import.")
    else:
        print(f"Found {len(files_to_import)} YAML files to import.")
        import_questions_from_yaml_files(files_to_import, conn)

    conn.close()


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
        cur.execute('UPDATE questions SET subject = ? WHERE rowid = ?', (subject, rowid))
        conn.commit()
        print(f"Assigned subject '{subject}' to question rowid {rowid}")
    else:
        cur.execute('SELECT rowid, id, prompt, subject FROM questions')
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
                print(f"[{row[0]}] id={row[1]} subject={row[3]}\n  Prompt: {row[2]!r}\n")
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


# --- from: scripts/enrich_question_sources.py ---
def handle_enrich_sources(args):
    """
    Scans the database for questions without a 'source' and populates it
    based on the source_file.
    """
    print("Enriching question sources in the database...")
    source_map = {}
    for name, path in cfg.ENABLED_QUIZZES.items():
        source_file = os.path.basename(path)
        source_map[source_file] = name

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Find questions that need a source
        cursor.execute("SELECT id, source_file FROM questions WHERE source IS NULL OR source = ''")
        questions_to_update = cursor.fetchall()

        if not questions_to_update:
            print("All questions already have a source. No action needed.")
            return

        print(f"Found {len(questions_to_update)} questions missing a source. Updating...")

        updated_count = 0
        for q_id, source_file in questions_to_update:
            if source_file in source_map:
                source_name = source_map[source_file]
                cursor.execute("UPDATE questions SET source = ? WHERE id = ?", (source_name, q_id))
                updated_count += 1
            else:
                print(f"  - Warning: No source mapping found for '{source_file}' (question ID: {q_id})")

        conn.commit()
        print(f"Successfully updated {updated_count} questions.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()


# --- from: scripts/export_db_to_yaml.py ---
def handle_export_to_yaml(args):
    """Export all questions from the database to a YAML file."""
    print(f"{Fore.CYAN}--- Exporting database questions to YAML ---{Style.RESET_ALL}")
    db_path = args.db_path or get_live_db_path()
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = get_db_connection(db_path)
    questions = get_all_questions(conn)
    conn.close()

    if not questions:
        print(f"{Fore.YELLOW}No questions found in the database to export.{Style.RESET_ALL}")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            # The standard format seems to be a list of question dicts
            yaml.dump(questions, f, sort_keys=False, indent=2)
        print(f"\n{Fore.GREEN}Successfully exported {len(questions)} questions to:{Style.RESET_ALL}")
        print(str(args.output))
    except IOError as e:
        print(f"{Fore.RED}Error writing to output file {args.output}: {e}{Style.RESET_ALL}")


# --- from: scripts/enrich_unseen_questions.py ---
def handle_enrich_unseen(args):
    """Generate new questions from a source file if they don't exist in the database."""
    if not os.environ.get("OPENAI_API_KEY") and not args.dry_run:
        print("ERROR: OPENAI_API_KEY environment variable not set. Cannot generate questions.", file=sys.stderr)
        sys.exit(1)

    # Load existing prompts to filter out already-imported questions
    conn = None
    try:
        conn = get_db_connection()
        existing_prompts = get_existing_prompts(conn)
        print(f"INFO: Found {len(existing_prompts)} existing questions in the database.")
    except Exception as e:
        print(f"WARNING: Could not connect to database or fetch questions: {e}", file=sys.stderr)
        existing_prompts = set()
    finally:
        if conn:
            conn.close()

    try:
        with open(args.source_file, 'r', encoding='utf-8') as f:
            source_questions = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: Error reading source file {args.source_file}: {e}", file=sys.stderr)
        sys.exit(1)

    unseen_questions = []
    for question in source_questions:
        prompt = question.get('prompt') or question.get('question')
        if prompt and prompt not in existing_prompts:
            unseen_questions.append(question)

    print(f"INFO: Found {len(unseen_questions)} unseen questions in {args.source_file}.")

    if args.dry_run:
        print("INFO: Dry run enabled. Listing unseen question prompts:")
        for i, q in enumerate(unseen_questions[:args.num_questions]):
            print(f"  {i+1}. {q.get('prompt') or q.get('question')}")
        return

    if not unseen_questions:
        print("INFO: No new questions to generate.")
        return

    generator = AIQuestionGenerator()
    generated_questions = []

    questions_to_generate = unseen_questions[:args.num_questions]
    print(f"INFO: Attempting to generate up to {len(questions_to_generate)} new questions...")

    for i, base_question in enumerate(questions_to_generate):
        prompt = base_question.get('prompt') or base_question.get('question')
        print(f"INFO: [{i+1}/{len(questions_to_generate)}] Generating question for prompt: \"{prompt}\"")
        try:
            new_question = generator.generate_question(base_question)
            if new_question:
                generated_questions.append(new_question)
                print("  -> SUCCESS: Successfully generated question.")
            else:
                print("  -> WARNING: Failed to generate question (AI returned empty response).")
        except Exception as e:
            print(f"  -> ERROR: An error occurred during generation: {e}")

    if generated_questions:
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            yaml.dump(generated_questions, f, default_flow_style=False, sort_keys=False)
        print(f"SUCCESS: Successfully generated {len(generated_questions)} new questions and saved them to {args.output_file}")
    else:
        print("WARNING: No questions were generated.")


def handle_import_yaml(args):
    """Import questions from YAML file(s) into the database."""
    db_path = args.db_path or get_live_db_path()
    print(f"Targeting database: {db_path}")

    if args.clear:
        print("Clearing database before import...")
        db_mod.init_db(clear=True, db_path=db_path)

    conn = get_db_connection(db_path=db_path)
    cursor = conn.cursor()
    imported_count = 0

    for file_path in tqdm(args.yaml_files, desc="Importing YAML files"):
        if not file_path.is_file():
            print(f"\nWarning: YAML file not found, skipping: {file_path}")
            continue

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"\nError reading or parsing YAML file {file_path}: {e}")
            continue

        questions_to_import = []
        if isinstance(data, dict) and 'questions' in data:
            questions_to_import = data.get('questions', [])
        elif isinstance(data, list):
            questions_to_import = data

        for q_dict in questions_to_import:
            if not isinstance(q_dict, dict) or not q_dict.get('id') or not q_dict.get('prompt'):
                continue

            # Ensure all fields are present or None
            q_data = {
                'id': q_dict.get('id'),
                'prompt': q_dict.get('prompt'),
                'response': q_dict.get('response'),
                'category': q_dict.get('category'),
                'subject': q_dict.get('subject'),
                'source': q_dict.get('source', 'yaml_import'),
                'source_file': file_path.name,
                'raw': q_dict.get('raw'),
                'validation_steps': json.dumps(q_dict.get('validation_steps')) if q_dict.get('validation_steps') else None,
                'validator': json.dumps(q_dict.get('validator')) if q_dict.get('validator') else None,
                'review': q_dict.get('review', 0)
            }

            try:
                cursor.execute(
                    """INSERT OR REPLACE INTO questions (id, prompt, response, category, subject, source, source_file, raw, validation_steps, validator, review)
                       VALUES (:id, :prompt, :response, :category, :subject, :source, :source_file, :raw, :validation_steps, :validator, :review)""",
                    q_data
                )
                imported_count += 1
            except sqlite3.Error as e:
                print(f"\nFailed to import question {q_dict.get('id')} from {file_path.name}: {e}")

    conn.commit()
    conn.close()
    print(f"\nImport complete. Imported {imported_count} questions.")


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


# --- from: scripts/fix_links.py ---
def check_url(url):
    try:
        resp = requests.head(url, allow_redirects=True, timeout=5)
        return resp.status_code < 400
    except Exception:
        return False

def handle_fix_links(args):
    """Interactively fix broken links in question YAML files."""
    path = Path(args.directory)
    if not path.is_dir():
        print(f'Directory not found: {path}', file=sys.stderr)
        sys.exit(1)
    for file in path.rglob('*.yaml'):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Could not read/parse {file}: {e}", file=sys.stderr)
            continue

        questions = []
        if isinstance(data, dict) and 'questions' in data:
            questions = data.get('questions', [])
        elif isinstance(data, list):
            questions = data
        else:
            continue

        changed = False
        for q in questions:
            if not isinstance(q, dict): continue
            links = q.get('links')
            if not isinstance(links, list):
                continue

            for i, url in enumerate(links):
                if not isinstance(url, str): continue
                if not check_url(url):
                    print(f"Broken URL in {file.name}:{q.get('id', 'N/A')}: {url}")
                    new = input('Enter replacement or leave blank to remove: ').strip()
                    if new:
                        links[i] = new
                    else:
                        links[i] = None
                    changed = True

        if changed:
            # Remove None entries from all questions that might have been modified
            for q_to_clean in questions:
                 if isinstance(q_to_clean, dict) and 'links' in q_to_clean and isinstance(q_to_clean['links'], list):
                    q_to_clean['links'] = [u for u in q_to_clean['links'] if u is not None]

            with open(file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, sort_keys=False, indent=2)
            print(f'Updated links in {file}')


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


# --- from: scripts/generate_ai_questions.py ---
def handle_generate_ai_questions(args):
    """Generate questions using AI and add them to the database."""
    print(f"Generating {args.num_questions} AI questions for subject '{args.subject}'...")
    try:
        generator = AIQuestionGenerator()
    except Exception as e:
        print(f"Failed to initialize AIQuestionGenerator: {e}", file=sys.stderr)
        sys.exit(1)

    new_questions = generator.generate_questions(
        subject=args.subject,
        num_questions=args.num_questions,
        category=args.category,
        base_questions=[]
    )

    if not new_questions:
        print("AI generation returned no questions.")
        return

    print(f"Successfully generated {len(new_questions)} questions. Adding to database...")
    conn = get_db_connection(args.db_path)
    added = 0
    skipped = 0
    cursor = conn.cursor()
    for q_dict in new_questions:
        try:
            q_obj = Question(**q_dict)
            validation_steps_for_db = [step.__dict__ for step in q_obj.validation_steps]
            cursor.execute("""
                INSERT OR REPLACE INTO questions (id, prompt, source_file, response, category, subject, source, raw, validation_steps, validator, review)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                q_obj.id,
                q_obj.prompt,
                q_obj.source_file or 'ai_generated',
                json.dumps(q_obj.response) if q_obj.response is not None else None,
                q_obj.category,
                q_obj.subject.value if q_obj.subject else args.subject,
                'ai_generator',
                json.dumps(q_dict),
                json.dumps(validation_steps_for_db),
                json.dumps(q_obj.validator) if q_obj.validator else None,
                getattr(q_obj, 'review', False)
            ))
            added += 1
        except sqlite3.IntegrityError:
            skipped += 1
        except Exception as e:
            print(f"Failed to add AI-generated question: {e}", file=sys.stderr)
            skipped += 1

    conn.commit()
    conn.close()
    print(f"Added {added} new questions to the database. Skipped {skipped}.")


# --- from: scripts/generate_service_account_questions.py ---
def handle_generate_sa_questions(args):
    """Generate static ServiceAccount questions and optionally add them to DB or file."""
    def _generate_questions():
        """Return a list of question dicts in unified format."""
        questions = []
        # Question 0: Simple ServiceAccount in default namespace
        ans0 = (
            "apiVersion: v1\n"
            "kind: ServiceAccount\n"
            "metadata:\n"
            "  name: sa-reader\n"
            "  namespace: default"
        )
        questions.append({
            "id": "service_accounts::0",
            "prompt": "Create a ServiceAccount named 'sa-reader' in the 'default' namespace.",
            "type": "command",
            "pre_shell_cmds": [],
            "initial_files": {},
            "validation_steps": [
                {"cmd": ans0, "matcher": {"exit_code": 0}}
            ],
            "explanation": None,
            "categories": ["Service Account"],
            "difficulty": None,
            "metadata": {"answer": ans0}
        })
        # Question 1: ServiceAccount in custom namespace
        ans1 = (
            "apiVersion: v1\n"
            "kind: ServiceAccount\n"
            "metadata:\n"
            "  name: sa-deployer\n"
            "  namespace: dev-namespace"
        )
        questions.append({
            "id": "service_accounts::1",
            "prompt": "Create a ServiceAccount named 'sa-deployer' in the 'dev-namespace' namespace.",
            "type": "command",
            "pre_shell_cmds": [],
            "initial_files": {},
            "validation_steps": [
                {"cmd": ans1, "matcher": {"exit_code": 0}}
            ],
            "explanation": None,
            "categories": ["Service Account"],
            "difficulty": None,
            "metadata": {"answer": ans1}
        })
        # Question 2: ServiceAccount with imagePullSecrets
        ans2 = (
            "apiVersion: v1\n"
            "kind: ServiceAccount\n"
            "metadata:\n"
            "  name: sa-db\n"
            "  namespace: prod\n"
            "imagePullSecrets:\n"
            "- name: db-secret"
        )
        questions.append({
            "id": "service_accounts::2",
            "prompt": "Create a ServiceAccount named 'sa-db' in the 'prod' namespace with imagePullSecret 'db-secret'.",  # noqa: E501
            "type": "command",
            "pre_shell_cmds": [],
            "initial_files": {},
            "validation_steps": [
                {"cmd": ans2, "matcher": {"exit_code": 0}}
            ],
            "explanation": None,
            "categories": ["Service Account"],
            "difficulty": None,
            "metadata": {"answer": ans2}
        })
        return questions

    questions = _generate_questions()
    if args.num and args.num > 0:
        questions = questions[:args.num]

    json_out = json.dumps(questions, indent=2)
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(json_out)
            print(f"Wrote {len(questions)} questions to {args.output}")
        except IOError as e:
            print(f"Error writing to {args.output}: {e}", file=sys.stderr)
    
    if not args.output and not args.to_db:
        print(json_out)

    if args.to_db:
        conn = get_db_connection()
        init_db(conn=conn)
        added = 0
        cursor = conn.cursor()
        for q in questions:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO questions (id, prompt, source_file, response, category, source, validation_steps, validator)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    q['id'],
                    q['prompt'],
                    'service_accounts',
                    q['metadata']['answer'],
                    q.get('categories', [None])[0],
                    'script',
                    json.dumps(q.get('validation_steps')),
                    None
                ))
                added += 1
            except Exception as e:
                print(f"Warning: could not add question '{q['id']}' to DB: {e}")
        conn.commit()
        conn.close()
        print(f"Requested to add {len(questions)} questions; successfully added {added} to the kubelingo database.")


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


# --- from: scripts/add_service_account_questions.py ---
def handle_add_service_account_questions(args):
    """Add predefined Service Account questions to the database."""
    # This function's logic is from scripts/add_service_account_questions.py
    # It ensures the user's local database is targeted.
    home_cfg_dir = os.path.expanduser('~/.kubelingo')
    os.makedirs(home_cfg_dir, exist_ok=True)
    cfg.APP_DIR = home_cfg_dir
    cfg.DATABASE_FILE = os.path.join(home_cfg_dir, 'kubelingo.db')
    db_mod.DATABASE_FILE = cfg.DATABASE_FILE

    # Initialize database schema and get connection
    init_db()
    conn = get_db_connection()

    source_file = 'service_account_script'
    category = 'Service Account Operations'

    # Predefined questions
    questions = [
        {
            'id': f'{source_file}::1',
            'prompt': "Create a ServiceAccount named 'deployment-sa' in the 'prod' namespace.",
            'response': 'kubectl create serviceaccount deployment-sa -n prod',
            'validation_steps': [
                {'cmd': 'kubectl get serviceaccount deployment-sa -n prod', 'matcher': {'exit_code': 0}}
            ]
        },
        {
            'id': f'{source_file}::2',
            'prompt': "Create a Pod named 'sa-example' using image nginx and assign it the ServiceAccount 'deployment-sa'.",
            'response': (
                'apiVersion: v1\n'
                'kind: Pod\n'
                'metadata:\n'
                '  name: sa-example\n'
                'spec:\n'
                '  serviceAccountName: deployment-sa\n'
                '  containers:\n'
                '  - name: nginx\n'
                '    image: nginx'
            ),
            'validation_steps': [
                {'cmd': (
                    "kubectl get pod sa-example -o jsonpath='{.spec.serviceAccountName}'"
                ), 'matcher': {'exit_code': 0}}
            ]
        },
        {
            'id': f'{source_file}::3',
            'prompt': "Grant the 'edit' ClusterRole to the ServiceAccount 'deployment-sa' in namespace 'prod'.",
            'response': (
                'kubectl create rolebinding deployment-sa-edit --clusterrole=edit '
                '--serviceaccount=prod:deployment-sa -n prod'
            ),
            'validation_steps': [
                {'cmd': (
                    "kubectl get rolebinding deployment-sa-edit -n prod -o jsonpath='{.subjects[0].name}'"
                ), 'matcher': {'exit_code': 0}}
            ]
        }
    ]

    try:
        cursor = conn.cursor()
        # Add or replace each question in the database
        for q in questions:
            cursor.execute("""
                INSERT OR REPLACE INTO questions (id, prompt, source_file, response, category, source, validation_steps)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                q['id'],
                q['prompt'],
                source_file,
                q.get('response'),
                category,
                'script',
                json.dumps(q.get('validation_steps')),
            ))
            print(f"Added question {q['id']}")

        # Summarize
        cursor.execute("SELECT * FROM questions WHERE source_file = ?", (source_file,))
        entries = cursor.fetchall()
        print(f"Total ServiceAccount questions in DB (source={source_file}): {len(entries)}")
    finally:
        conn.close()


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
        cursor = conn.cursor()
        for q in questions:
            validator = {'type': 'yaml', 'expected': q['correct_yaml']}
            try:
                # Using raw INSERT since add_question is removed
                cursor.execute(
                    """INSERT INTO questions (id, prompt, source_file, category, source, raw, validation_steps, validator)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        q['id'],
                        q['prompt'],
                        source_file,
                        q.get('category'),
                        'script',
                        str(q),
                        json.dumps([]),
                        json.dumps(validator)
                    )
                )
                print(f"Added UI question {q['id']}")
                added += 1
            except Exception as e:
                print(f"Failed to add question {q['id']}: {e}")
        conn.commit()
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
        cursor = conn.cursor()
        for i in range(1, len(parts), 2):
            qnum = parts[i].strip()
            content = parts[i+1].strip()
            lines = content.splitlines()
            if not lines:
                continue
            title = lines[0].strip()
            body = '\n'.join(lines[1:]).strip()
            prompt = f"Simulator Question {qnum}: {title}\n{body}" if body else f"Simulator Question {qnum}: {title}"

            cursor.execute("SELECT COUNT(*) FROM questions WHERE prompt LIKE ?", (f"%Simulator Question {qnum}:%",))
            if cursor.fetchone()[0] > 0:
                print(f"Skipping Question {qnum}, already in DB.")
                continue

            qid = f"sim_pdf::{qnum}"
            try:
                cursor.execute(
                    """INSERT INTO questions (id, prompt, source_file, category, source, raw, validation_steps, validator)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        qid,
                        prompt,
                        'pdf_simulator',
                        'Simulator',
                        'pdf',
                        prompt,
                        json.dumps([]),
                        None
                    )
                )
                print(f"Added Question {qnum} to DB.")
                imported += 1
            except Exception as e:
                print(f"Failed to add Question {qnum}: {e}")
        conn.commit()
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


# --- from: scripts/extract_pdf_questions.py ---
def handle_extract_pdf_ai(args):
    """Generate and insert new questions from PDF content using AI."""
    text = extract_text_from_pdf(args.pdf_path)
    if not text:
        print("No text extracted; aborting.")
        return

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY environment variable not set. Cannot generate questions.", file=sys.stderr)
        sys.exit(1)

    # Truncate text for AI prompt to avoid token limits
    snippet = text[:4000]
    subject = f"Generate {args.num} new, distinct Kubernetes quiz questions based on the following PDF content:\n\n{snippet}"

    generator = AIQuestionGenerator()
    new_questions = generator.generate_questions(subject, num_questions=args.num)

    if not new_questions:
        print("AI generation returned no questions.")
        return

    conn = get_db_connection()
    try:
        existing_prompts = get_existing_prompts(conn)
        added_count = 0
        for q_dict in new_questions:
            q = Question(**q_dict)
            if q.prompt in existing_prompts:
                print(f"Skipping existing question: {q.prompt}")
                continue
            
            # Convert ValidationStep objects to dicts for DB storage
            validation_steps_for_db = [vs.__dict__ for vs in q.validation_steps] if q.validation_steps else []

            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO questions (id, prompt, response, category, source, source_file, validation_steps, validator, review)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                q.id,
                q.prompt,
                q.response,
                "killershell",
                "pdf_ai",
                os.path.basename(args.pdf_path),
                json.dumps(validation_steps_for_db),
                json.dumps(q.validator or {}),
                False
            ))
            added_count += 1
            print(f"Added question {q.id}")
        
        conn.commit()
        print(f"Added {added_count} new questions from PDF content.")
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

    # Sub-parser for 'add-sa-questions'
    parser_add_sa = subparsers.add_parser('add-sa-questions', help='Add predefined Service Account questions to the database.', description="Adds a predefined set of Service Account questions to the user's local database.")
    parser_add_sa.set_defaults(func=handle_add_service_account_questions)

    # Sub-parser for 'add-ui-config'
    parser_add_ui = subparsers.add_parser('add-ui-config', help='Add hardcoded UI configuration questions to the database.', description="Adds a predefined set of UI configuration questions to the user's local database.")
    parser_add_ui.set_defaults(func=handle_add_ui_config)

    # Sub-parser for 'build-db'
    parser_build = subparsers.add_parser('build-db', help='Build the question database from YAML source files.', description="Builds or updates the question database from specified YAML files or all YAML files in the repo.")
    parser_build.add_argument('files', nargs='*', help='Specific YAML files to import. If not provided, all YAML files in the repo are used.')
    parser_build.add_argument('--db-path', default=None, help='Path to the SQLite database file. Defaults to the live application database.')
    parser_build.add_argument('--clear', action='store_true', help='Clear the existing database before importing.')
    parser_build.add_argument('--no-backup', action='store_true', help='Do not backup the database when using --clear.')
    parser_build.set_defaults(func=handle_build_db)

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

    # Sub-parser for 'enrich-sources'
    parser_enrich = subparsers.add_parser('enrich-sources', help="Populate the 'source' field for questions based on their source file.", description="Scans the database for questions without a 'source' and populates it based on the source_file, using the ENABLED_QUIZZES mapping.")
    parser_enrich.set_defaults(func=handle_enrich_sources)

    # Sub-parser for 'enrich-unseen'
    parser_enrich_unseen = subparsers.add_parser('enrich-unseen', help="Generate new questions from a source file for prompts not already in the database.", description="Generate new questions from a source file if they don't exist in the database.")
    parser_enrich_unseen.add_argument("--source-file", type=str, default="/Users/user/Documents/GitHub/kubelingo/question-data/unified.json", help="Path to the JSON file with source questions.")
    parser_enrich_unseen.add_argument("--output-file", type=str, default="question-data/yaml/ai_generated_new_questions.yaml", help="Path to save the newly generated questions in YAML format.")
    parser_enrich_unseen.add_argument("--num-questions", type=int, default=5, help="Maximum number of new questions to generate.")
    parser_enrich_unseen.add_argument("--dry-run", action="store_true", help="Preview unseen questions without generating new ones.")
    parser_enrich_unseen.set_defaults(func=handle_enrich_unseen)

    # Sub-parser for 'export-to-yaml'
    parser_export_yaml = subparsers.add_parser('export-to-yaml', help='Export all questions from database to a single YAML file.', description="Reads all questions from the SQLite database and writes them to a YAML file.")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_export_filename = f'db_export_{timestamp}.yaml'
    default_export_path = Path(project_root) / 'backups' / 'yaml' / default_export_filename
    parser_export_yaml.add_argument('-o', '--output', type=Path, default=default_export_path, help=f'Output file path for the YAML export. Default: {default_export_path}')
    parser_export_yaml.add_argument("--db-path", default=None, help="Path to the SQLite database file. Defaults to the live application database.")
    parser_export_yaml.set_defaults(func=handle_export_to_yaml)

    # Sub-parser for 'import-yaml'
    parser_import_yaml = subparsers.add_parser('import-yaml', help='Import questions from YAML file(s) into the database.')
    parser_import_yaml.add_argument('yaml_files', nargs='+', type=Path, help='Path(s) to YAML file(s) to import.')
    parser_import_yaml.add_argument("--db-path", default=None, help="Path to the SQLite database file. Defaults to the live application database.")
    parser_import_yaml.add_argument('--clear', action='store_true', help='Clear the database before importing.')
    parser_import_yaml.set_defaults(func=handle_import_yaml)

    # Sub-parser for 'fix-categories'
    parser_fix = subparsers.add_parser('fix-categories', help='Interactively fix or assign schema_category for questions.', description="Interactively fix or assign schema_category for questions in the database.")
    parser_fix.add_argument('--list-only', action='store_true', help='Only list questions that need a category, without prompting for changes.')
    parser_fix.set_defaults(func=handle_fix_categories)

    # Sub-parser for 'fix-links'
    parser_fix_links = subparsers.add_parser('fix-links', help='Interactively fix broken documentation links in YAML files.', description="Scan question YAML files for `links` entries and interactively fix broken URLs.")
    parser_fix_links.add_argument('directory', nargs='?', default='question-data/questions', help='Directory of YAML question files to scan.')
    parser_fix_links.set_defaults(func=handle_fix_links)

    # Sub-parser for 'format'
    parser_format = subparsers.add_parser('format', help='Reformat question YAML files for style consistency.', description="Lint and reformat question YAML files for style consistency.")
    parser_format.add_argument('directory', nargs='?', default='question-data/questions', help='Directory of YAML question files to reformat.')
    parser_format.set_defaults(func=handle_format)

    # Sub-parser for 'generate-ai-questions'
    parser_gen_ai = subparsers.add_parser('generate-ai-questions', help='Generate new questions for a subject using AI.', description="Uses AIQuestionGenerator to create new questions for a given subject and adds them to the database.")
    parser_gen_ai.add_argument('subject', help='The subject matter for question generation (e.g., "Service").')
    parser_gen_ai.add_argument('-n', '--num-questions', type=int, default=1, help='Number of questions to generate.')
    parser_gen_ai.add_argument('-c', '--category', default='Command', help='The category for generated questions.')
    parser_gen_ai.add_argument("--db-path", type=str, default=None, help="Path to the SQLite database file. Defaults to the live application database.")
    parser_gen_ai.set_defaults(func=handle_generate_ai_questions)

    # Sub-parser for 'generate-sa-questions'
    parser_gen_sa = subparsers.add_parser('generate-sa-questions', help='Generate static ServiceAccount questions.', description="Generate static ServiceAccount questions and optionally add to kubelingo DB or write to file.")
    parser_gen_sa.add_argument('--to-db', action='store_true', help='Add generated questions to the kubelingo database.')
    parser_gen_sa.add_argument('-n', '--num', type=int, default=0, help='Number of questions to output (default: all).')
    parser_gen_sa.add_argument('-o', '--output', type=str, help='Write generated questions to a JSON file.')
    parser_gen_sa.set_defaults(func=handle_generate_sa_questions)

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

    # Sub-parser for 'import-pdf'
    parser_import_pdf = subparsers.add_parser('import-pdf', help='Import questions from a PDF file.', description="Import new quiz questions from the 'Killer Shell - Exam Simulators.pdf' into the Kubelingo database.")
    default_pdf_path = os.path.join(project_root, 'Killer Shell - Exam Simulators.pdf')
    parser_import_pdf.add_argument('pdf_file', nargs='?', default=default_pdf_path, help=f"Path to the PDF file to import questions from. Default: {default_pdf_path}")
    parser_import_pdf.add_argument('--no-backup', action='store_true', help="Do not back up the database after importing questions.")
    parser_import_pdf.set_defaults(func=handle_import_pdf)

    # Sub-parser for 'extract-pdf-ai'
    parser_extract_pdf = subparsers.add_parser('extract-pdf-ai', help='Extract text from a PDF and generate new quiz questions using AI.', description="Extracts text from a PDF, uses it as context for an AI to generate questions, and adds them to the database, avoiding duplicates.")
    parser_extract_pdf.add_argument("pdf_path", help="Path to the PDF file containing quiz content.")
    parser_extract_pdf.add_argument("-n", "--num", type=int, default=5, help="Number of questions to generate.")
    parser_extract_pdf.set_defaults(func=handle_extract_pdf_ai)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
