import subprocess
import sys
from pathlib import Path
import pytest
import json
import yaml

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


def run_generator(*args, cwd=None):
    """Helper to run the generator script and capture output."""
    cmd = [sys.executable, str(SCRIPT_PATH)] + list(args)
    # Use text=True for Python 3.7+
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=cwd)
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


@pytest.mark.skipif(not yaml, reason="PyYAML is not installed")
def test_generator_resource_reference(tmp_path: Path):
    """Test the 'resource-reference' subcommand."""
    result = run_generator('resource-reference', cwd=tmp_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    output_file = tmp_path / 'question-data/yaml/manifests/resource_reference.yaml'
    assert output_file.exists()

    data = yaml.safe_load(output_file.read_text())
    assert isinstance(data, list)
    assert len(data) > 50  # there are many resources

    content = output_file.read_text()
    assert 'id: pod::shortnames' in content
    assert 'response: "po"' in content
    assert 'id: service::apiversion' in content
    assert 'response: "v1"' in content


@pytest.mark.skipif(not yaml, reason="PyYAML is not installed")
def test_generator_kubectl_operations(tmp_path: Path):
    """Test the 'kubectl-operations' subcommand."""
    result = run_generator('kubectl-operations', cwd=tmp_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    output_file = tmp_path / 'question-data/yaml/kubectl_operations.yaml'
    assert output_file.exists()

    data = yaml.safe_load(output_file.read_text())
    assert isinstance(data, list)
    assert len(data) > 20

    content = output_file.read_text()
    assert 'id: kubectl::apply' in content
    assert 'question: "Apply or Update a resource from a file or stdin."' in content
    assert 'response: "apply"' in content


@pytest.mark.skipif(not yaml, reason="PyYAML is not installed")
def test_generator_manifests(tmp_path: Path):
    """Test the 'manifests' subcommand."""
    # Setup source file
    json_dir = tmp_path / 'question-data' / 'json'
    json_dir.mkdir(parents=True)

    sample_question = [{
        "prompt": "Create a pod.",
        "answer": "apiVersion: v1\nkind: Pod\nmetadata:\n  name: mypod"
    }]

    json_file = json_dir / "sample.json"
    json_file.write_text(json.dumps(sample_question))

    result = run_generator('manifests', cwd=tmp_path)
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"

    manifest_file = tmp_path / 'question-data' / 'yaml' / 'manifests' / 'sample.yaml'
    solution_file = tmp_path / 'question-data' / 'yaml' / 'solutions' / 'sample' / '0.yaml'

    assert manifest_file.exists()
    assert solution_file.exists()

    manifest_data = yaml.safe_load(manifest_file.read_text())
    assert len(manifest_data) == 1
    assert manifest_data[0]['id'] == 'sample::0'
    assert manifest_data[0]['question'] == 'Create a pod.'

    solution_content = solution_file.read_text()
    assert solution_content.strip() == sample_question[0]['answer']
