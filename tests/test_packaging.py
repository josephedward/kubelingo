import subprocess
import sys
import venv
from pathlib import Path

import pytest


@pytest.mark.e2e
@pytest.mark.skip(reason="Skipping packaging test in offline environment")
def test_install_and_run_from_source(tmp_path: Path):
    """
    Tests that the package can be installed from source using pip
    and that a basic command works. This is a basic check for packaging issues.
    """
    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)

    if sys.platform == "win32":
        pip_executable = venv_dir / "Scripts" / "pip.exe"
        executable = venv_dir / "Scripts" / "kubelingo.exe"
    else:
        pip_executable = venv_dir / "bin" / "pip"
        executable = venv_dir / "bin" / "kubelingo"

    # Install the project from the current directory.
    # Assumes the test is run from the project root.
    # Install the project from the current directory, without build isolation to reuse venv build tools
    subprocess.check_call([str(pip_executable), "install", "--no-build-isolation", "."])

    # Run a simple command to check if installation was successful.
    result = subprocess.run(
        [str(executable), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )

    # Check for a string that is likely to be in the --help output.
    assert "usage: kubelingo" in result.stdout
