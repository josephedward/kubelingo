import pytest
from unittest.mock import patch
from kubelingo.utils.validation import commands_equivalent, validate_yaml_structure

def test_commands_equivalent_basic():
    """Test basic command equivalence."""
    cmd1 = "kubectl get pods"
    cmd2 = "kubectl get pods"
    assert commands_equivalent(cmd1, cmd2)

def test_commands_equivalent_whitespace():
    """Test command equivalence with different whitespace."""
    cmd1 = "kubectl  get   pods"
    cmd2 = "kubectl get pods"
    assert commands_equivalent(cmd1, cmd2)

def test_commands_not_equivalent():
    """Test commands that are not equivalent."""
    cmd1 = "kubectl get pods"
    cmd2 = "kubectl get services"
    assert not commands_equivalent(cmd1, cmd2)

def test_commands_equivalent_case_insensitive():
    """Test command equivalence is case-insensitive (Rust and Python fallback)."""
    cmd1 = "kubectl get pods"
    cmd2 = "KUBECTL GET PODS"
    assert commands_equivalent(cmd1, cmd2)


@patch('kubelingo.utils.validation.rust_commands_equivalent', None)
def test_commands_equivalent_python_fallback(capsys):
    """Test that the Python fallback for command equivalence works."""
    cmd1 = "kubectl  get   pods"
    cmd2 = "kubectl get pods"
    assert commands_equivalent(cmd1, cmd2)
    captured = capsys.readouterr()
    assert "Warning: Rust extension not found" in captured.out


@patch('kubelingo.utils.validation.rust_validate_yaml_structure', None)
def test_validate_yaml_structure_python_fallback(capsys):
    """Test that the Python fallback for YAML validation works."""
    yaml_content = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test"
    result = validate_yaml_structure(yaml_content)
    assert result['valid'] is True
    captured = capsys.readouterr()
    assert "Warning: Rust extension not found" in captured.out

