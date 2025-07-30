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

from kubelingo.modules.kubernetes.session import load_questions

try:
    import openai
except ImportError:
    print("OpenAI Python client is not installed. Please run 'pip install openai'")
    sys.exit(1)

# --- Constants ---
QUESTION_DATA_DIR = project_root / 'question-data'
ARCHIVE_DIR = QUESTION_DATA_DIR / '_archive'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- AI Helper ---

def get_openai_client():
    """Initializes and returns the OpenAI client, checking for the API key."""
    if "OPENAI_API_KEY" not in os.environ:
        logging.warning("OPENAI_API_KEY environment variable not found.")
        return None
    return openai.OpenAI()

def generate_explanation(client, question):
    """Generates a concise explanation for a given question using an AI model."""
    prompt = question.get('prompt', '')
    response = question.get('response', '') or question.get('answer', '')

    if not prompt or not response:
        return None

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a Kubernetes expert who provides concise, one-sentence explanations for `kubectl` commands. The explanation should describe what the command does and why it's useful in a real-world scenario."
                },
                {
                    "role": "user",
                    "content": f"Question: \"{prompt}\"\nCommand: `{response}`\n\nExplanation:"
                }
            ],
            model="gpt-3.5-turbo",
            max_tokens=100,
            temperature=0.3,
        )
        explanation = chat_completion.choices[0].message.content.strip()
        # Clean up the explanation
        explanation = explanation.replace('"', '').strip()
        return explanation
    except openai.APIConnectionError as e:
        logging.error(f"Failed to connect to OpenAI API for prompt '{prompt}'. This is likely a network issue.")
        logging.warning("Please check your internet connection, firewall, or proxy settings.")
        logging.debug(f"Details: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred generating explanation for prompt '{prompt}': {e}")
        return None

def generate_validation_steps(client, question):
    """Generates validation steps for a given question using an AI model."""
    prompt = question.get('prompt', '')
    response = question.get('response', '') or question.get('answer', '')

    if not prompt or not response:
        return None

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": """You are a Kubernetes expert that generates validation steps for exercises.
Given a question prompt and the correct command, generate a JSON object containing a 'validation_steps' key with a JSON array of validation steps.
Each step must be a `kubectl` command using `jsonpath` to verify a key attribute of the created resource.
The output MUST be only a valid JSON object.
Example for a question about creating a deployment with 1 replica:
{"validation_steps": [{"cmd": "kubectl get deployment my-deployment -o jsonpath='{.spec.replicas}'", "matcher": {"value": 1}}]}"""
                },
                {
                    "role": "user",
                    "content": f"Question: \"{prompt}\"\nCorrect Command: `{response}`\n\nJSON validation_steps object:"
                }
            ],
            model="gpt-4-turbo",
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        steps_json = chat_completion.choices[0].message.content.strip()
        try:
            data = json.loads(steps_json)
            steps = data.get("validation_steps")
            
            if not isinstance(steps, list):
                logging.warning(f"AI did not return a list for validation steps for prompt: {prompt}")
                return None
            for step in steps:
                if not all(k in step for k in ['cmd', 'matcher']):
                    logging.warning(f"Invalid step structure in validation steps for prompt: {prompt}")
                    return None # Invalid structure
            return steps
        except (json.JSONDecodeError, AttributeError) as e:
            logging.warning(f"Failed to decode or parse validation steps JSON for prompt '{prompt}': {e}")
            logging.debug(f"Received from AI: {steps_json}")
            return None
    except openai.APIConnectionError as e:
        logging.error(f"Failed to connect to OpenAI API for prompt '{prompt}'. This is likely a network issue.")
        logging.warning("Please check your internet connection, firewall, or proxy settings.")
        logging.debug(f"Details: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred generating validation steps for prompt '{prompt}': {e}")
        return None

def _process_question(question, client, explained_prompts, dry_run, do_dedupe, do_explanations, do_validations):
    """
    Processes a single question for de-duplication and enrichment.
    Returns a tuple: (processed_question | None, was_deduplicated, explanation_added, steps_added)
    """
    prompt_text = question.get('prompt', '').strip()
    was_deduplicated = False
    explanation_added = False
    steps_added = False

    if do_dedupe and prompt_text in explained_prompts:
        was_deduplicated = True
        logging.info(f"De-duplicating question (already has explanation): \"{prompt_text[:50]}...\"")
        return None, was_deduplicated, explanation_added, steps_added

    if do_explanations and not question.get('explanation'):
        logging.info(f"Generating explanation for: \"{prompt_text[:50]}...\"")
        if not dry_run:
            explanation = generate_explanation(client, question)
            if explanation:
                question['explanation'] = explanation
                explanation_added = True
        else:
            explanation_added = True

    if do_validations and not question.get('validation_steps'):
        logging.info(f"Generating validation steps for: \"{prompt_text[:50]}...\"")
        if not dry_run:
            steps = generate_validation_steps(client, question)
            if steps:
                question['validation_steps'] = steps
                steps_added = True
        else:
            steps_added = True

    return question, was_deduplicated, explanation_added, steps_added

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

def enrich_and_deduplicate(target_file_path, ref_file_path, dry_run=False, do_dedupe=True, do_explanations=True, do_validations=True):
    """Enriches questions with AI explanations and de-duplicates them."""
    logging.info("--- Starting question enrichment and de-duplication ---")

    client = get_openai_client()
    if not client and (do_explanations or do_validations):
        logging.warning("Skipping enrichment as OpenAI client is not available.")
        return

    if not target_file_path.exists():
        logging.error(f"Target file not found: '{target_file_path}'.")
        return

    explained_prompts = set()
    if do_dedupe:
        if ref_file_path and ref_file_path.exists():
            ref_questions = load_questions(str(ref_file_path))
            explained_prompts = {q.get('prompt', '').strip() for q in ref_questions if q.get('explanation')}
            logging.info(f"Loaded {len(explained_prompts)} prompts with existing explanations from '{ref_file_path.name}'")
        else:
            logging.warning(f"Reference file '{ref_file_path}' not found. Skipping de-duplication.")

    with open(target_file_path, 'r', encoding='utf-8') as f:
        target_data_raw = json.load(f)

    is_nested = isinstance(target_data_raw, list) and target_data_raw and isinstance(target_data_raw[0], dict) and 'prompts' in target_data_raw[0]

    enriched_explanation_count = 0
    enriched_steps_count = 0
    deduplicated_count = 0

    process_args = (client, explained_prompts, dry_run, do_dedupe, do_explanations, do_validations)

    if is_nested:
        final_data = []
        for category_group in target_data_raw:
            prompts_to_keep = []
            for question in category_group.get('prompts', []):
                processed_q, was_deduped, exp_added, steps_added = _process_question(question, *process_args)
                if was_deduped:
                    deduplicated_count += 1
                    continue
                if exp_added:
                    enriched_explanation_count += 1
                if steps_added:
                    enriched_steps_count += 1
                if processed_q:
                    prompts_to_keep.append(processed_q)
            
            if prompts_to_keep:
                category_group['prompts'] = prompts_to_keep
                final_data.append(category_group)
    else:  # Flat structure
        final_data = []
        for question in target_data_raw:
            processed_q, was_deduped, exp_added, steps_added = _process_question(question, *process_args)
            if was_deduped:
                deduplicated_count += 1
                continue
            if exp_added:
                enriched_explanation_count += 1
            if steps_added:
                enriched_steps_count += 1
            if processed_q:
                final_data.append(processed_q)

    if do_explanations:
        logging.info(f"Enriched {enriched_explanation_count} questions with new explanations.")
    if do_validations:
        logging.info(f"Enriched {enriched_steps_count} questions with new validation steps.")
    if do_dedupe:
        logging.info(f"Removed {deduplicated_count} duplicate questions.")

    if not dry_run:
        with open(target_file_path, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2)
        logging.info(f"Successfully updated '{target_file_path}'")

    logging.info("--- Question enrichment and de-duplication complete ---")

def main():
    parser = argparse.ArgumentParser(description="Organize and enrich Kubelingo question data.")
    parser.add_argument('--dry-run', action='store_true', help="Show what would be done, but don't make changes.")
    parser.add_argument('--organize-only', action='store_true', help="Only perform file organization.")
    parser.add_argument('--enrich-only', action='store_true', help="Only perform AI enrichment and de-duplication.")
    parser.add_argument('--generate-validations', action='store_true', help="Only generate validation steps for questions, skipping all other operations.")
    parser.add_argument('--enrich-file', type=Path, help="Path to a specific JSON question file to enrich.")
    parser.add_argument('--dedupe-ref-file', type=Path, help="Reference file with explanations for de-duplication.")
    args = parser.parse_args()

    if args.generate_validations:
        logging.info("--- Running in validation generation only mode. ---")
        json_dir = QUESTION_DATA_DIR / "json"
        target_file = args.enrich_file if args.enrich_file else json_dir / "kubernetes.json"
        ref_file = args.dedupe_ref_file if args.dedupe_ref_file else json_dir / "kubernetes_with_explanations.json"

        enrich_and_deduplicate(
            target_file,
            ref_file,
            dry_run=args.dry_run,
            do_dedupe=False,
            do_explanations=False,
            do_validations=True
        )
        return

    run_organize = not args.enrich_only
    run_enrich = not args.organize_only

    if run_organize:
        organize_files(dry_run=args.dry_run)

    if run_enrich:
        json_dir = QUESTION_DATA_DIR / "json"
        target_file = args.enrich_file if args.enrich_file else json_dir / "kubernetes.json"
        ref_file = args.dedupe_ref_file if args.dedupe_ref_file else json_dir / "kubernetes_with_explanations.json"

        enrich_and_deduplicate(target_file, ref_file, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
