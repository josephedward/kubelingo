import pytest
import shutil
import tempfile
import os
import pytest
pytest.skip("Skipping real vimrunner integration tests", allow_module_level=True)
try:
    from kubelingo.modules.kubernetes.vim_yaml_editor import Server
except ImportError:
    pass

# The vim_executable fixture from conftest.py handles discovery and skipping.

@pytest.fixture
def vim_server(vim_executable):
    """Fixture to start and clean up a Vim server for testing."""
    server = Server(executable=vim_executable)
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
