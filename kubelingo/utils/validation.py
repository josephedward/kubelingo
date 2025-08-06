import re
import shlex
try:
    import yaml
except ImportError:
    yaml = None
from typing import Dict, Any, List, Optional

# Attempt to import high-performance extensions from the Rust library
try:
    from kubelingo._native import commands_equivalent as rust_commands_equivalent
    from kubelingo._native import validate_yaml_structure as rust_validate_yaml_structure
except ImportError:
    rust_commands_equivalent = None
    rust_validate_yaml_structure = None
import os

# Allow disabling Rust-based validation via environment variable
RUST_VALIDATOR_ENABLED = os.getenv("KUBELINGO_DISABLE_RUST", "").lower() not in ("1", "true", "yes")
import subprocess
import shlex


def commands_equivalent(cmd1: str, cmd2: str) -> bool:
    """
    Check if two kubectl commands are functionally equivalent.
    This function normalizes whitespace, handles aliases, is case-insensitive,
    and ignores the order of flags.
    """
    if rust_commands_equivalent and RUST_VALIDATOR_ENABLED:
        return rust_commands_equivalent(cmd1, cmd2)

    # Fallback to a more robust Python-based comparison if the Rust extension is not available.
    print("Warning: Rust extension not found or disabled. Falling back to enhanced Python command comparison.")

    def _normalize_command(cmd_str: str) -> (list, list):
        # 1. Lowercase and remove shell redirection
        cmd_str = cmd_str.lower().split(' > ')[0].strip()

        # 2. Handle common concatenated flags like -oyaml
        cmd_str = re.sub(r'(-o|-n)([a-z0-9-]+)', r'\1 \2', cmd_str)

        # 3. Tokenize using shlex to handle quotes
        try:
            parts = shlex.split(cmd_str)
        except ValueError:
            parts = cmd_str.split()  # Fallback for malformed commands

        # 4. Handle 'k' alias
        if parts and parts[0] == 'k':
            parts[0] = 'kubectl'

        # 5. Separate positional args from flags
        positional_args = []
        flags = []
        i = 0
        while i < len(parts):
            part = parts[i]
            if part.startswith('-'):
                # Handle --flag=value
                if '=' in part:
                    flags.append(part)
                    i += 1
                # Handle --flag value
                elif i + 1 < len(parts) and not parts[i+1].startswith('-'):
                    flags.append(f"{part} {parts[i+1]}")
                    i += 2
                # Handle boolean flag --flag
                else:
                    flags.append(part)
                    i += 1
            else:
                positional_args.append(part)
                i += 1

        flags.sort()
        return positional_args, flags

    cmd1_pos, cmd1_flags = _normalize_command(cmd1)
    cmd2_pos, cmd2_flags = _normalize_command(cmd2)

    return cmd1_pos == cmd2_pos and cmd1_flags == cmd2_flags

def validate_kubectl_syntax(cmd_str: str) -> Dict[str, Any]:
    """
    Validates a kubectl command's syntax without requiring a Kubernetes cluster.
    Attempts to run the command with '--help' and checks for unknown commands or flags.

    Args:
        cmd_str: The kubectl command as a string (e.g., 'kubectl get pods').

    Returns:
        A dict with keys:
        {
            'valid': bool,
            'errors': List[str],   # error messages if invalid
            'warnings': List[str]  # warnings from stderr if any
        }
    """
    parts: List[str]
    try:
        parts = shlex.split(cmd_str)
    except ValueError:
        return {'valid': False, 'errors': ["Failed to parse command string."], 'warnings': []}
    # Handle 'k' alias
    if parts and parts[0] == 'k':
        parts[0] = 'kubectl'
    # Append --help to trigger syntax checking
    help_cmd = parts + ['--help']
    try:
        proc = subprocess.run(help_cmd, capture_output=True, text=True)
    except FileNotFoundError as e:
        return {'valid': False, 'errors': [str(e)], 'warnings': []}
    valid = (proc.returncode == 0)
    errors: List[str] = []
    warnings: List[str] = []
    stderr = (proc.stderr or '').strip()
    stdout = (proc.stdout or '').strip()
    if not valid:
        # Capture stderr or stdout for error details
        if stderr:
            errors.append(stderr)
        elif stdout:
            errors.append(stdout)
        else:
            errors.append(f"Command exited with code {proc.returncode}.")
    else:
        # Treat any stderr output as a warning
        if stderr:
            warnings.append(stderr)
    return {'valid': valid, 'errors': errors, 'warnings': warnings}

def validate_yaml_structure(yaml_content: str) -> Dict[str, Any]:
    """
    Validates YAML syntax and basic Kubernetes structure using the Rust implementation.

    This function checks for syntax errors and the presence of top-level
    'apiVersion', 'kind', and 'metadata' fields.

    Args:
        yaml_content: The YAML content as a string.

    Returns:
        A dictionary with validation results:
        {
            'valid': bool,
            'errors': List[str],
            'warnings': List[str],
            'parsed_yaml': Optional[Any]
        }
    """
    result = {
        'valid': False,
        'errors': [],
        'warnings': [],
        'parsed_yaml': None
    }

    # Use the high-performance Rust validator if available and enabled.
    if rust_validate_yaml_structure and RUST_VALIDATOR_ENABLED:
        is_valid, message = rust_validate_yaml_structure(yaml_content)
        if not is_valid:
            result['errors'].append(message)
        else:
            result['valid'] = True
    else:
        # Fallback to pure Python if the Rust extension is missing.
        warning_msg = "Warning: Rust extension not found. Using Python-based YAML validation."
        result['warnings'].append(warning_msg)
        # Also print a warning to stdout for visibility
        print(warning_msg)
        try:
            parsed = yaml.safe_load(yaml_content)
            if parsed is None:
                result['errors'].append("YAML content is empty or null.")
            elif not isinstance(parsed, dict):
                result['errors'].append("YAML is not a dictionary (mapping).")
            else:
                # Basic Kubernetes resource validation
                required_fields = ['apiVersion', 'kind', 'metadata']
                missing_fields = [field for field in required_fields if field not in parsed]
                if missing_fields:
                    result['errors'].extend([f"Missing required field: {field}" for field in missing_fields])
                else:
                    result['valid'] = True
        except yaml.YAMLError as e:
            result['errors'].append(f"YAML parsing error: {str(e)}")

    # Regardless of the validation method, try to parse and return the object
    # for further use by the caller.
    if yaml:
        try:
            result['parsed_yaml'] = yaml.safe_load(yaml_content)
        except yaml.YAMLError:
            # If parsing fails, parsed_yaml will remain None.
            pass

    return result

def validate_prompt_completeness(cmd_str: str, prompt: str) -> Dict[str, Any]:
    """
    Ensure that the prompt includes the resource type, resource name,
    and any flag values used in the kubectl command.
    Returns a dict with 'valid' bool and 'errors' list.
    """
    try:
        tokens = shlex.split(cmd_str)
    except ValueError:
        return {'valid': False, 'errors': ['Failed to parse command string for prompt validation.']}
    errors: list[str] = []
    prompt_l = prompt.lower()
    # Determine resource name position: skip kubectl, verb, and resource type
    idx = 0
    if tokens and tokens[0].lower() == 'kubectl':
        idx = 1
    if idx < len(tokens):
        idx += 1  # skip verb
    if idx < len(tokens) and not tokens[idx].startswith('-'):
        idx += 1  # skip resource type
    # resource name
    if idx < len(tokens) and not tokens[idx].startswith('-'):
        resource_name = tokens[idx]
        if resource_name.lower() not in prompt_l:
            errors.append(f"Resource name '{resource_name}' missing from prompt")
    # flag values: namespace, filename
    for i, tok in enumerate(tokens):
        # namespace flags
        if tok in ('-n', '--namespace') and i + 1 < len(tokens):
            ns = tokens[i+1]
            if ns.lower() not in prompt_l:
                errors.append(f"Namespace '{ns}' missing from prompt")
        elif tok.startswith('--namespace='):
            ns = tok.split('=', 1)[1]
            if ns.lower() not in prompt_l:
                errors.append(f"Namespace '{ns}' missing from prompt")
        # filename flags
        if tok in ('-f', '--filename') and i + 1 < len(tokens):
            fname = tokens[i+1]
            if fname.lower() not in prompt_l:
                errors.append(f"Filename '{fname}' missing from prompt")
        elif tok.startswith('--filename=') or tok.startswith('-f='):
            parts = tok.split('=', 1)
            if len(parts) == 2 and parts[1].lower() not in prompt_l:
                errors.append(f"Filename '{parts[1]}' missing from prompt")
    return {'valid': not errors, 'errors': errors}


def is_yaml_subset(subset_yaml_str: str, superset_yaml_str: str) -> bool:
    """
    Checks if one YAML object is a structural subset of another.
    It parses both YAML strings and recursively compares them.
    - All keys and values in subset must exist in superset.
    - Lists are handled specially: each item in subset list must find a matching
      item in superset list. For list of dicts, matching is done by checking if
      an item in superset is a superset of an item in subset.
    - It ignores extra keys in superset.
    - It is flexible with types for scalar values (e.g., 5432 vs "5432").
    """
    if not yaml:
        print("Warning: PyYAML not installed, cannot perform YAML subset check.")
        # Fallback to simple string comparison if yaml lib is not available.
        return superset_yaml_str == subset_yaml_str

    try:
        subset = yaml.safe_load(subset_yaml_str)
        superset = yaml.safe_load(superset_yaml_str)
    except yaml.YAMLError:
        return False  # If parsing fails, they can't be equivalent

    def _compare(sub, super_):
        if isinstance(sub, dict):
            if not isinstance(super_, dict):
                return False
            for key, value in sub.items():
                if key not in super_:
                    return False
                if not _compare(value, super_[key]):
                    return False
            return True
        elif isinstance(sub, list):
            if not isinstance(super_, list):
                return False
            
            # Create a copy of the superset list to modify it during iteration
            super_list_copy = list(super_)
            for sub_item in sub:
                found_match = False
                for i, super_item in enumerate(super_list_copy):
                    if _compare(sub_item, super_item):
                        found_match = True
                        super_list_copy.pop(i)  # Remove to handle duplicates correctly
                        break
                if not found_match:
                    return False
            return True
        else:
            # For scalars (int, str, etc.), compare as strings for flexibility
            return str(sub) == str(super_)

    return _compare(subset, superset)
