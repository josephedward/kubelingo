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
            return True, f"Unexpected error during health check: {e}"import subprocess
from pathlib import Path


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
