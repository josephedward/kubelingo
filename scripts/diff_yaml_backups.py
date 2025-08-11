#!/usr/bin/env python3
"""
Compares YAML backup files to show changes in questions.

Can compare two specified files, or if no files are provided, it discovers all
backups in the configured directories, sorts them by modification date, and
compares each file to its successor.
"""
import argparse
import sys
from pathlib import Path
from typing import List

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from kubelingo.modules.yaml_loader import YAMLLoader
    from kubelingo.question import Question
    from kubelingo.utils.path_utils import find_yaml_files_from_paths
    from kubelingo.utils.config import YAML_BACKUP_DIRS
except ImportError as e:
    print(f"Error: A required kubelingo module is not available: {e}. "
          "Ensure you run this from the project root.", file=sys.stderr)
    sys.exit(1)


def compare_questions(questions1: List[Question], questions2: List[Question]):
    """Compares two lists of Question objects and prints the differences."""
    q1_map = {q.id: q for q in questions1}
    q2_map = {q.id: q for q in questions2}

    added_ids = q2_map.keys() - q1_map.keys()
    removed_ids = q1_map.keys() - q2_map.keys()
    common_ids = q1_map.keys() & q2_map.keys()

    modified_ids = []
    for q_id in common_ids:
        # Simple string comparison is a good proxy for changes in a dataclass
        if str(q1_map[q_id]) != str(q2_map[q_id]):
            modified_ids.append(q_id)

    if added_ids:
        print(f"--- Added ({len(added_ids)}) ---")
        for q_id in sorted(list(added_ids)):
            print(f"  + {q_id}")

    if removed_ids:
        print(f"--- Removed ({len(removed_ids)}) ---")
        for q_id in sorted(list(removed_ids)):
            print(f"  - {q_id}")

    if modified_ids:
        print(f"--- Modified ({len(modified_ids)}) ---")
        for q_id in sorted(modified_ids):
            print(f"  ~ {q_id}")

    if not any([added_ids, removed_ids, modified_ids]):
        print("No changes detected.")

    print("-" * 20)


def main():
    """Main function to diff YAML backup files."""
    parser = argparse.ArgumentParser(
        description="Diff YAML backup files to track changes in questions.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        'files',
        nargs='*',
        help="Two YAML files to compare. If not provided, compares all backups in configured directories chronologically."
    )
    args = parser.parse_args()

    loader = YAMLLoader()

    if len(args.files) == 2:
        path1 = Path(args.files[0])
        path2 = Path(args.files[1])

        if not path1.is_file() or not path2.is_file():
            print("Error: One or both files not found.", file=sys.stderr)
            sys.exit(1)

        print(f"Comparing {path1.name} to {path2.name}...")
        questions1 = loader.load_file(str(path1))
        questions2 = loader.load_file(str(path2))
        compare_questions(questions1, questions2)

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

        print(f"Found {len(sorted_files)} backups. Comparing sequentially...")

        for i in range(len(sorted_files) - 1):
            path1 = sorted_files[i]
            path2 = sorted_files[i + 1]

            print(f"\nComparing {path1.name} -> {path2.name}")
            questions1 = loader.load_file(str(path1))
            questions2 = loader.load_file(str(path2))
            compare_questions(questions1, questions2)

    else:
        parser.error("Please provide either two files to compare, or no files to compare all backups.")


if __name__ == "__main__":
    main()
