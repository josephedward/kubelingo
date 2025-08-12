"""
Self-healing agent logic for Kubelingo.
"""
import os
import subprocess
from pathlib import Path

class SelfHealingAgent:
    """Attempts to fix issues using a local LLM agent (e.g., Aider)."""

    def __init__(self, repo_path: Path, model: str = "llama3.2:3b"):
        self.repo_path = repo_path
        self.model = os.getenv("AIDER_MODEL", model)

    def fix_issue(self, error_context: str) -> bool:
        """
        Invoke the agent to fix the given error context.
        Returns True if a fix was applied, False otherwise.
        """
        prompt = f"""
Fix the following issues in the repository:

{error_context}
"""
        cmd = [
            "aider",
            "--model", self.model,
            "--message", prompt,
            "--yes",
        ]
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            print("Error: 'aider' not found. Install aider-chat and ensure it's in PATH.")
            return False
        except subprocess.CalledProcessError as e:
            print(f"Error running aider: {e}")
            return Falseimport os
import subprocess
from pathlib import Path

from kubelingo.utils.path_utils import get_project_root
from .monitor import HealthMonitor

# Placeholder for conceptual goals. In a real implementation, this could be loaded from a config file.
CKAD_CONCEPTUAL_GOALS = "The application should help users study for the CKAD exam by providing quizzes on Kubernetes concepts, commands, and YAML manifests. It must be interactive and provide feedback."


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


def run_self_healing_cycle():
    """Runs a single cycle of health monitoring and self-healing."""
    project_root = get_project_root()
    print(f"Project root: {project_root}")

    monitor = HealthMonitor(repo_path=project_root)
    print("Running health monitor to detect issues...")
    has_issues, output = monitor.detect_issues()

    if not has_issues:
        print("✅ No issues detected. All tests passed.")
        return

    print("🚨 Issues detected. Test output:")
    print(output)
    print("\nInitiating self-healing agent...")

    agent = SelfHealingAgent(repo_path=project_root)
    fix_successful = agent.fix_issue(error_context=output)

    if fix_successful:
        print("✅ Self-healing agent attempted a fix and committed changes.")
        print("Re-running tests to verify the fix...")
        has_issues_after_fix, output_after_fix = monitor.detect_issues()
        if not has_issues_after_fix:
            print("✅✅ Success! All tests passed after the fix.")
        else:
            print("⚠️ The fix was not successful. Tests are still failing.")
            print(output_after_fix)
    else:
        print("❌ Self-healing agent failed to apply a fix.")
