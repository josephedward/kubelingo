import pytest
import shutil
import tempfile
import os
import subprocess
from kubelingo.modules.kubernetes.vimrunner import Server

def _vim_supports_clientserver():
    """Checks if vim is installed and has the +clientserver feature."""
    if shutil.which('vim') is None:
        return False
    try:
        # The version info can be on stdout or stderr depending on the system
        output = subprocess.check_output(
            ['vim', '--version'], text=True, stderr=subprocess.STDOUT
        )
        return '+clientserver' in output
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

pytestmark = pytest.mark.skipif(
    not _vim_supports_clientserver(),
    reason="Vim with +clientserver support not available, skipping real integration tests"
)

@pytest.fixture
def vim_server():
    """Fixture to start and clean up a Vim server for testing."""
    server = Server()
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
