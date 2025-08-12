import subprocess
import pytest

from kubelingo.agent.monitor import HealthMonitor


class DummyCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_detect_issues_all_pass(monkeypatch, tmp_path):
    """HealthMonitor.detect_issues should report no issues when pytest returns 0."""
    # Arrange: stub subprocess.run to simulate passing tests
    def fake_run(cmd, cwd, capture_output, text, check):
        return DummyCompleted(returncode=0, stdout="tests passed", stderr="")
    monkeypatch.setattr(subprocess, 'run', fake_run)

    monitor = HealthMonitor(repo_path=tmp_path)
    has_issues, output = monitor.detect_issues()

    # Assert: no issues, output message
    assert has_issues is False
    assert "All tests passed" in output or "tests passed" in output


def test_detect_issues_with_failures(monkeypatch, tmp_path):
    """HealthMonitor.detect_issues should report issues and include stdout/stderr when returncode != 0."""
    # Arrange: stub subprocess.run to simulate failing tests
    def fake_run(cmd, cwd, capture_output, text, check):
        return DummyCompleted(returncode=1, stdout="out error", stderr="err info")
    monkeypatch.setattr(subprocess, 'run', fake_run)

    monitor = HealthMonitor(repo_path=tmp_path)
    has_issues, output = monitor.detect_issues()

    # Assert: issues detected and output contains both stdout and stderr
    assert has_issues is True
    assert "stdout:" in output
    assert "stderr:" in output
    assert "out error" in output
    assert "err info" in output


def test_detect_issues_pytest_missing(monkeypatch, tmp_path):
    """HealthMonitor.detect_issues should report error when pytest is not installed."""
    def fake_run(cmd, cwd, capture_output, text, check):
        raise FileNotFoundError
    monkeypatch.setattr(subprocess, 'run', fake_run)

    monitor = HealthMonitor(repo_path=tmp_path)
    has_issues, output = monitor.detect_issues()

    assert has_issues is True
    assert "pytest not found" in output


def test_detect_issues_unexpected_error(monkeypatch, tmp_path):
    """HealthMonitor.detect_issues should catch unexpected exceptions and report them."""
    def fake_run(cmd, cwd, capture_output, text, check):
        raise RuntimeError("boom")
    monkeypatch.setattr(subprocess, 'run', fake_run)

    monitor = HealthMonitor(repo_path=tmp_path)
    has_issues, output = monitor.detect_issues()

    assert has_issues is True
    assert "Unexpected error" in output