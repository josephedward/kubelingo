#!/usr/bin/env python3
"""
Performs a one-time consolidation of all scattered question source files (JSON,
Markdown, YAML) into a single, organized directory of category-based YAML files.
"""
import os
import sys
from pathlib import Path
from dataclasses import asdict, fields
from collections import defaultdict
import yaml

# Add project root to path to allow importing kubelingo modules
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from kubelingo.modules.json_loader import JSONLoader
from kubelingo.modules.md_loader import MDLoader
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.question import Question
from kubelingo.utils.config import (
    JSON_QUIZ_DIR,
    MD_QUIZ_DIR,
    YAML_QUIZ_DIR,
    MANIFESTS_QUIZ_DIR,
    DATA_DIR,
)

# Define the new consolidated directory
CONSOLIDATED_YAML_DIR = Path(DATA_DIR) / 'questions'

def main():
    """Runs the consolidation process."""
    print("--- Consolidating all question sources into unified YAML files ---")

    loaders = {
        "JSON": (JSONLoader(), Path(JSON_QUIZ_DIR)),
        "Markdown": (MDLoader(), Path(MD_QUIZ_DIR)),
        "YAML": (YAMLLoader(), Path(YAML_QUIZ_DIR)),
        "Manifests": (YAMLLoader(), Path(MANIFESTS_QUIZ_DIR)),
    }

    all_questions = []
    for name, (loader, source_dir) in loaders.items():
        if not source_dir.is_dir():
            print(f"Info: Source directory for {name} not found, skipping: {source_dir}")
            continue

        print(f"\nProcessing {name} questions from '{source_dir}'...")
        if name == "JSON":
            files = list(source_dir.glob("**/*.json"))
        elif name == "Markdown":
            files = list(source_dir.glob("**/*.md"))
        else:  # YAML and Manifests
            files = list(source_dir.glob("**/*.yaml")) + list(source_dir.glob("**/*.yml"))

        if not files:
            print(f"  - No files found in '{source_dir}'.")
            continue

        for file_path in files:
            try:
                questions_from_file = loader.load_file(str(file_path))
                if questions_from_file:
                    all_questions.extend(questions_from_file)
                    print(f"  - Loaded {len(questions_from_file)} questions from {file_path.name}")
            except Exception as e:
                print(f"    - Error loading {file_path.name}: {e}")

    # Deduplicate questions based on their ID
    unique_questions = {q.id: q for q in all_questions}.values()
    print(f"\nTotal unique questions loaded: {len(unique_questions)}")

    # Group questions by category
    grouped_by_category = defaultdict(list)
    question_fields = {f.name for f in fields(Question)}

    for q in unique_questions:
        q_dict = asdict(q)
        # Clean up the dictionary to only include valid Question fields
        cleaned_dict = {k: v for k, v in q_dict.items() if k in question_fields and v}
        
        # Determine category
        category = "uncategorized"
        if cleaned_dict.get('categories'):
            category = cleaned_dict['categories'][0].lower().replace(" ", "_").replace("/", "-")
        elif cleaned_dict.get('metadata', {}).get('category'):
            category = cleaned_dict['metadata']['category'].lower().replace(" ", "_").replace("/", "-")
        
        grouped_by_category[category].append(cleaned_dict)

    # Write to new YAML files
    print(f"\nWriting consolidated YAML files to '{CONSOLIDATED_YAML_DIR}'...")
    os.makedirs(CONSOLIDATED_YAML_DIR, exist_ok=True)

    for category, questions in grouped_by_category.items():
        file_path = CONSOLIDATED_YAML_DIR / f"{category}.yaml"
        print(f"  - Writing {len(questions)} questions to {file_path.name}")
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(questions, f, sort_keys=False, default_flow_style=False, indent=2)

    print("\n--- Consolidation complete ---")
    print(f"{'='*60}")
    print("Next steps:")
    print("1. Review the new YAML files in 'question-data/questions'.")
    print("2. Run 'python3 scripts/build_question_db.py' to build the database from these new files.")
    print("3. Once satisfied, you can delete the old directories: 'json', 'md', 'yaml', 'manifests', and 'solutions'.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
