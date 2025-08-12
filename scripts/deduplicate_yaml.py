#!/usr/bin/env python
"""
Scans a directory for YAML question files, deduplicates the questions based on
their content, and writes the unique questions to a single output file.
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict

import yaml

from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.question import Question


def question_to_key(q: Question) -> str:
    """
    Creates a canonical, hashable key from a Question object for deduplication.
    It serializes the question content to a JSON string, ignoring metadata
    fields that do not affect content uniqueness.
    """
    d = asdict(q)
    # Exclude fields that vary between identical questions from different sources
    d.pop('id', None)
    d.pop('source_file', None)

    # Clean up None values to ensure consistent serialization
    cleaned_dict = {k: v for k, v in d.items() if v is not None}

    # The `default=str` is a fallback for any non-serializable types, like Enums
    return json.dumps(cleaned_dict, sort_keys=True, default=str)


def main():
    """
    Main function to parse arguments and run the deduplication process.
    """
    parser = argparse.ArgumentParser(
        description="Deduplicate YAML questions in a directory and consolidate them."
    )
    parser.add_argument(
        "directory",
        type=str,
        help="Directory containing YAML question files to process."
    )
    parser.add_argument(
        "--output-file",
        "-o",
        type=str,
        help="Output file for consolidated unique questions. "
             "Defaults to 'unique_questions.yaml' in the source directory."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run to see statistics without writing any files."
    )

    args = parser.parse_args()
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
                key = question_to_key(q)
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

    # Prepare data for YAML output, converting Question objects back to dicts.
    questions_for_yaml = [asdict(q) for q in unique_questions.values()]

    # Clean up None values for a tidier YAML output file.
    cleaned_questions_for_yaml = []
    for q_dict in questions_for_yaml:
        cleaned_questions_for_yaml.append(
            {k: v for k, v in q_dict.items() if v is not None}
        )

    output_data = {"questions": cleaned_questions_for_yaml}

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(output_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        print(f"\nSuccessfully wrote {len(unique_questions)} unique questions to '{output_file}'.")
    except IOError as e:
        print(f"\nError writing to output file '{output_file}': {e}")
        exit(1)


if __name__ == "__main__":
    main()
