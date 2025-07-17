import shlex

try:
    import yaml
except ImportError:
    yaml = None

try:
    # Attempt to import the fast Rust implementation
    from kubelingo._native import commands_equivalent, validate_yaml_structure
    RUST_CORE_AVAILABLE = True
except ImportError:
    RUST_CORE_AVAILABLE = False

    def _normalize_command(cmd_str):
        """(Python) Parse and normalize a kubectl command into canonical tokens."""
        # This is a simplified fallback implementation.
        tokens = shlex.split(cmd_str)
        return " ".join(tokens).lower()

    def commands_equivalent(user_cmd, expected_cmd):
        # Fallback Python implementation
        return _normalize_command(user_cmd) == _normalize_command(expected_cmd)

    def validate_yaml_structure(yaml_content_str):
        # Fallback Python implementation
        try:
            if yaml is None:
                return False, "PyYAML not installed"
            parsed = yaml.safe_load(yaml_content_str)

            if not parsed:
                return False, "Empty YAML content"
            if not isinstance(parsed, dict):
                return False, "YAML is not a dictionary"

            required = ["apiVersion", "kind", "metadata"]
            missing = [f for f in required if f not in parsed]
            if missing:
                return False, f"Missing required fields: {', '.join(missing)}"
            return True, "YAML is valid"
        except Exception as e:
            return False, str(e)
