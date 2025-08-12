import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = ROOT / 'scripts' / 'generator.py'

SUBCOMMANDS = [
    'from-pdf',
    'ai-quiz',
    'resource-reference',
    'kubectl-operations',
    'ai-questions',
    'validation-steps',
    'service-account',
    'manifests',
]


def run_generator(*args):
    """Helper to run the generator script and capture output."""
    cmd = [sys.executable, str(SCRIPT_PATH)] + list(args)
    # Use text=True for Python 3.7+
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result


def test_script_exists_and_is_executable():
    """Test that the script exists and has execute permissions."""
    assert SCRIPT_PATH.exists(), f"Script not found at {SCRIPT_PATH}"
    # In a git repo on macOS/Linux, +x bit should be set.
    # On Windows, this check is not as relevant.
    if sys.platform != 'win32':
        assert SCRIPT_PATH.stat().st_mode & 0o111, "Script is not executable"


def test_generator_help():
    """Test that the script runs with --help and shows top-level usage."""
    result = run_generator('--help')
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert 'usage: generator.py' in result.stdout
    for subcommand in SUBCOMMANDS:
        assert subcommand in result.stdout


def test_generator_subcommand_help():
    """Test that each subcommand runs with --help and shows its own usage."""
    for subcommand in SUBCOMMANDS:
        # Some subcommands have required arguments, so just checking for the usage string is better.
        result = run_generator(subcommand, '--help')
        assert result.returncode == 0, f"Subcommand '{subcommand}' failed with --help. Stderr: {result.stderr}"
        assert f"usage: generator.py {subcommand}" in result.stdout, f"Subcommand '{subcommand}' --help output is incorrect."
