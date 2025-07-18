import pytest
import os
import shutil
import tempfile
from unittest.mock import patch, MagicMock
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


@pytest.fixture
def vim_client(vim_executable):
    """Fixture to start a vim instance and provide a client."""
    if not vimrunner:
        pytest.skip("vimrunner is not installed")
    server = vimrunner.Server(executable=vim_executable)
    client = server.start()
    yield client
    server.kill()


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


@pytest.fixture
def multi_vim_script():
    """Create two vim scripts: one to add a label, one to change the image."""
    script1_content = """/metadata/a
  labels:
    app: myapp-multi
.
"""
    script2_content = """:%s/image: nginx/image: nginx:1.21/g
:wq
"""
    # Create temporary files for scripts
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".vim", encoding='utf-8') as f1, \
         tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".vim", encoding='utf-8') as f2:
        f1.write(script1_content)
        f2.write(script2_content)
        script1_path, script2_path = f1.name, f2.name

    yield [script1_path, script2_path]

    os.remove(script1_path)
    os.remove(script2_path)

def test_edit_yaml_with_multiple_vim_scripts(vim_editor, multi_vim_script):
    """
    Tests that multiple vim scripts passed via _vim_args are executed in order.
    """
    initial_yaml = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "test-pod"},
                    "spec": {"containers": [{"name": "nginx", "image": "nginx"}]}}

    # The implementation will automatically convert file paths to -S arguments
    vim_args = ["-e", "-s"] + multi_vim_script

    edited_yaml = vim_editor.edit_yaml_with_vim(initial_yaml, _vim_args=vim_args)

    assert edited_yaml is not None
    assert edited_yaml.get("metadata", {}).get("labels") == {"app": "myapp-multi"}
    assert edited_yaml.get("spec", {}).get("containers")[0].get("image") == "nginx:1.21"

def test_edit_yaml_with_vim_c_command(vim_editor):
    """
    Tests editing using a vim -c command argument.
    """
    initial_yaml = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "test-pod"}}
    vim_args = ["-e", "-s", "-c", "%s/test-pod/renamed-pod/g", "-c", "wq"]

    edited_yaml = vim_editor.edit_yaml_with_vim(initial_yaml, _vim_args=vim_args)

    assert edited_yaml is not None
    assert edited_yaml.get("metadata", {}).get("name") == "renamed-pod"

def test_edit_yaml_with_raw_string_input(vim_editor, vim_script):
    """
    Tests passing a raw YAML string to the editor function.
    """
    initial_yaml_str = """
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
"""
    vim_args = ["-e", "-s", "-S", vim_script] # script adds a label
    edited_yaml = vim_editor.edit_yaml_with_vim(initial_yaml_str, _vim_args=vim_args)

    assert edited_yaml is not None
    assert edited_yaml.get("metadata", {}).get("labels") == {"app": "myapp"}

def test_temp_file_is_cleaned_up(vim_editor, tmp_path):
    """
    Ensures the temporary file is deleted after editing, even on failure.
    """
    # Point tempfile directory to pytest's tmp_path for this test
    original_tempdir = tempfile.tempdir
    tempfile.tempdir = str(tmp_path)
    
    # Simulate an error during editing by providing invalid YAML
    with patch('yaml.safe_load', side_effect=yaml.YAMLError("parsing failed")):
        vim_editor.edit_yaml_with_vim("key: value: invalid", _vim_args=["-c", "wq"])

    # After the function returns (even with an error), the temp dir should be empty
    assert len(list(tmp_path.iterdir())) == 0

    # Reset tempdir to avoid side effects on other tests
    tempfile.tempdir = original_tempdir
