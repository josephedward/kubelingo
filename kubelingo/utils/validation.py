import re
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


def commands_equivalent(cmd1: str, cmd2: str) -> bool:
    """
    Check if two kubectl commands are functionally equivalent using the Rust implementation.
    This function normalizes whitespace and is case-insensitive.
    """
    if rust_commands_equivalent and RUST_VALIDATOR_ENABLED:
        return rust_commands_equivalent(cmd1, cmd2)

    # This fallback should ideally not be reached if the Rust extension is built correctly.
    # It provides a basic, less robust implementation for environments where the
    # native extension might be missing.
    print("Warning: Rust extension not found or disabled. Falling back to basic Python command comparison.")
    cmd1_norm = ' '.join(cmd1.strip().split()).lower()
    cmd2_norm = ' '.join(cmd2.strip().split()).lower()
    return cmd1_norm == cmd2_norm

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
