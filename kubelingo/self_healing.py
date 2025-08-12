import os
import subprocess
from pathlib import Path

# Placeholder for conceptual goals, as mentioned in the user's document.
# In a real implementation, this could be loaded from a config file.
CKAD_CONCEPTUAL_GOALS = "The application should help users study for the CKAD exam by providing quizzes on Kubernetes concepts, commands, and YAML manifests. It must be interactive and provide feedback."

def get_project_root() -> Path:
    """Returns the project root directory."""
    return Path(__file__).parent.parent

class HealthMonitor:
    """Monitors the health of the application by running tests."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def detect_issues(self) -> tuple[bool, str]:
        """
        Runs tests to detect issues and returns a tuple of (has_issues, output).
        """
        try:
            # Using pytest to run tests. Assuming tests are in the 'tests/' directory.
            process = subprocess.run(
                ["pytest"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False,  # Don't raise exception on non-zero exit code
            )
            if process.returncode != 0:
                # Combine stdout and stderr for full context
                output = f"stdout:\n{process.stdout}\n\nstderr:\n{process.stderr}"
                return True, output
            return False, "All tests passed."
        except FileNotFoundError:
            return True, "pytest not found. Please install it with 'pip install pytest'."
        except Exception as e:
            return True, f"An unexpected error occurred while running tests: {e}"

class SelfHealingAgent:
    """An agent that attempts to fix issues using aider."""

    def __init__(self, repo_path: Path, aider_model: str = "gpt-4o-mini"):
        self.repo_path = repo_path
        self.model = os.getenv("AIDER_MODEL", aider_model)

    def fix_issue(self, error_context: str) -> bool:
        """
        Attempts to fix an issue using aider.

        :param error_context: The error message and context from the failed tests.
        :return: True if the fix was applied successfully, False otherwise.
        """
        prompt = f"""
The following tests failed in the Kubelingo CKAD learning CLI. Please fix the issue.

Error context:
```
{error_context}
```

Ensure your fix addresses the test failures while adhering to these core principles:
- The application's main purpose is to help users study for the CKAD exam. Maintain all existing study functionality.
- Do not break the question database schema or functionality.
- Follow Python and Rust best practices already present in the codebase.
- The conceptual goals of the project are: {CKAD_CONCEPTUAL_GOALS}

Please apply the fix and commit the changes.
"""
        try:
            # Aider is best run without specifying files if we want it to use its repo-map
            # and figure out the context on its own. --yes applies the first change.
            cmd = [
                "aider",
                "--model", self.model,
                "--message", prompt,
                "--yes",
            ]

            print(f"Running self-healing agent with command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            print("Aider ran successfully. Output:")
            print(result.stdout)
            if result.stderr:
                print("Aider stderr:")
                print(result.stderr)

            # Aider exits with 0 on success. Aider's stdout is checked for confirmation.
            if "Applied edit to" in result.stdout or "Committing..." in result.stdout:
                return True
            return False
        except FileNotFoundError:
            print("Error: 'aider' command not found. Please ensure aider-chat is installed and in your PATH.")
            return False
        except subprocess.CalledProcessError as e:
            print("Error running aider:")
            print(f"Return code: {e.returncode}")
            print(f"Stdout: {e.stdout}")
            print(f"Stderr: {e.stderr}")
            return False

from kubelingo.agent.monitor import HealthMonitor as AgentHealthMonitor
from kubelingo.agent.heal import SelfHealingAgent as AgentSelfHealingAgent
from kubelingo.agent.git_manager import GitHealthManager
from kubelingo.agent.conceptual_guard import ConceptualGuard
from datetime import datetime

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
