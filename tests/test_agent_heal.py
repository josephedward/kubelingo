import subprocess
import pytest

from kubelingo.agent.heal import SelfHealingAgent


class DummyCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_fix_issue_success(monkeypatch, tmp_path):
    """SelfHealingAgent.fix_issue returns True when subprocess.run succeeds with returncode 0."""
    # Arrange: stub subprocess.run in heal module to simulate a successful run
    def fake_run(cmd, cwd, capture_output, text, check):
        return DummyCompleted(returncode=0, stdout="Committing...", stderr="")
    monkeypatch.setattr('kubelingo.agent.heal.subprocess.run', fake_run)

    agent = SelfHealingAgent(repo_path=tmp_path)
    result = agent.fix_issue(error_context="dummy error")
    assert result is True


def test_fix_issue_no_aider(monkeypatch, capsys, tmp_path):
    """SelfHealingAgent.fix_issue returns False and logs when subprocess.run raises FileNotFoundError."""
    def fake_run(cmd, cwd, capture_output, text, check):
        raise FileNotFoundError
    monkeypatch.setattr('kubelingo.agent.heal.subprocess.run', fake_run)

    agent = SelfHealingAgent(repo_path=tmp_path)
    result = agent.fix_issue(error_context="dummy error")
    captured = capsys.readouterr()
    assert result is False
    assert "Error: 'aider' not found" in captured.out


def test_fix_issue_subprocess_error(monkeypatch, capsys, tmp_path):
    """SelfHealingAgent.fix_issue returns False and logs when subprocess.run raises CalledProcessError."""
    def fake_run(cmd, cwd, capture_output, text, check):
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd, output="out", stderr="err")
    monkeypatch.setattr('kubelingo.agent.heal.subprocess.run', fake_run)

    agent = SelfHealingAgent(repo_path=tmp_path)
    result = agent.fix_issue(error_context="dummy error")
    captured = capsys.readouterr()
    assert result is False
    assert "Error running aider" in captured.out