import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
import pytest
import json
from unittest.mock import patch, mock_open, MagicMock

# Functions to test
from kubelingo.modules.base.session import SessionManager
from kubelingo.modules.kubernetes.session import (
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

@pytest.fixture
def session_manager():
    """Fixture for a SessionManager instance."""
    return SessionManager(logger=MagicMock())

# --- Tests for File Operations ---

@pytest.mark.skip(reason="Review flagging now uses separate store; JSON file mutation deprecated")
def test_mark_question_for_review(sample_quiz_data, session_manager):
    """Tests that a question is correctly flagged for review in the data file."""
    # Simulate empty flagged file
    session_manager.flagged_file = 'dummy_flags.json'
    session_manager.flagged_ids = set()
    mock_file = mock_open(read_data='[]')
    with patch('builtins.open', mock_file):
        # Flag a question by its unique ID
        session_manager.mark_question_for_review('core::0')
    # Capture written JSON to flagged file
    written_content = ''.join(call.args[0] for call in mock_file().write.call_args_list)
    updated_flags = json.loads(written_content)
    assert 'core::0' in updated_flags

@pytest.mark.skip(reason="Review flagging now uses separate store; JSON file mutation deprecated")
def test_unmark_question_for_review(sample_quiz_data, session_manager):
    """Tests that a 'review' flag is correctly removed from a question."""
    # Simulate flagged IDs with two entries
    session_manager.flagged_file = 'dummy_flags.json'
    session_manager.flagged_ids = {'core::1', 'other::0'}
    mock_file = mock_open(read_data=json.dumps(sorted(session_manager.flagged_ids)))
    with patch('builtins.open', mock_file):
        # Unflag a question by its unique ID
        session_manager.unmark_question_for_review('core::1')
    written_content = ''.join(call.args[0] for call in mock_file().write.call_args_list)
    updated_flags = json.loads(written_content)
    assert 'core::1' not in updated_flags
    assert 'other::0' in updated_flags

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

@pytest.mark.skip(reason="YAML functionality not yet implemented")
def test_validate_yaml_structure_success():
    """Tests validate_yaml_structure with a valid Kubernetes object."""
    valid_yaml = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': 'test'}}
    result = validate_yaml_structure(yaml.dump(valid_yaml))
    assert result['valid'] is True
    assert not result['errors']

@pytest.mark.skip(reason="YAML functionality not yet implemented")
def test_validate_yaml_structure_missing_fields():
    """Tests validate_yaml_structure with missing required fields."""
    invalid_yaml = {'apiVersion': 'v1', 'kind': 'Pod'}
    result = validate_yaml_structure(yaml.dump(invalid_yaml))
    assert result['valid'] is False
    assert any("metadata" in str(error) for error in result['errors'])

@pytest.fixture
def yaml_editor():
    return VimYamlEditor()

@pytest.mark.skip(reason="YAML functionality not yet implemented")
def test_create_yaml_exercise_known_type(yaml_editor):
    """Tests that create_yaml_exercise returns a dict for a known type."""
    pod_template = yaml_editor.create_yaml_exercise("pod")
    assert isinstance(pod_template, dict)
    assert pod_template['kind'] == 'Pod'

@pytest.mark.skip(reason="YAML functionality not yet implemented")
def test_create_yaml_exercise_unknown_type(yaml_editor):
    """Tests that create_yaml_exercise raises ValueError for an unknown type."""
    with pytest.raises(ValueError, match="Unknown exercise type: non-existent-type"):
        yaml_editor.create_yaml_exercise("non-existent-type")

