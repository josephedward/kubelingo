import pytest
from kubelingo.utils.validation import normalize_command, commands_equivalent


@pytest.mark.parametrize("command1, command2, are_equivalent", [
    # Identical commands
    ("kubectl get pods", "kubectl get pods", True),
    # Aliased vs. full command
    ("k get po", "kubectl get pods", True),
    ("kubectl describe deploy my-app", "k describe deployments my-app", True),
    # Flag aliases
    ("kubectl get pods -n default", "kubectl get pods --namespace default", True),
    # Flag order
    ("kubectl run nginx --image=nginx --replicas=3", "kubectl run nginx --replicas=3 --image=nginx", True),
    # Different commands
    ("kubectl get pods", "kubectl get services", False),
    ("kubectl get pods my-pod", "kubectl get pods other-pod", False),
    ("kubectl scale deploy --replicas=3", "kubectl scale deploy --replicas=5", False),
    # Case differences
    ("KUBEctl GET poDS", "k get po", True),
])
def test_commands_equivalent(command1, command2, are_equivalent):
    """Tests command equivalence logic with various aliases and structures."""
    assert commands_equivalent(command1, command2) == are_equivalent
