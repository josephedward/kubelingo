from datetime import datetime

from kubelingo.agent.conceptual_guard import ConceptualGuard
from kubelingo.agent.git_manager import GitHealthManager
from kubelingo.agent.heal import SelfHealingAgent as AgentSelfHealingAgent
from kubelingo.agent.monitor import HealthMonitor as AgentHealthMonitor
from kubelingo.utils.path_utils import get_project_root

# Placeholder for conceptual goals, as mentioned in the user's document.
# In a real implementation, this could be loaded from a config file.
CKAD_CONCEPTUAL_GOALS = "The application should help users study for the CKAD exam by providing quizzes on Kubernetes concepts, commands, and YAML manifests. It must be interactive and provide feedback."

def run_self_healing_cycle():
    """Runs a single cycle of health monitoring and self-healing."""
    project_root = get_project_root()
    print(f"Project root: {project_root}")

    monitor = AgentHealthMonitor(repo_path=project_root)
    print("Running health monitor to detect issues...")
    has_issues, output = monitor.detect_issues()

    if not has_issues:
        print("✅ No issues detected. All tests passed.")
        return

    print("🚨 Issues detected. Test output:")
    print(output)
    print("\nCreating healing branch and invoking self-healing agent...")

    git_manager = GitHealthManager(repo_path=project_root)
    issue_id = datetime.now().strftime("%Y%m%d%H%M%S")
    branch_name = f"heal/{issue_id}"
    if git_manager.create_healing_branch(issue_id):
        print(f"Created healing branch: {branch_name}")
    else:
        print(f"Failed to create healing branch '{branch_name}'. Aborting healing.")
        return

    agent = AgentSelfHealingAgent(repo_path=project_root)
    conceptual_guard = ConceptualGuard(ckad_objectives=CKAD_CONCEPTUAL_GOALS)
    fix_successful = agent.fix_issue(error_context=output)

    if not fix_successful:
        print("❌ Self-healing agent failed to apply a fix. Rolling back.")
        git_manager.rollback_if_failed()
        return

    print("✅ Self-healing agent applied patch. Validating conceptual integrity...")
    if not conceptual_guard.validate_changes(changed_files=[]):
        print("⚠️ Conceptual integrity validation failed. Rolling back.")
        git_manager.rollback_if_failed()
        return

    print("✅ Conceptual integrity validated. Re-running tests to verify the fix...")
    has_issues_after_fix, output_after_fix = monitor.detect_issues()
    if not has_issues_after_fix:
        print("✅✅ Success! All tests passed after the fix.")
    else:
        print("⚠️ The fix was not successful. Tests are still failing. Rolling back.")
        print(output_after_fix)
        git_manager.rollback_if_failed()
