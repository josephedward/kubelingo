import pytest
import os
import shutil
import tempfile
from unittest.mock import patch
import yaml
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
    # `-es` runs in ex mode silently, which is ideal for scripting.
    vim_args = ["-es", vim_script]
    
    edited_yaml = vim_editor.edit_yaml_with_vim(initial_yaml, _vim_args=vim_args)

    assert edited_yaml is not None
    assert "labels" in edited_yaml.get("metadata", {})
    assert edited_yaml["metadata"]["labels"] == {"app": "myapp"}
    assert edited_yaml["spec"] == initial_yaml["spec"] # Ensure other parts are untouched

    # The script should exit cleanly (returncode 0), so no warning should be printed.
    mock_print.assert_not_called()
