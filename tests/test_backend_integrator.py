import importlib.util
from pathlib import Path

import pytest
import yaml as yaml_lib

# Load backend_integrator module
module_path = Path(__file__).parent.parent / "backend_integrator.py"
spec = importlib.util.spec_from_file_location("backend_integrator", str(module_path))
bi_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bi_module)

BackendIntegrator = bi_module.BackendIntegrator
BackendType = bi_module.BackendType

@pytest.fixture
def temp_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_VAR=hello\n")
    # Remove from os.environ to test file loading
    monkeypatch.delenv("TEST_VAR", raising=False)
    return str(env_file)

def test_load_env_vars_includes_file_and_os_env(monkeypatch, temp_env_file):
    # Set OS env
    monkeypatch.setenv("OS_VAR", "world")
    integrator = BackendIntegrator(env_file_path=temp_env_file)
    assert integrator.env_vars.get("TEST_VAR") == "hello"
    assert integrator.env_vars.get("OS_VAR") == "world"

def test_create_minimal_base_yaml_deployment_service_pod():
    integrator = BackendIntegrator()
    # Deployment
    yaml_text = integrator._create_minimal_base_yaml("Create Deployment foo")
    data = yaml_lib.safe_load(yaml_text)
    assert data["kind"] == "Deployment"
    # Service
    yaml_text = integrator._create_minimal_base_yaml("Create Service foo")
    data = yaml_lib.safe_load(yaml_text)
    assert data["kind"] == "Service"
    # Pod (default)
    yaml_text = integrator._create_minimal_base_yaml("Do something else")
    data = yaml_lib.safe_load(yaml_text)
    assert data["kind"] == "Pod"

def test_extract_yaml_from_output_code_block():
    integrator = BackendIntegrator()
    output = "Some log\n```yaml\napiVersion: v1\nkind: Pod\nmetadata:\n  name: test\n```Other text"
    extracted = integrator._extract_yaml_from_output(output)
    assert "apiVersion: v1" in extracted
    assert "kind: Pod" in extracted
    assert "metadata:" in extracted