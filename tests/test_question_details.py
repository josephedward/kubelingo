import random
import re
import glob
import json
import yaml

import pytest
from kubelingo import question_generator

QuestionGenerator = question_generator.QuestionGenerator

@pytest.fixture(autouse=True)
def fixed_seed():
    random.seed(0)
    yield

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
