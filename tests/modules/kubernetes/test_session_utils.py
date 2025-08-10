import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
import pytest
from unittest.mock import patch, mock_open, MagicMock

# Functions to test
from kubelingo.modules.base.session import SessionManager
from kubelingo.modules.kubernetes.session import (
    check_dependencies,
    VimYamlEditor
)
from kubelingo.utils.validation import validate_yaml_structure
import yaml

# --- Fixtures ---

@pytest.fixture
def session_manager():
    """Fixture for a SessionManager instance."""
    return SessionManager(logger=MagicMock())

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

