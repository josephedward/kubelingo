import shlex

try:
    import yaml
except ImportError:
    yaml = None

# These are now implemented in Rust and imported from the compiled extension.
from kubelingo_core import commands_equivalent, validate_yaml_structure
