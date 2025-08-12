import pytest
from pathlib import Path

import kubelingo.agent.cli as cli_mod


def test_monitor_cmd_no_issues(monkeypatch, capsys):
    """monitor_cmd should report no issues when detect_issues returns no errors."""
    monkeypatch.setattr(
        cli_mod.HealthMonitor,
        'detect_issues',
        lambda self: (False, 'All tests passed.')
    )
    cli_mod.monitor_cmd(repo_path=Path('/dummy'))
    captured = capsys.readouterr()
    assert 'No issues detected. All tests passed.' in captured.out


def test_monitor_cmd_with_issues(monkeypatch, capsys):
    """monitor_cmd should report detected issues and print output."""
    error_text = 'failure details'
    monkeypatch.setattr(
        cli_mod.HealthMonitor,
        'detect_issues',
        lambda self: (True, error_text)
    )
    cli_mod.monitor_cmd(repo_path=Path('/dummy'))
    captured = capsys.readouterr()
    assert 'Issues detected' in captured.out
    assert error_text in captured.out


def test_heal_cmd_no_issues(monkeypatch, capsys):
    """heal_cmd should exit early when there are no issues to heal."""
    monkeypatch.setattr(
        cli_mod.HealthMonitor,
        'detect_issues',
        lambda self: (False, '')
    )
    cli_mod.heal_cmd(repo_path=Path('/dummy'))
    captured = capsys.readouterr()
    assert 'Nothing to heal' in captured.out


@pytest.mark.parametrize('fix_success,conceptual_ok,final_status,final_msg', [
    (True, True, False, 'Success! All tests passed after the fix'),
    (False, True, True, 'Self-healing agent failed to apply a fix'),
    (True, False, True, 'Conceptual integrity validation failed'),
])
def test_heal_cmd_various_flows(monkeypatch, capsys, fix_success, conceptual_ok, final_status, final_msg):
    """heal_cmd should handle branch creation, fix, conceptual validation, and test re-run flows."""
    # Setup detect_issues: first call returns an issue, second depends on flow
    outcomes = iter([(True, 'initial fail'), (not final_status, 'post-fix output')])
    monkeypatch.setattr(
        cli_mod.HealthMonitor,
        'detect_issues',
        lambda self: next(outcomes)
    )
    # Branch creation succeeds
    monkeypatch.setattr(
        cli_mod.GitHealthManager,
        'create_healing_branch',
        lambda self, issue_id: True
    )
    # Stub fix_issue and conceptual validation
    monkeypatch.setattr(
        cli_mod.SelfHealingAgent,
        'fix_issue',
        lambda self, error_context: fix_success
    )
    monkeypatch.setattr(
        cli_mod.ConceptualGuard,
        'validate_changes',
        lambda self, changed_files: conceptual_ok
    )
    # Track rollback calls
    rollback_called = {'count': 0}
    def fake_rollback(self):
        rollback_called['count'] += 1
    monkeypatch.setattr(
        cli_mod.GitHealthManager,
        'rollback_if_failed',
        fake_rollback
    )

    cli_mod.heal_cmd(repo_path=Path('/dummy'))
    captured = capsys.readouterr()
    assert final_msg in captured.out
    # If fix or conceptual fails, rollback should have been called
    if not fix_success or not conceptual_ok or final_status:
        assert rollback_called['count'] >= 1
    else:
        assert rollback_called['count'] == 0


def test_heal_cmd_branch_creation_failure(monkeypatch, capsys):
    """heal_cmd should abort when branch creation fails."""
    monkeypatch.setattr(
        cli_mod.HealthMonitor,
        'detect_issues',
        lambda self: (True, 'init fail')
    )
    monkeypatch.setattr(
        cli_mod.GitHealthManager,
        'create_healing_branch',
        lambda self, issue_id: False
    )
    cli_mod.heal_cmd(repo_path=Path('/dummy'))
    captured = capsys.readouterr()
    assert 'Failed to create healing branch' in captured.out