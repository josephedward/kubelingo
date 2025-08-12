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
            return False