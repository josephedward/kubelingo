import re
import shlex
try:
    import yaml
except ImportError:
    yaml = None
from typing import Dict, Any, List, Optional
import os
from pathlib import Path

# Attempt to import high-performance extensions from the Rust library
try:
    from kubelingo._native import commands_equivalent as rust_commands_equivalent
    from kubelingo._native import validate_yaml_structure as rust_validate_yaml_structure
except ImportError:
    rust_commands_equivalent = None
    rust_validate_yaml_structure = None

# Allow disabling Rust-based validation via environment variable
RUST_VALIDATOR_ENABLED = os.getenv("KUBELINGO_DISABLE_RUST", "").lower() not in ("1", "true", "yes")


def find_duplicate_answers(yaml_data: Dict[str, Any]) -> List[List[str]]:
    """
    Identifies duplicate YAML files based on the "answer" field.

    Args:
        yaml_data: A dictionary where keys are file paths and values are parsed YAML content.

    Returns:
        A list of lists, where each inner list contains file paths with duplicate answers.
    """
    answer_map = {}
    duplicates = []

    for file_path, content in yaml_data.items():
        if not content or "answer" not in content:
            continue
        answer = content["answer"]
        if answer in answer_map:
            answer_map[answer].append(file_path)
        else:
            answer_map[answer] = [file_path]

    for paths in answer_map.values():
        if len(paths) > 1:
            duplicates.append(paths)

    return duplicates
