import pytest
import shutil
import tempfile
import os
import subprocess
import sys
from kubelingo.modules.kubernetes.vimrunner import Server, VimrunnerException

def _find_compatible_vim():
    """Finds a vim executable with +clientserver support."""
    # On macOS, prefer 'mvim' or homebrew 'vim'. On Linux, 'gvim' or 'vim'.
    candidates = ['gvim', 'vim']
    if sys.platform == "darwin":
        # On macOS, graphical vim (mvim) is a good candidate
        candidates.insert(0, 'mvim')

    for candidate in candidates:
        executable = shutil.which(candidate)
        if not executable:
            continue
        try:
            output = subprocess.check_output(
                [executable, '--version'], text=True, stderr=subprocess.STDOUT
            )
            if '+clientserver' in output:
                return executable
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    return None

COMPATIBLE_VIM = _find_compatible_vim()

pytestmark = pytest.mark.skipif(
    not COMPATIBLE_VIM,
    reason="A vim executable with +clientserver support was not found."
)

@pytest.fixture
def vim_server():
    """Fixture to start and clean up a Vim server for testing."""
    server = Server(executable=COMPATIBLE_VIM)
    yield server
    server.kill()

def test_edit_file_with_vimrunner(vim_server):
    """
    Tests a real vim session where a file is created, edited, and saved.
    """
    # Arrange
    temp_dir = tempfile.mkdtemp()
    test_file = os.path.join(temp_dir, "test.txt")
    with open(test_file, "w") as f:
        f.write("initial content\n")

    # Act: Start vim, edit the file, and save it
    client = vim_server.start(test_file)
    client.type("G")  # Go to last line
    client.type("o")  # Open new line below
    client.type("appended content") # Type text
    client.type("<esc>") # Exit insert mode
    client.command("w") # Save the file

    # Assert: Check if the file content was updated
    with open(test_file, "r") as f:
        content = f.read()

    assert "initial content" in content
    assert "appended content" in content

    # Cleanup
    shutil.rmtree(temp_dir)
