import subprocess
import sys
import os
import pytest

def test_cli_hangs_before_showing_question(tmp_path):
    """
    Launch the CLI, select a topic with 1 incomplete question, and ensure the question prompt
    appears within a short timeout. If it does not, the test fails quickly.
    """
    # Prepare environment to use local module, not globally installed
    env = os.environ.copy()
    # Use the same Python interpreter
    cmd = [sys.executable, '-m', 'kubelingo.kubelingo']
    # Start the CLI process
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=str(tmp_path),
        text=True
    )
    # Simulate: select topic 2, then 'i' for incomplete questions
    user_input = "2\ni\n"
    try:
        out, err = proc.communicate(input=user_input, timeout=1)
    except subprocess.TimeoutExpired as e:
        # Process did not finish in time; check partial output
        out = e.output or b""
        out = out.decode(errors='ignore')
        assert "Question 1/" in out, (
            f"CLI hung without showing question prompt. Partial output:\n{out}" )
        return
    # Check that the question header is in the output
    assert "Question 1/" in out, f"Expected question prompt, got:\nSTDOUT:\n{out}\nSTDERR:\n{err}"