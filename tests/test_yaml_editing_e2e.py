import pytest
from unittest.mock import patch, call

pytestmark = pytest.mark.skip(reason="YAML editing feature not enabled")
try:
    import yaml
except ImportError:
    yaml = None

from kubelingo.modules.kubernetes.session import VimYamlEditor


@pytest.fixture
def editor():
    """Fixture to provide a VimYamlEditor instance."""
    return VimYamlEditor()


# Test data for the progressive exercise
starting_pod_yaml_str = """
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
  - name: main
    image: nginx:1.20
"""

step1_edited_pod_dict = {
    'apiVersion': 'v1',
    'kind': 'Pod',
    'metadata': {'name': 'test-pod', 'labels': {'app': 'test'}},
    'spec': {'containers': [{'name': 'main', 'image': 'nginx:1.20'}]}
}

step2_edited_pod_dict = {
    'apiVersion': 'v1',
    'kind': 'Pod',
    'metadata': {'name': 'test-pod', 'labels': {'app': 'test'}},
    'spec': {'containers': [{'name': 'main', 'image': 'nginx:1.21'}]}
}


# Dummy validation functions
def validate_step1(yaml_obj):
    return 'labels' in yaml_obj.get('metadata', {}), "Labels are missing"


def validate_step2(yaml_obj):
    image = yaml_obj.get('spec', {}).get('containers', [{}])[0].get('image')
    return image == 'nginx:1.21', f"Incorrect image: {image}"


exercise_steps = [
    {
        'prompt': "Step 1: Add a label 'app: test' to the pod.",
        'starting_yaml': starting_pod_yaml_str,
        'validation_func': validate_step1
    },
    {
        'prompt': "Step 2: Update the container image to 'nginx:1.21'.",
        'validation_func': validate_step2
    }
]


@pytest.mark.skipif(yaml is None, reason="PyYAML is not installed")
def test_progressive_yaml_exercise_e2e_success(editor):
    """
    Tests the end-to-end flow of a progressive YAML exercise, simulating
    successful user edits at each step.
    """
    with patch('kubelingo.modules.kubernetes.session.VimYamlEditor.edit_yaml_with_vim') as mock_edit:
        # Simulate the user successfully editing the YAML in Vim at each step
        mock_edit.side_effect = [
            step1_edited_pod_dict,  # Return for step 1
            step2_edited_pod_dict   # Return for step 2
        ]

        result = editor.run_progressive_yaml_exercises(exercise_steps)

    assert result is True, "Progressive exercise should succeed with valid edits"

    # Verify that the editor was opened with the correct content at each stage
    assert mock_edit.call_count == 2
    mock_edit.assert_has_calls([
        call(starting_pod_yaml_str, 'step-1.yaml'),
        call(step1_edited_pod_dict, 'step-2.yaml')
    ])


@pytest.mark.skipif(yaml is None, reason="PyYAML is not installed")
def test_progressive_yaml_exercise_e2e_invalid_yaml(editor):
    """
    Tests that the progressive exercise handles invalid YAML from the editor
    and exits gracefully.
    """
    with patch('kubelingo.modules.kubernetes.session.VimYamlEditor.edit_yaml_with_vim') as mock_edit:
        # Simulate the editor returning None (e.g., user saves invalid YAML)
        mock_edit.return_value = None

        result = editor.run_progressive_yaml_exercises(exercise_steps)

    assert result is False, "Progressive exercise should fail if YAML is invalid"
    assert mock_edit.call_count == 1, "Should stop after the first failed edit"
