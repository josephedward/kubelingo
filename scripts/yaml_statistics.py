#!/usr/bin/env python3
"""
Calculates and prints statistics about questions in YAML files.
"""
import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import List

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    import yaml
except ImportError:
    print("Error: PyYAML is not installed. Please run: pip install PyYAML", file=sys.stderr)
    sys.exit(1)

try:
    from kubelingo.question import Question
    from kubelingo.modules.yaml_loader import YAMLLoader
    from kubelingo.utils.path_utils import find_yaml_files
    from kubelingo.utils.config import QUESTION_DIRS
except ImportError as e:
    print(f"Error: A required kubelingo module is not available: {e}. "
          "Ensure you run this from the project root.", file=sys.stderr)
    sys.exit(1)


def main():
    """Calculates and prints statistics about questions in YAML files."""
    parser = argparse.ArgumentParser(description="Get statistics about questions in YAML files.")
    parser.add_argument(
        "path",
        nargs='?',
        default=None,
        help="Path to a YAML file or directory. Defaults to all configured question directories."
    )
    args = parser.parse_args()

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
        for q_type, count in type_counts.most_common():
            print(f"  - {q_type:<20} {count}")
    else:
        print("  No questions with 'type' field found.")

    print("\n--- Questions by Subject Matter (Category) ---")
    if category_counts:
        for category, count in category_counts.most_common():
            print(f"  - {category:<30} {count}")
    else:
        print("  No questions with 'category' field found.")


if __name__ == "__main__":
    main()
