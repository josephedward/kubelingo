import random
import re
import pytest
from kubelingo.question_generator import QuestionGenerator
from kubelingo.cli_shim import KubernetesTopics

@pytest.fixture(autouse=True)
def fixed_seed():
    # Ensure reproducible context variable generation
    random.seed(0)
    yield

def test_context_variables_match_question():
    gen = QuestionGenerator()
    # Test for each Kubernetes topic
    for topic in [t.value for t in KubernetesTopics]:
        q = gen.generate_question(kind=topic, count=1)
        if isinstance(q, list):
            q = q[0]
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
