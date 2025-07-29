import pytest
from kubelingo.utils.validation import commands_equivalent

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

