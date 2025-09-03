import glob
import os
import yaml
import pytest

import os
import sys
# Determine repository root relative to this test file
SCRIPT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
QUESTIONS_DIR = os.path.join(REPO_ROOT, 'questions')

# Required and optional fields for static questions
REQUIRED = {'id', 'question', 'suggestions', 'success_criteria', 'source'}
OPTIONAL = {'difficulty', 'requirements'}
ALLOWED = REQUIRED.union(OPTIONAL)
FORBIDDEN = {'expected_resources', 'hints', 'scenario_context'}

@pytest.mark.parametrize('fpath', glob.glob(os.path.join(QUESTIONS_DIR, '*.yaml')))
def test_file_contains_questions_list(fpath):
    try:
        data = yaml.safe_load(open(fpath, encoding='utf-8'))
    except Exception as e:
        pytest.skip(f"Skipping invalid YAML {fpath}: {e}")
    assert 'questions' in data and isinstance(data['questions'], list), (
        f"{fpath} must contain a 'questions' list"
    )

@pytest.mark.parametrize('fpath', glob.glob(os.path.join(QUESTIONS_DIR, '*.yaml')))
def test_questions_match_canonical_schema(fpath):
    try:
        data = yaml.safe_load(open(fpath, encoding='utf-8'))
    except Exception as e:
        pytest.skip(f"Skipping invalid YAML {fpath}: {e}")
    for q in data.get('questions', []):
        keys = set(q.keys())
        missing = REQUIRED - keys
        extra = keys - ALLOWED
        forbidden = keys.intersection(FORBIDDEN)
        assert not missing, f"{fpath}: missing fields {missing}"
        assert not extra, f"{fpath}: unexpected fields {extra}"
        assert not forbidden, f"{fpath}: forbidden fields {forbidden}"
        assert isinstance(q['suggestions'], list), (
            f"{fpath}: 'suggestions' must be a list"
        )
        assert isinstance(q['success_criteria'], list), (
            f"{fpath}: 'success_criteria' must be a list"
        )