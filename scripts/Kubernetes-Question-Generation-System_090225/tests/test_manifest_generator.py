import importlib.util
from pathlib import Path

import pytest
import sys
from pathlib import Path
import yaml as yaml_lib

sys.path.insert(0, str(Path(__file__).parent.parent))
# Load k8s_manifest_generator module
module_path = Path(__file__).parent.parent / "k8s_manifest_generator.py"
spec = importlib.util.spec_from_file_location("k8s_manifest_generator", str(module_path))
mg_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mg_module)

ManifestGenerator = mg_module.ManifestGenerator

@pytest.fixture(autouse=True)
def no_api_keys(monkeypatch):
    # Remove keys to force static-only behavior
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    yield

def test_validate_yaml_valid_and_invalid():
    mg = ManifestGenerator(env_file_path="does_not_exist.env")
    valid = mg.validate_yaml("apiVersion: v1\nkind: Pod")
    assert valid["valid"] is True
    assert valid["error"] is None
    # Use malformed YAML for invalid case
    invalid = mg.validate_yaml("apiVersion: [v1, v2")
    assert invalid["valid"] is False
    assert isinstance(invalid["error"], str)

def test_introduce_flaw_missing_replicas():
    mg = ManifestGenerator(env_file_path="does_not_exist.env")
    input_yaml = (
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: test\n"
        "spec:\n"
        "  replicas: 3\n"
    )
    flawed = mg.introduce_flaw(input_yaml, flaw_type="missing-replicas")
    data = yaml_lib.safe_load(flawed)
    assert "replicas" not in data["spec"]

def test_introduce_flaw_invalid_port():
    mg = ManifestGenerator(env_file_path="does_not_exist.env")
    input_yaml = (
        "apiVersion: v1\n"
        "kind: Pod\n"
        "spec:\n"
        "  containers:\n"
        "  - name: c\n"
        "    image: img\n"
        "    ports:\n"
        "    - containerPort: 80\n"
    )
    flawed = mg.introduce_flaw(input_yaml, flaw_type="invalid-port")
    data = yaml_lib.safe_load(flawed)
    assert data["spec"]["containers"][0]["ports"][0]["containerPort"] == 99999

def test_introduce_flaw_missing_labels():
    mg = ManifestGenerator(env_file_path="does_not_exist.env")
    input_yaml = (
        "apiVersion: v1\n"
        "kind: Pod\n"
        "metadata:\n"
        "  name: test\n"
        "  labels:\n"
        "    app: test\n"
    )
    flawed = mg.introduce_flaw(input_yaml, flaw_type="missing-labels")
    data = yaml_lib.safe_load(flawed)
    assert "labels" not in data["metadata"]

def test_introduce_flaw_wrong_api_version():
    mg = ManifestGenerator(env_file_path="does_not_exist.env")
    input_yaml = "apiVersion: v1\nkind: Pod\n"
    flawed = mg.introduce_flaw(input_yaml, flaw_type="wrong-api-version")
    data = yaml_lib.safe_load(flawed)
    assert data["apiVersion"] == "v2"