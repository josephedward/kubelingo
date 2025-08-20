#!/usr/bin/env python3
"""
Agent CLI for Kubelingo self-healing operations.
"""
import argparse
from pathlib import Path
from datetime import datetime

from kubelingo.agent.monitor import HealthMonitor
from kubelingo.agent.heal import SelfHealingAgent
from kubelingo.agent.git_manager import GitHealthManager
from kubelingo.agent.conceptual_guard import ConceptualGuard
from kubelingo.self_healing import CKAD_CONCEPTUAL_GOALS

def monitor_cmd(repo_path: Path) -> None:
    monitor = HealthMonitor(repo_path=repo_path)
    print("Running health monitor to detect issues...")
    has_issues, output = monitor.detect_issues()
    if not has_issues:
        print("✅ No issues detected. All tests passed.")
    else:
        print("🚨 Issues detected. Test output:")
        print(output)

def heal_cmd(repo_path: Path) -> None:
    monitor = HealthMonitor(repo_path=repo_path)
    print("Running health monitor to detect issues...")
    has_issues, output = monitor.detect_issues()
    if not has_issues:
        print("✅ No issues detected. Nothing to heal.")
        return
    print("🚨 Issues detected. Test output:")
    print(output)

    git_manager = GitHealthManager(repo_path=repo_path)
    issue_id = datetime.now().strftime("%Y%m%d%H%M%S")
    branch_name = f"heal/{issue_id}"
    if git_manager.create_healing_branch(issue_id):
        print(f"Created healing branch: {branch_name}")
    else:
        print(f"❌ Failed to create healing branch '{branch_name}'. Aborting.")
        return

    agent = SelfHealingAgent(repo_path=repo_path)
    conceptual_guard = ConceptualGuard(ckad_objectives=CKAD_CONCEPTUAL_GOALS)
    fix_successful = agent.fix_issue(error_context=output)

    if not fix_successful:
        print("❌ Self-healing agent failed to apply a fix. Rolling back.")
        git_manager.rollback_if_failed()
        return

    print("✅ Patch applied. Validating conceptual integrity...")
    if not conceptual_guard.validate_changes(changed_files=[]):
        print("⚠️ Conceptual integrity validation failed. Rolling back.")
        git_manager.rollback_if_failed()
        return

    print("✅ Conceptual integrity validated. Re-running tests to verify the fix...")
    has_issues_after, output_after = monitor.detect_issues()
    if not has_issues_after:
        print("✅✅ Success! All tests passed after the fix.")
    else:
        print("⚠️ The fix was not successful. Tests are still failing. Rolling back.")
        print(output_after)
        git_manager.rollback_if_failed()

def main():
    parser = argparse.ArgumentParser(
        prog="kubelingo-agent",
        description="Self-healing agent CLI for Kubelingo"
    )
    parser.add_argument(
        'command', choices=['monitor', 'heal'],
        help="Command to run: 'monitor' or 'heal'"
    )
    args = parser.parse_args()
    repo_path = Path(__file__).resolve().parent.parent
    if args.command == 'monitor':
        monitor_cmd(repo_path)
    elif args.command == 'heal':
        heal_cmd(repo_path)

if __name__ == '__main__':
    main()