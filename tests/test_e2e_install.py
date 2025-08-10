import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest

try:
    import pexpect
except ImportError:
    pexpect = None


@pytest.mark.skipif(pexpect is None, reason="pexpect is not installed. Run 'pip install pexpect'")
@pytest.mark.e2e
@pytest.mark.skip(reason="Skipping end-to-end source install test in offline environment")
@pytest.mark.skip(reason="Skipping end-to-end source install test in offline environment")
@pytest.mark.skipif(pexpect is None, reason="pexpect is not installed. Run 'pip install pexpect'")
@pytest.mark.e2e
def test_source_install_and_openai_key_prompt(tmp_path: Path):
    """
    An end-to-end test that installs kubelingo from local source and verifies
    that the interactive prompt for an OpenAI API key works as expected.

    This test is marked as 'e2e' and can be slow.
    It requires the 'pexpect' library.
    """
    venv_dir = tmp_path / "venv"

    # 1. Create a clean virtual environment.
    print(f"\nCreating virtual environment in {venv_dir}...")
    venv.create(venv_dir, with_pip=True, clear=True)

    # 2. Install the package from source.
    pip_executable = venv_dir / "bin" / "pip"
    print("Installing kubelingo from source...")
    install_result = subprocess.run(
        [str(pip_executable), "install", "."],
        capture_output=True, text=True, check=False, timeout=300
    )
    assert install_result.returncode == 0, (
        f"Failed to install kubelingo from source.\n"
        f"STDOUT:\n{install_result.stdout}\n"
        f"STDERR:\n{install_result.stderr}"
    )

    # 3. Run the interactive CLI and check for the API key prompt.
    kubelingo_executable = venv_dir / "bin" / "kubelingo"
    
    # Unset OPENAI_API_KEY to ensure the prompt logic can be triggered.
    child_env = os.environ.copy()
    child_env.pop("OPENAI_API_KEY", None)
    child_env["PATH"] = f"{venv_dir / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"

    print(f"Running '{kubelingo_executable}'...")
    child = pexpect.spawn(str(kubelingo_executable), env=child_env, encoding="utf-8", timeout=20)
    child.logfile_read = sys.stdout

    # Based on shared_context.md, the bare `kubelingo` menu has this option.
    child.expect("Choose a session type:", timeout=15)

    # Navigate down to "Enter OpenAI API Key" (assumed to be the 3rd option).
    child.sendline('\x1b[B')  # Down arrow
    child.sendline('\x1b[B')  # Down arrow
    child.sendline('\r')      # Enter key

    # Verify that the correct prompt is displayed.
    child.expect("Please enter your OpenAI API key:")

    # Cleanly terminate the process.
    child.sendeof()
    child.close()

    assert not child.isalive(), "Process should have terminated."
    assert child.signalstatus == pexpect.EOF, f"Process did not exit cleanly. Exit status: {child.exitstatus}, Signal status: {child.signalstatus}"
