#!/usr/bin/env python3
"""
Performs a one-time consolidation of all scattered question source files (JSON,
Markdown, YAML) into a single, organized directory of category-based YAML files,
and archives the original files.
"""
import os
import sys
import json
import shutil
from pathlib import Path
from dataclasses import asdict, fields
from collections import defaultdict
import uuid

# Add project root to path to allow importing kubelingo modules
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# All Question logic is self-contained, so this is safe.
from kubelingo.question import Question

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Please install it using: pip install pyyaml")
    sys.exit(1)


# --- Self-Contained Loaders ---

def load_json_file(path: str) -> list[Question]:
    """Loads questions from a single JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    questions = []
    # Handle both list of questions and section-based format
    if isinstance(data, list):
        items = data
        category = Path(path).stem
    elif isinstance(data, dict) and 'questions' in data:
        items = data.get('questions', [])
        category = data.get('category', Path(path).stem)
    else: # Assuming sections
        items = []
        category = Path(path).stem
        for section in data:
            cat = section.get('category', category)
            for prompt in section.get('prompts', []):
                prompt['category'] = cat
                items.append(prompt)

    for item in items:
        # Ensure a unique ID
        if 'id' not in item or not item['id']:
            item['id'] = str(uuid.uuid4())
        item.setdefault('source_file', Path(path).name)
        # The `type` field is sometimes called `question_type` in old formats.
        if 'question_type' in item and 'type' not in item:
            item['type'] = item.pop('question_type')
        try:
            questions.append(Question(**item))
        except TypeError as e:
            print(f"  - Warning: Skipping question in {Path(path).name} due to invalid field: {e}")
    return questions


def load_md_file(path: str) -> list[Question]:
    """Loads questions from a single Markdown file with YAML frontmatter."""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    parts = content.split('---')
    if len(parts) < 3:
        return []

    frontmatter = yaml.safe_load(parts[1])
    if not frontmatter or not isinstance(frontmatter.get('questions'), list):
        return []

    questions = []
    for item in frontmatter['questions']:
        if 'id' not in item or not item['id']:
            item['id'] = str(uuid.uuid4())
        item.setdefault('source_file', Path(path).name)
        if 'question_type' in item and 'type' not in item:
            item['type'] = item.pop('question_type')
        try:
            questions.append(Question(**item))
        except TypeError as e:
            print(f"  - Warning: Skipping question in {Path(path).name} due to invalid field: {e}")
    return questions


def load_yaml_file(path: str) -> list[Question]:
    """Loads questions from a single YAML file."""
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    if not data:
        return []

    questions = []
    # The YAML files can be a list of questions or a dict with a 'questions' key.
    items = data if isinstance(data, list) else data.get('questions', [])
    
    for item in items:
        if not isinstance(item, dict):
            continue
        if 'id' not in item or not item['id']:
            item['id'] = str(uuid.uuid4())
        item.setdefault('source_file', Path(path).name)
        if 'question_type' in item and 'type' not in item:
            item['type'] = item.pop('question_type')
        try:
            questions.append(Question(**item))
        except TypeError as e:
            print(f"  - Warning: Skipping question in {Path(path).name} due to invalid field: {e}")
            
    return questions


def main():
    """Runs the consolidation process."""
    from kubelingo.utils.config import DATA_DIR
    
    CONSOLIDATED_YAML_DIR = Path(DATA_DIR) / 'questions'
    ARCHIVE_DIR = Path(DATA_DIR).parent / 'question-data-archive'
    
    print("--- Consolidating all question sources into unified YAML files ---")
    print(f"Source directory: {DATA_DIR}")
    print(f"Target directory for new YAML files: {CONSOLIDATED_YAML_DIR}")
    print(f"Archive directory for old files: {ARCHIVE_DIR}")

    # 1. Find all question files
    print("\n[Step 1/5] Finding all question files...")
    all_files = list(Path(DATA_DIR).rglob('*.json')) + \
                list(Path(DATA_DIR).rglob('*.md')) + \
                list(Path(DATA_DIR).rglob('*.yaml')) + \
                list(Path(DATA_DIR).rglob('*.yml'))
    
    # Exclude files in the target directory to allow re-running the script
    all_files = [f for f in all_files if not str(f).startswith(str(CONSOLIDATED_YAML_DIR))]

    if not all_files:
        print("No question files found to process. Exiting.")
        return
    print(f"Found {len(all_files)} potential question files.")

    # 2. Load questions from all sources
    print("\n[Step 2/5] Loading questions from all sources...")
    all_questions = []
    processed_files = set()

    for file_path in all_files:
        try:
            if file_path.suffix == '.json':
                questions = load_json_file(str(file_path))
            elif file_path.suffix == '.md':
                questions = load_md_file(str(file_path))
            elif file_path.suffix in ('.yaml', '.yml'):
                questions = load_yaml_file(str(file_path))
            
            if questions:
                all_questions.extend(questions)
                processed_files.add(file_path)
                print(f"  - Loaded {len(questions)} questions from {file_path.relative_to(DATA_DIR)}")
        except Exception as e:
            print(f"  - Error loading {file_path.relative_to(DATA_DIR)}: {e}")

    # 3. Deduplicate questions
    print("\n[Step 3/5] Deduplicating questions...")
    unique_questions = {q.id: q for q in all_questions}.values()
    print(f"  - Started with {len(all_questions)} questions, {len(unique_questions)} are unique.")

    # 4. Group by category and write to new YAML files
    print(f"\n[Step 4/5] Writing consolidated YAML files to '{CONSOLIDATED_YAML_DIR}'...")
    if not CONSOLIDATED_YAML_DIR.exists():
        CONSOLIDATED_YAML_DIR.mkdir(parents=True)
    
    grouped_by_category = defaultdict(list)
    question_fields = {f.name for f in fields(Question)}

    for q in unique_questions:
        q_dict = asdict(q)
        # Clean up dict to only include valid Question fields and non-empty values
        cleaned_dict = {k: v for k, v in q_dict.items() if k in question_fields and v is not None}
        
        category = "uncategorized"
        # Prefer 'categories' list, then 'category' field
        cats = cleaned_dict.get('categories')
        if cats and isinstance(cats, list) and cats[0]:
            category = cats[0]
        elif cleaned_dict.get('category'):
            category = cleaned_dict['category']
        
        sanitized_category = category.lower().replace(" ", "_").replace("/", "-")
        grouped_by_category[sanitized_category].append(cleaned_dict)

    for category, questions in grouped_by_category.items():
        file_path = CONSOLIDATED_YAML_DIR / f"{category}.yaml"
        print(f"  - Writing {len(questions)} questions to {file_path.relative_to(project_root)}")
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(questions, f, sort_keys=False, default_flow_style=False, indent=2)

    # 5. Archive old source files
    print(f"\n[Step 5/5] Archiving old source files to '{ARCHIVE_DIR}'...")
    ARCHIVE_DIR.mkdir(exist_ok=True)
    
    # Archive question source files
    for file_path in processed_files:
        relative_path = file_path.relative_to(DATA_DIR)
        archive_dest = ARCHIVE_DIR / relative_path
        archive_dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"  - Archiving {relative_path}")
        shutil.move(str(file_path), str(archive_dest))

    # Archive solution script files
    solution_files = list(Path(DATA_DIR).rglob('*.sh'))
    for file_path in solution_files:
        relative_path = file_path.relative_to(DATA_DIR)
        archive_dest = ARCHIVE_DIR / relative_path
        archive_dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"  - Archiving solution {relative_path}")
        shutil.move(str(file_path), str(archive_dest))
        
    # Clean up any empty directories that might be left
    for root, _, _ in os.walk(DATA_DIR, topdown=False):
        if Path(root).exists() and not os.listdir(root) and Path(root) != CONSOLIDATED_YAML_DIR:
            try:
                print(f"  - Removing empty directory: {Path(root).relative_to(project_root)}")
                os.rmdir(root)
            except OSError as e:
                print(f"  - Could not remove directory {root}: {e}")


    print("\n--- Consolidation complete ---")
    print(f"{'='*60}")
    print("Next steps:")
    print("1. Review the new YAML files in 'question-data/questions/'.")
    print("2. Run 'python3 scripts/build_question_db.py' to build the database from these new files.")
    print("3. Once satisfied, you can review the archived files in 'question-data-archive/'.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
