import os
import subprocess
import tempfile
import shlex
import difflib

from kubelingo.utils.validation import validate_yaml_structure
from kubelingo.utils.ui import Fore, Style, yaml


class VimYamlEditor:
    """
    Provides functionality to create, edit, and validate Kubernetes YAML manifests
    interactively using Vim.
    """
    pass
