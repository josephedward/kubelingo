import random
import importlib.util
from pathlib import Path
import re
import glob
import json
import yaml

import pytest

# Load question_generator module from file
module_path = Path(__file__).parent.parent / "question_generator.py"
spec = importlib.util.spec_from_file_location("question_generator", str(module_path))
qg_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg_module)
QuestionGenerator = qg_module.QuestionGenerator
KubernetesTopics = qg_module.KubernetesTopics

@pytest.fixture(autouse=True)
def fixed_seed():
    random.seed(0)
    yield

def test_question_contains_required_details():
    """
    Tests that a generated question contains all the required details:
    - Question text with ID
    - Documentation link
    - Topic
    - Scenario Context
    """
    gen = QuestionGenerator()
    q = gen.generate_question(topic="services", include_context=True)

    assert isinstance(q, dict)

    # Test for question text with ID
    assert "question" in q
    assert isinstance(q["question"], str)
    assert len(q["question"]) > 0
    assert re.search(r'\[[a-f0-9]{8}\]$', q["question"]) is not None

    # Test for documentation link
    assert "documentation_link" in q
    assert isinstance(q["documentation_link"], str)
    assert q["documentation_link"].startswith("https://kubernetes.io/docs/concepts/")

    # Test for topic
    assert "topic" in q
    assert isinstance(q["topic"], str)
    assert q["topic"] == "services"

    # Test for scenario context
    assert "scenario_context" in q
    assert isinstance(q["scenario_context"], dict)
    assert "environment" in q["scenario_context"]
    assert "industry" in q["scenario_context"]
    assert "team_size" in q["scenario_context"]
    assert "constraints" in q["scenario_context"]

def test_static_question_suggestions_are_valid():
    """
    Tests that for static questions from files, if suggestions are present,
    their type matches the inferred question type.
    """
    question_files = glob.glob("questions/uncategorized/*.json")
    
    for file_path in question_files:
        with open(file_path) as f:
            try:
                q = json.load(f)
            except json.JSONDecodeError:
                # Skip malformed JSON files
                continue

        if "suggestions" in q and q["suggestions"]:
            is_manifest_question = False
            if isinstance(q["suggestions"][0], dict):
                is_manifest_question = True
            elif "manifest" in q.get("question", "").lower():
                is_manifest_question = True

            for suggestion in q["suggestions"]:
                if is_manifest_question:
                    assert isinstance(suggestion, dict), \
                        f"Suggestion for manifest question in {file_path} should be a dict."
                    # Simple structural validation for the manifest dict
                    assert "apiVersion" in suggestion, f"Manifest suggestion in {file_path} missing 'apiVersion'."
                    assert "kind" in suggestion, f"Manifest suggestion in {file_path} missing 'kind'."
                else:
                    # For non-manifest questions, suggestions should be strings.
                    assert isinstance(suggestion, str), \
                        f"Suggestion for non-manifest question in {file_path} should be a string."
