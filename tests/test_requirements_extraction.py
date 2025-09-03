"""
Smoke tests to verify that every static question now has a non-empty requirements mapping,
parsed from its suggestions or existing definitions.
"""
import glob
import yaml

import pytest

def test_all_questions_have_requirements():
    """
    Ensure each question entry in questions/*.yaml has a 'requirements' dict that is not empty.
    """
    paths = glob.glob("questions/*.yaml")
    assert paths, "No question files found in 'questions/'"
    for path in paths:
        data = yaml.safe_load(open(path, encoding='utf-8')) or {}
        qs = data.get('questions')
        assert isinstance(qs, list), f"{path} missing 'questions' list"
        for q in qs:
            assert 'requirements' in q, f"{path}:{q.get('id')} missing requirements"
            req = q['requirements']
            assert isinstance(req, dict), f"{path}:{q.get('id')} requirements not a dict"
            assert req, f"{path}:{q.get('id')} has empty requirements"

@pytest.mark.parametrize("path, expected_kind", [
    ("questions/pod.yaml", "Pod"),
    ("questions/deployment.yaml", "Deployment"),
    ("questions/service.yaml", "Service"),
])
def test_resource_kind_in_requirements(path, expected_kind):
    """
    Spot-check that common resource questions derive the correct 'kind'.
    """
    data = yaml.safe_load(open(path, encoding='utf-8')) or {}
    for q in data.get('questions', []):
        req = q.get('requirements', {})
        kind = req.get('kind')
        assert kind == expected_kind, (
            f"{path}:{q.get('id')} expected kind={expected_kind} but got {kind}"
        )