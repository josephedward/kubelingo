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
    env['KUBELINGO_DEBUG'] = 'true'
    # Add project root to PYTHONPATH so kubelingo module can be found
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if 'PYTHONPATH' in env:
        env['PYTHONPATH'] = f"{project_root}:{env['PYTHONPATH']}"
    else:
        env['PYTHONPATH'] = project_root
    # Use the same Python interpreter
    cmd = [sys.executable, '-m', 'kubelingo.kubelingo']
    # Create a dummy question file for the test
    questions_dir = tmp_path / "questions"
    questions_dir.mkdir()
    question_content = """
questions:
  - question: "What is Kubernetes?"
    solution: "An open-source container-orchestration system for automating application deployment, scaling, and management."
    source: "https://kubernetes.io/docs/concepts/overview/what-is-kubernetes/"
"""
    (questions_dir / "test_topic.yaml").write_text(question_content)

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
    # Simulate: select topic 1 (test_topic), then 'i' for incomplete questions
    user_input = "1\ni\n"
    try:
        out, err = proc.communicate(input=user_input, timeout=5)
    except subprocess.TimeoutExpired as e:
        # Process did not finish in time; check partial output
        out = e.output or b""
        out = out.decode(errors='ignore')
        assert "Question 1/" in out, (
            f"CLI hung without showing question prompt. Partial output:\n{out}" )
        return
    # Check that the question header is in the output
    assert "Question 1/" in out, f"Expected question prompt, got:\nSTDOUT:\n{out}\nSTDERR:\n{err}"