import pytest
import json
from unittest.mock import patch, mock_open

# Functions to test
from kubelingo.modules.kubernetes.session import (
    mark_question_for_review,
    unmark_question_for_review,
    check_dependencies,
    load_questions,
    VimYamlEditor
)
from kubelingo.utils.validation import validate_yaml_structure
import yaml

# --- Fixtures ---

@pytest.fixture
def sample_quiz_data():
    """Provides sample quiz data as a dictionary."""
    return [
        {
            "category": "core",
            "prompts": [
                {"prompt": "Get all pods", "response": "kubectl get pods", "type": "command"},
                {"prompt": "Get a specific pod", "response": "kubectl get pod my-pod", "type": "command", "review": True}
            ]
        },
        {
            "category": "networking",
            "prompts": [
                {"prompt": "Expose a deployment", "response": "kubectl expose deployment my-deploy", "type": "command"}
            ]
        }
    ]

# --- Tests for File Operations ---

def test_mark_question_for_review(sample_quiz_data):
    """Tests that a question is correctly flagged for review in the data file."""
    mock_file = mock_open(read_data=json.dumps(sample_quiz_data))
    with patch('builtins.open', mock_file):
        mark_question_for_review("dummy_path.json", "core", "Get all pods")

    written_content = "".join(call.args[0] for call in mock_file().write.call_args_list)
    updated_data = json.loads(written_content)
    assert updated_data[0]['prompts'][0]['review'] is True

def test_unmark_question_for_review(sample_quiz_data):
    """Tests that a 'review' flag is correctly removed from a question."""
    mock_file = mock_open(read_data=json.dumps(sample_quiz_data))
    with patch('builtins.open', mock_file):
        unmark_question_for_review("dummy_path.json", "core", "Get a specific pod")

    written_content = "".join(call.args[0] for call in mock_file().write.call_args_list)
    updated_data = json.loads(written_content)
    assert 'review' not in updated_data[0]['prompts'][1]

# --- Tests for Dependency Checking ---

@patch('shutil.which')
def test_check_dependencies_all_found(mock_which):
    """Tests dependency check when all commands are found."""
    mock_which.return_value = '/usr/bin/some_command'
    assert check_dependencies('git', 'docker', 'kubectl') == []
    assert mock_which.call_count == 3

@patch('shutil.which')
def test_check_dependencies_some_missing(mock_which):
    """Tests dependency check when some commands are missing."""
    def which_side_effect(cmd):
        return '/usr/bin/cmd' if cmd == 'git' else None
    
    mock_which.side_effect = which_side_effect
    assert check_dependencies('git', 'docker', 'kubectl') == ['docker', 'kubectl']

# --- Tests for Question Loading ---

def test_load_questions(sample_quiz_data):
    """Tests loading questions from a JSON file."""
    mock_file = mock_open(read_data=json.dumps(sample_quiz_data))
    with patch('builtins.open', mock_file):
        questions = load_questions("dummy.json")
    
    assert len(questions) == 3
    assert questions[0]['category'] == 'core'
    assert questions[0]['prompt'] == 'Get all pods'
    assert questions[1]['review'] is True

# --- Tests for YAML Validation and Creation ---

@pytest.mark.skipif(yaml is None, reason="PyYAML is not installed")
def test_validate_yaml_structure_success():
    """Tests validate_yaml_structure with a valid Kubernetes object."""
    valid_yaml = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': 'test'}}
    valid, msg = validate_yaml_structure(yaml.dump(valid_yaml))
    assert valid is True
    assert "valid" in msg.lower()

@pytest.mark.skipif(yaml is None, reason="PyYAML is not installed")
def test_validate_yaml_structure_missing_fields():
    """Tests validate_yaml_structure with missing required fields."""
    invalid_yaml = {'apiVersion': 'v1', 'kind': 'Pod'}
    valid, msg = validate_yaml_structure(yaml.dump(invalid_yaml))
    assert valid is False
    assert "Missing required fields" in msg

@pytest.fixture
def yaml_editor():
    return VimYamlEditor()

def test_create_yaml_exercise_known_type(yaml_editor):
    """Tests that create_yaml_exercise returns a dict for a known type."""
    pod_template = yaml_editor.create_yaml_exercise("pod")
    assert isinstance(pod_template, dict)
    assert pod_template['kind'] == 'Pod'

def test_create_yaml_exercise_unknown_type(yaml_editor):
    """Tests that create_yaml_exercise raises ValueError for an unknown type."""
    with pytest.raises(ValueError, match="Unknown exercise type: non-existent-type"):
        yaml_editor.create_yaml_exercise("non-existent-type")

