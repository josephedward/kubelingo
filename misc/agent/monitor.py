"""
Health monitoring for the self-healing agent.
"""
from pathlib import Path
import subprocess

class HealthMonitor:
    """Monitors repository health by running tests and reporting failures."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def detect_issues(self) -> tuple[bool, str]:
        """
        Run pytest in the repository. Returns (has_issues, output).
        """
        try:
            process = subprocess.run(
                ["pytest"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
            if process.returncode != 0:
                output = f"stdout:\n{process.stdout}\n\nstderr:\n{process.stderr}"
                return True, output
            return False, "All tests passed."
        except FileNotFoundError:
            return True, "pytest not found. Install pytest to enable health checks."
        except Exception as e:
            return True, f"Unexpected error during health check: {e}"