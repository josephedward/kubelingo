import random
import re
import importlib.util
from pathlib import Path

# Load question_generator module dynamically
module_path = Path(__file__).parent.parent / "question_generator.py"
spec = importlib.util.spec_from_file_location("question_generator", str(module_path))
qg_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg_module)
QuestionGenerator = qg_module.QuestionGenerator
KubernetesTopics = qg_module.KubernetesTopics

import pytest

@pytest.fixture(autouse=True)
def fixed_seed():
    # Ensure reproducible context variable generation
    random.seed(0)
    yield

def test_context_variables_match_question():
    gen = QuestionGenerator()
    # Test for each Kubernetes topic
    for topic in [t.value for t in KubernetesTopics]:
        q = gen.generate_question(topic=topic, include_context=True)
        assert isinstance(q, dict)
        question_text = q.get("question", "")
        context_vars = q.get("context_variables", {}) or {}
        # No leftover placeholders
        assert "{" not in question_text and "}" not in question_text
        # Each context variable value should appear in the question text
        for key, val in context_vars.items():
            # Convert to string for matching
            sval = str(val)
            assert sval in question_text, f"Context var '{key}={sval}' not found in question text '{question_text}'"