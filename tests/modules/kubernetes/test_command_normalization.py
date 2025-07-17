import pytest
from kubelingo.modules.kubernetes.session import normalize_command, commands_equivalent

@pytest.mark.parametrize("input_command, expected_normalized_list", [
    # Simple case
    ("kubectl get pods", ["kubectl", "get", "pods"]),
    # Verb and resource aliases
    ("k get po", ["kubectl", "get", "pods"]),
    ("k describe svc my-service", ["kubectl", "describe", "services", "my-service"]),
    # Flag aliases and value handling
    ("kubectl get pods -n default", ["kubectl", "get", "pods", "--namespace=default"]),
    ("kubectl get pods --namespace=default", ["kubectl", "get", "pods", "--namespace=default"]),
    ("kubectl get pods -o yaml", ["kubectl", "get", "pods", "--output=yaml"]),
    # Flag ordering is normalized
    ("kubectl create deployment --image=nginx nginx", ["kubectl", "create", "deployments", "nginx", "--image=nginx"]),
    # Case insensitivity
    ("KubeCTL GeT PoDs", ["kubectl", "get", "pods"]),
    # Unhandled aliases/verbs pass through
    ("kubectl custom-verb custom-resource", ["kubectl", "custom-verb", "custom-resource"]),
    # Multiple flags
    ("kubectl run nginx --image=nginx --replicas 2", ["kubectl", "run", "nginx", "--image=nginx", "--replicas=2"]),
])
def test_normalize_command(input_command, expected_normalized_list):
    """Tests that commands are normalized into a canonical list of tokens."""
    assert normalize_command(input_command) == expected_normalized_list

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
