import os
import sys
import subprocess
import tempfile
import textwrap
import pytest

import pytest
pytest.skip("Skipping CLI answer integration tests", allow_module_level=True)
@pytest.mark.integration
def test_cli_answer_pod_correct(tmp_path, monkeypatch):
    # Prepare a correct kubectl command matching the first question
    manifest = "kubectl run cache-server --image=nginx:1.20"
    # Run the CLI in a subprocess to exercise argparse path
    env = os.environ.copy()
    # Use a temporary working directory
    cwd = tmp_path
    cmd = [sys.executable, '-m', 'kubelingo',
           '--cli-answer', manifest,
           '--cli-question-topic', 'pod',
           '--cli-question-index', '0']
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    # Exit code should be 0
    assert result.returncode == 0, result.stderr
    # Output should contain 'Correct'
    assert 'Correct' in result.stdout

@pytest.mark.integration
def test_cli_answer_pod_incorrect(tmp_path):
    # Prepare an incorrect kubectl command (wrong image)
    manifest = "kubectl run cache-server --image=busybox"
    env = os.environ.copy()
    cmd = [sys.executable, '-m', 'kubelingo',
           '--cli-answer', manifest,
           '--cli-question-topic', 'pod',
           '--cli-question-index', '0']
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert result.returncode == 0
    # Output should indicate incorrect
    assert 'Incorrect' in result.stdout