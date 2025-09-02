import pytest

from kubelingo.source_manager import get_source_for_kind

@pytest.mark.parametrize("kind,expected", [
    ("Pod", "https://kubernetes.io/docs/concepts/workloads/pods/"),
    ("Deployment", "https://kubernetes.io/docs/concepts/workloads/controllers/deployment/"),
    ("Service", "https://kubernetes.io/docs/concepts/services-networking/service/"),
    ("PersistentVolumeClaim", "https://kubernetes.io/docs/concepts/storage/persistent-volumes/"),
    ("ConfigMap", "https://kubernetes.io/docs/concepts/configuration/configmap/"),
    ("Secret", "https://kubernetes.io/docs/concepts/configuration/secret/"),
    ("Job", "https://kubernetes.io/docs/concepts/workloads/controllers/job/"),
    ("UnknownKind", "https://kubernetes.io/docs/"),
])
def test_get_source_for_kind(kind, expected):
    assert get_source_for_kind(kind) == expected