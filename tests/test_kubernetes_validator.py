import sys
import pytest
from pathlib import Path

# Ensure the qgen+grader directory is on the import path
sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts' / 'qgen+grader_090125'))

import kubernetes_generator

@pytest.fixture
def validator():
    return kubernetes_generator.KubernetesAnswerValidator()

def test_validate_kubectl_command_success(validator):
    requirements = {'name': 'nginx', 'image': 'nginx:1.20'}
    result = validator.validate_kubectl_command(
        'kubectl run nginx --image=nginx:1.20', requirements)
    assert result['valid']
    assert result['type'] == 'kubectl_command'
    assert result['extracted_values']['name'] == 'nginx'
    assert result['extracted_values']['image'] == 'nginx:1.20'

def test_validate_kubectl_command_name_mismatch(validator):
    requirements = {'name': 'nginx', 'image': 'nginx:1.20'}
    result = validator.validate_kubectl_command(
        'kubectl run wrong --image=nginx:1.20', requirements)
    assert not result['valid']
    assert any('Name mismatch' in err for err in result['errors'])

def test_validate_yaml_manifest_minimal(validator):
    requirements = {'kind': 'Pod', 'name': 'nginx', 'image': 'nginx:1.20'}
    manifest = {
        'apiVersion': 'v1',
        'kind': 'Pod',
        'metadata': {'name': 'nginx'},
        'spec': {'containers': [{'name': 'nginx', 'image': 'nginx:1.20'}]}
    }
    result = validator.validate_yaml_manifest(manifest, requirements)
    assert result['valid']
    assert result['type'] == 'yaml_manifest'
    assert result['extracted_values']['spec.containers[0].image'] == 'nginx:1.20'

def test_validate_yaml_manifest_wrong_image(validator):
    requirements = {'kind': 'Pod', 'name': 'nginx', 'image': 'nginx:1.20'}
    manifest = {
        'apiVersion': 'v1',
        'kind': 'Pod',
        'metadata': {'name': 'nginx'},
        'spec': {'containers': [{'name': 'nginx', 'image': 'nginx:1.19'}]}
    }
    result = validator.validate_yaml_manifest(manifest, requirements)
    assert not result['valid']
    assert any('Invalid value for spec.containers[0].image' in err for err in result['errors'])

def test_validate_answer_unknown(validator):
    requirements = {'kind': 'Pod'}
    result = validator.validate_answer('random text', requirements)
    assert not result['valid']
    assert result['type'] == 'unknown'

def test_validate_answer_list_single_manifest(validator):
    requirements = {'kind': 'Pod', 'name': 'nginx', 'image': 'nginx:1.20'}
    manifests = [{
        'apiVersion': 'v1',
        'kind': 'Pod',
        'metadata': {'name': 'nginx'},
        'spec': {'containers': [{'name': 'nginx', 'image': 'nginx:1.20'}]}
    }]
    result = validator.validate_answer(manifests, requirements)
    assert result['valid']
    assert result['type'] == 'yaml_manifest'

def test_validate_answer_multiple_manifests(validator):
    requirements = {'kind': 'Pod'}
    manifests = [{}, {}]
    result = validator.validate_answer(manifests, requirements)
    assert not result['valid']
    assert result['type'] == 'multiple_manifests'