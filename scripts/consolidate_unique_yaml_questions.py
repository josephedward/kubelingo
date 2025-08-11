#!/usr/bin/env python3
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
import yaml
from typing import List, Dict, Any, Set

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from kubelingo.utils.path_utils import get_all_yaml_files_in_repo
from kubelingo.utils.ui import Fore, Style

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


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Consolidate unique YAML questions from across the repository into a single file."
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_filename = f'consolidated_unique_questions_{timestamp}.yaml'
    default_path = Path(project_root) / 'backups' / 'yaml' / default_filename
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=default_path,
        help=f'Output file path for consolidated questions. Default: {default_path}'
    )
    args = parser.parse_args()
    consolidate_unique_yaml_questions(args.output)


if __name__ == '__main__':
    main()
