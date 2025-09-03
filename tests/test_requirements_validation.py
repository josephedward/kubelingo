import pytest
import yaml

from kubelingo.validation import validate_requirements

POD_YAML = """
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  replicas: 1
  containers:
    - name: test-container
      image: nginx:1.21
      resources:
        requests:
          cpu: "100m"
          memory: "128Mi"
        limits:
          cpu: "200m"
          memory: "256Mi"
"""

SERVICE_YAML = """
apiVersion: v1
kind: Service
metadata:
  name: svc
spec:
  selector:
    app: myapp
  ports:
    - port: 80
      targetPort: 8080
"""

CONFIGMAP_YAML = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: cfg
data:
  KEY1: value1
  KEY2: value2
"""

@pytest.fixture
def pod_obj():
    return yaml.safe_load(POD_YAML)

@pytest.fixture
def service_obj():
    return yaml.safe_load(SERVICE_YAML)

@pytest.fixture
def configmap_obj():
    return yaml.safe_load(CONFIGMAP_YAML)

def test_validate_kind_and_metadata(pod_obj):
    reqs = {"kind": "Pod", "metadata": {"name": "test-pod"}}
    ok, errs = validate_requirements(pod_obj, reqs)
    assert ok and not errs

def test_validate_kind_mismatch(pod_obj):
    reqs = {"kind": "Deployment"}
    ok, errs = validate_requirements(pod_obj, reqs)
    assert not ok
    assert any("Expected kind='Deployment'" in e for e in errs)

def test_validate_replicas(pod_obj):
    reqs = {"replicas": 1}
    ok, errs = validate_requirements(pod_obj, reqs)
    assert ok
    reqs2 = {"replicas": 2}
    ok2, errs2 = validate_requirements(pod_obj, reqs2)
    assert not ok2
    assert any("Expected replicas=2" in e for e in errs2)

def test_validate_container_name_and_image(pod_obj):
    reqs = {"container": {"name": "test-container", "image": "nginx:1.21"}}
    ok, errs = validate_requirements(pod_obj, reqs)
    assert ok
    # mismatched image
    reqs2 = {"container": {"image": "nginx:latest"}}
    ok2, errs2 = validate_requirements(pod_obj, reqs2)
    assert not ok2
    assert any("container.image='nginx:latest'" in e for e in errs2)

def test_validate_requests_limits(pod_obj):
    reqs = {"requests": {"cpu": "100m", "memory": "128Mi"},
            "limits": {"cpu": "200m", "memory": "256Mi"}}
    ok, errs = validate_requirements(pod_obj, reqs)
    assert ok
    reqs2 = {"limits": {"memory": "512Mi"}}
    ok2, errs2 = validate_requirements(pod_obj, reqs2)
    assert not ok2
    assert any("resources.limits.memory='512Mi'" in e for e in errs2)

def test_validate_service_ports_and_selector(service_obj):
    reqs = {"kind": "Service", "selector": {"app": "myapp"},
            "ports": {"port": 80, "targetPort": 8080}}
    ok, errs = validate_requirements(service_obj, reqs)
    assert ok
    # mismatched selector
    reqs2 = {"selector": {"app": "other"}}
    ok2, errs2 = validate_requirements(service_obj, reqs2)
    assert not ok2
    assert any("service.selector.app='other'" in e for e in errs2)

def test_validate_configmap_data(configmap_obj):
    reqs = {"kind": "ConfigMap", "metadata": {"name": "cfg"},
            "data": {"KEY1": "value1", "KEY2": "value2"}}
    ok, errs = validate_requirements(configmap_obj, reqs)
    assert ok
    # missing key
    reqs2 = {"data": {"KEY3": "val"}}
    ok2, errs2 = validate_requirements(configmap_obj, reqs2)
    assert not ok2
    assert any("configmap.data.KEY3" in e for e in errs2)