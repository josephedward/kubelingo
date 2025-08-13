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
    Identifies duplicate YAML files based on the "answers" field.

    Args:
        yaml_data: A dictionary where keys are file paths and values are parsed YAML content.

    Returns:
        A list of lists, where each inner list contains file paths with duplicate answers.
    """
    answer_map = {}
    duplicates = []

    for file_path, content in yaml_data.items():
        if not content:
            continue

        # Extract all "answers" fields from the YAML content
        answers = []
        if isinstance(content, dict) and "answers" in content:
            answers = content["answers"]
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and "answers" in item:
                    answers.extend(item["answers"])

        # Ensure answers is a list
        if not isinstance(answers, list):
            continue

        # Map each answer to the file path
        for answer in answers:
            normalized_answer = str(answer).strip().lower()  # Normalize answers for comparison
            if normalized_answer in answer_map:
                answer_map[normalized_answer].append(file_path)
            else:
                answer_map[normalized_answer] = [file_path]

    # Identify duplicates
    for paths in answer_map.values():
        if len(paths) > 1:
            duplicates.append(paths)

    return duplicates


def validate_yaml_structure(yaml_content: str) -> Dict[str, Any]:
    """
    Validates a Kubernetes YAML manifest, using a high-performance Rust
    validator if available, otherwise falling back to a Python implementation.
    """
    if RUST_VALIDATOR_ENABLED and rust_validate_yaml_structure:
        try:
            is_valid, message = rust_validate_yaml_structure(yaml_content)
            return {"valid": is_valid, "reason": message}
        except Exception:
            # Fall through to Python validator on Rust error
            pass

    if not yaml:
        return {"valid": False, "reason": "PyYAML is not installed."}

    try:
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            return {"valid": False, "reason": "YAML is not a dictionary."}
        
        # Basic Kubernetes structure check
        if not all(k in data for k in ["apiVersion", "kind", "metadata"]):
            return {"valid": False, "reason": "Missing one or more required keys: apiVersion, kind, metadata."}
            
        return {"valid": True, "reason": "YAML is syntactically valid and has basic Kubernetes keys."}
    except yaml.YAMLError as e:
        return {"valid": False, "reason": f"YAML syntax error: {e}"}


def is_yaml_subset(subset_yaml: str, superset_yaml: str) -> bool:
    """
    Checks if one YAML document is a structural subset of another.
    - Dictionaries are checked recursively. All keys in subset must be in superset.
    - Lists are checked for item presence. All items in subset must be in superset.
    - Other values are checked for equality.
    """
    if not yaml:
        return False  # PyYAML not available

    try:
        subset = yaml.safe_load(subset_yaml)
        superset = yaml.safe_load(superset_yaml)
    except (yaml.YAMLError, AttributeError):
        # Handle cases where input is not valid YAML or not loadable
        return False

    def _is_subset_recursive(sub, sup):
        if isinstance(sub, dict) and isinstance(sup, dict):
            return all(
                k in sup and _is_subset_recursive(v, sup[k])
                for k, v in sub.items()
            )
        if isinstance(sub, list) and isinstance(sup, list):
            # For each item in the subset list, we must find a matching item in the superset list.
            return all(
                any(_is_subset_recursive(sub_item, sup_item) for sup_item in sup)
                for sub_item in sub
            )
        # For scalar values (str, int, bool, etc.), check for direct equality.
        return sub == sup

    return _is_subset_recursive(subset, superset)


def validate_prompt_completeness(command: str, prompt: str) -> Dict[str, Any]:
    """
    Validates that a generated kubectl command's key arguments are present
    in the prompt to prevent the AI from inventing details.

    Args:
        command: The kubectl command string.
        prompt: The question prompt string.

    Returns:
        A dictionary with a "valid" boolean and a "reason" string.
    """
    try:
        # A list of common kubectl parts to ignore in the check.
        ignore_tokens = {
            'kubectl', 'get', 'describe', 'create', 'delete', 'apply', 'edit', 'run',
            '-n', '--namespace', '-o', '--output', 'yaml', 'json',
            '--dry-run=client', '--dry-run', 'client'
        }

        # Use shlex to handle quoted arguments correctly.
        tokens = set(shlex.split(command.lower()))
        prompt_lower = prompt.lower()
        
        # Get the tokens that should be present in the prompt.
        check_tokens = tokens - ignore_tokens

        missing_tokens = []
        for token in check_tokens:
            # Simple substring check.
            if token not in prompt_lower:
                missing_tokens.append(token)
        
        if missing_tokens:
            reason = f"The prompt may be incomplete. The following arguments from the command are missing in the prompt: {', '.join(missing_tokens)}."
            return {"valid": False, "reason": reason}
        
        return {"valid": True, "reason": "All key command arguments appear to be in the prompt."}
    except Exception as e:
        # In case of parsing errors, fail open to not block generation.
        return {"valid": True, "reason": f"Validator failed with an error: {e}"}


def validate_prompt_completeness(response: str, prompt: str) -> Dict[str, Any]:
    """
    Validates that a response is complete and relevant to the given prompt.

    Args:
        response: The response to validate.
        prompt: The prompt that the response is supposed to answer.

    Returns:
        A dictionary with validation results, including whether the response is valid.
    """
    if not response or not prompt:
        return {"valid": False, "reason": "Response or prompt is empty."}

    # Check if the response contains at least one word from the prompt
    prompt_words = set(re.findall(r'\w+', prompt.lower()))
    response_words = set(re.findall(r'\w+', response.lower()))

    if not prompt_words.intersection(response_words):
        return {"valid": False, "reason": "Response does not address the prompt."}

    return {"valid": True}
