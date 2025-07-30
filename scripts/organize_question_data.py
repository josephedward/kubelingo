import os
import shutil
import argparse
import json
import logging
from pathlib import Path
import sys
import re

# Determine project root directory and ensure local modules are importable
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Load shared context from project root
try:
    with open(project_root / 'shared_context.md', 'r', encoding='utf-8') as f:
        SHARED_CONTEXT = f.read()
except FileNotFoundError:
    logging.warning("shared_context.md not found. AI prompts will be less detailed.")
    SHARED_CONTEXT = ""

try:
    import openai
except ImportError:
    openai = None
    logging.warning("OpenAI library not found. AI features will be disabled. Run 'pip install openai'")


# --- Constants ---
QUESTION_DATA_DIR = project_root / 'question-data'
# Default file for enrichment if not specified
DEFAULT_ENRICH_FILE = QUESTION_DATA_DIR / 'json' / 'kubernetes.json'
ARCHIVE_DIR = QUESTION_DATA_DIR / '_archive'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

# --- AI Enrichment ---

def _get_openai_client():
    """Returns an OpenAI client if the key is available, otherwise None."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not openai:
        logging.error("OpenAI library not installed. Cannot perform AI enrichment.")
        return None
    if not api_key:
        logging.error("OPENAI_API_KEY environment variable not set. Cannot perform AI enrichment.")
        return None
    try:
        return openai.OpenAI(api_key=api_key)
    except Exception as e:
        logging.error(f"Failed to initialize OpenAI client: {e}")
        return None

def generate_validation_steps(question, model="gpt-4-turbo", dry_run=False):
    """Generates validation steps for a question using an AI model."""
    client = _get_openai_client()
    if not client:
        return None

    # Extract prompt and answer from the question dict
    prompt = question.get('prompt')
    # Top-level 'response' or 'answer' fields
    answer = question.get('response') or question.get('answer')

    if not prompt or not answer:
        logging.warning(
            f"Skipping validation generation for question without prompt or answer: id={question.get('id', 'N/A')}, prompt={prompt}"
        )
        return None

    system_prompt = (
        SHARED_CONTEXT +
        "\n\nYou are a Kubernetes expert that generates validation steps for exercises.\n"
        "Given a question prompt and the correct command, generate a JSON object containing a 'validation_steps' key with a JSON array of validation steps.\n"
        "Each step must be a `kubectl` command using `jsonpath` to verify a key attribute of the created resource.\n"
        "Generate up to 5 steps.\n"
        "The output MUST be only a valid JSON object.\n"
        "Example for a question about creating a deployment with 1 replica:\n"
        '''{"validation_steps": [{"cmd": "kubectl get deployment my-deployment -o jsonpath='{.spec.replicas}'", "matcher": {"value": "1"}}]}'''
    )

    user_prompt = f"Question: {prompt}\nAnswer: {answer}"

    logging.info(f"Generating validation steps for prompt: {prompt[:80]}...")
    if dry_run:
        logging.info("[DRY RUN] Would call OpenAI API to generate validation steps.")
        # Return a dummy structure for dry-run
        return [{"cmd": "kubectl get something...", "matcher": {"contains": "some value"}}]

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        response_content = completion.choices[0].message.content
        data = json.loads(response_content)
        steps = data.get('validation_steps')
        if not isinstance(steps, list):
            logging.error(f"AI returned invalid format for validation_steps: {steps}")
            return None
        return steps
    except Exception as e:
        logging.error(f"Error calling OpenAI API for prompt '{prompt[:80]}...': {e}")
        if "Connection" in str(e):
             logging.error("This may be a network issue. Please check your connection to api.openai.com.")
        return None

def enrich_and_dedupe(
    target_file,
    dedupe_ref_file=None,
    generate_validations=False,
    model="gpt-4-turbo",
    dry_run=False
):
    """Enriches a question file with AI-generated content and de-duplicates it."""
    logging.info("--- Starting enrichment and de-duplication ---")

    target_path = Path(target_file)
    if not target_path.exists():
        logging.error(f"Target file not found: {target_file}")
        return

    # Load target questions
    try:
        with open(target_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
             logging.error(f"Target file {target_file} does not contain a JSON list.")
             return
    except json.JSONDecodeError:
        logging.error(f"Failed to decode JSON from {target_file}")
        return

    # The data can be a flat list of questions, or a list of categories with nested questions.
    is_nested = isinstance(data[0], dict) and 'questions' in data[0] if data else False

    questions_to_update = []
    if generate_validations:
        logging.info("Scanning for questions missing 'validation_steps'...")
        
        question_source = []
        if is_nested:
            for category in data:
                question_source.extend(category.get('questions', []))
        else: # flat list
            question_source = data

        for q in question_source:
            if not q.get('validation_steps'):
                questions_to_update.append(q)

    if not questions_to_update and generate_validations:
        logging.info("No questions need validation steps.")
        return
    elif questions_to_update:
        logging.info(f"Found {len(questions_to_update)} questions to enrich with validation steps.")
        if dry_run:
            for q in questions_to_update:
                logging.info(f"[DRY RUN] Would generate validations for prompt: {q.get('prompt')}")

    updated_count = 0
    if not dry_run and questions_to_update:
        for q in questions_to_update:
            new_steps = generate_validation_steps(q, model=model, dry_run=dry_run)
            if new_steps:
                q['validation_steps'] = new_steps
                updated_count += 1
                logging.info(f"Successfully generated validation steps for: {q.get('prompt')[:80]}...")

    if updated_count > 0 and not dry_run:
        logging.info(f"Writing {updated_count} updated questions back to '{target_file}'")
        try:
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to write updates to {target_file}: {e}")

    logging.info("--- Enrichment complete ---")


def main():
    parser = argparse.ArgumentParser(
        description="Organize and enrich Kubelingo question data files.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    # Control flags
    parser.add_argument('--dry-run', action='store_true',
                        help="Show what would be done, but don't make any changes.")
    parser.add_argument('--organize-only', action='store_true',
                        help="Run only file organization tasks.")
    parser.add_argument('--enrich-only', action='store_true',
                        help="Run only enrichment and de-duplication tasks.")

    # Enrichment flags
    parser.add_argument('--enrich-file', type=str,
                        help=f"Path to the question file to enrich.\nDefault: {DEFAULT_ENRICH_FILE}")
    parser.add_argument('--dedupe-ref-file', type=str,
                        help="Path to a reference file for de-duplication.")
    parser.add_argument('--generate-validations', action='store_true',
                        help="Generate AI-scaffolded validation_steps for questions missing them.")
    parser.add_argument('--model', type=str, default='gpt-4-turbo',
                        help="AI model to use for generating content (e.g., 'gpt-4-turbo').")

    args = parser.parse_args()

    # Determine what to run. Default is to run both unless specific flags are used.
    run_organize = not args.enrich_only
    run_enrich = args.enrich_only or args.generate_validations or args.enrich_file

    if args.organize_only:
        run_enrich = False

    if args.organize_only and args.enrich_only:
        parser.error("--organize-only and --enrich-only are mutually exclusive.")

    if run_organize:
        organize_files(dry_run=args.dry_run)

    if run_enrich:
        target_file = args.enrich_file or str(DEFAULT_ENRICH_FILE)
        enrich_and_dedupe(
            target_file=target_file,
            dedupe_ref_file=args.dedupe_ref_file,
            generate_validations=args.generate_validations,
            model=args.model,
            dry_run=args.dry_run
        )


if __name__ == "__main__":
    main()
