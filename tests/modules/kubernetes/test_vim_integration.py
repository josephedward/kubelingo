import pytest
import os
import shutil
import tempfile
from unittest.mock import patch
import yaml

try:
    import vimrunner
except ImportError:
    vimrunner = None

from kubelingo.modules.kubernetes.session import VimYamlEditor

# Skip all tests in this file if vim is not available
pytestmark = pytest.mark.skipif(
    shutil.which('vim') is None,
    reason="Vim is not installed, skipping integration tests"
)

@pytest.fixture
def vim_editor():
    """Fixture to provide a VimYamlEditor instance."""
    return VimYamlEditor()

@pytest.fixture
def vim_script():
    """
    Fixture to create a temporary Vim script file that adds a label to a pod
    definition under the `metadata:` key.
    """
    # This ex-mode script does the following:
    # 1. /metadata/: Searches for the line containing "metadata:".
    # 2. a: Enters append mode to add text on the next line.
    # 3. <content>: The indented text to be added.
    # 4. .: Finishes append mode.
    # 5. wq: Saves the file and quits Vim.
    script_content = """/metadata/a
  labels:
    app: myapp
.
wq
"""

    # We use a temporary file for the script. It will be cleaned up automatically.
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".vim", encoding='utf-8') as f:
        f.write(script_content)
        script_path = f.name
    
    yield script_path
    
    os.remove(script_path)


@patch('builtins.print')
def test_edit_yaml_with_real_vim(mock_print, vim_editor, vim_script):
    """
    Integration test for edit_yaml_with_vim using a real Vim process.
    This test writes a vim script to add a label to a pod definition
    and verifies that the returned yaml object is updated correctly.
    """
    initial_yaml = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "test-pod"
        },
        "spec": {
            "containers": [{
                "name": "nginx",
                "image": "nginx"
            }]
        }
    }

    # Use the internal _vim_args to pass the script to vim.
    # -e: start in Ex mode (non-visual)
    # -s: silent mode (less output)
    # -S {file}: source the given script file after the first file has been read
    # This combination allows for non-interactive scripting of Vim.
    vim_args = ["-e", "-s", "-S", vim_script]
    
    edited_yaml = vim_editor.edit_yaml_with_vim(initial_yaml, _vim_args=vim_args)

    assert edited_yaml is not None
    assert "labels" in edited_yaml.get("metadata", {})
    assert edited_yaml["metadata"]["labels"] == {"app": "myapp"}
    assert edited_yaml["spec"] == initial_yaml["spec"] # Ensure other parts are untouched

    # The script should exit cleanly (returncode 0), so no warning should be printed.
    mock_print.assert_not_called()


@pytest.mark.skipif(vimrunner is None, reason="vimrunner-python is not installed")
@pytest.fixture
def vim_client():
    """Fixture to start a vim instance and provide a client."""
    server = vimrunner.Server()
    client = server.start()
    yield client
    server.kill()


@pytest.mark.skipif(vimrunner is None, reason="vimrunner-python is not installed")
def test_vim_editing_with_vimrunner(vim_client):
    """
    Tests Vim editing capabilities using vimrunner for robust interaction.
    This demonstrates a more advanced testing pattern for full-flow simulations.
    """
    initial_yaml_content = '''apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
  - name: nginx
    image: nginx
'''
    # vimrunner works with files, so we create a temporary one.
    with tempfile.NamedTemporaryFile(mode='w', suffix=".yaml", delete=False, encoding='utf-8') as tmp:
        tmp.write(initial_yaml_content)
        tmp_filename = tmp.name

    try:
        # Edit the file with the running vim instance
        vim_client.edit(tmp_filename)

        # Use a combination of ex commands and fed keys for robust scripting
        vim_client.command('execute "normal /metadata\\ro  labels:\\n    app: myapp"')
        vim_client.command('wq')

        # Verify the file content
        with open(tmp_filename, 'r', encoding='utf-8') as f:
            edited_content = f.read()

        edited_yaml = yaml.safe_load(edited_content)

        assert edited_yaml is not None
        assert "labels" in edited_yaml.get("metadata", {})
        assert edited_yaml["metadata"]["labels"] == {"app": "myapp"}
        assert edited_yaml["spec"]["containers"][0]["image"] == "nginx"

    finally:
        # Clean up the temporary file
        if os.path.exists(tmp_filename):
            os.remove(tmp_filename)
