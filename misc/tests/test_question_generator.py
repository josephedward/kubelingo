import random
import importlib.util
from pathlib import Path

import pytest

# Load question_generator module from file
module_path = Path(__file__).parent.parent / "question_generator.py"
spec = importlib.util.spec_from_file_location("question_generator", str(module_path))
qg_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg_module)
QuestionGenerator = qg_module.QuestionGenerator
DifficultyLevel = qg_module.DifficultyLevel
KubernetesTopics = qg_module.KubernetesTopics

@pytest.fixture(autouse=True)
def fixed_seed():
    random.seed(0)
    yield

def test_generate_question_defaults():
    gen = QuestionGenerator()
    q = gen.generate_question()
    assert isinstance(q, dict)
    assert "question" in q
    assert q["topic"] in [t.value for t in KubernetesTopics]
    assert q["difficulty"] in [lvl.value for lvl in DifficultyLevel]
    assert "id" in q and len(q["id"]) == 8
    assert isinstance(q["expected_resources"], list)
    assert isinstance(q["success_criteria"], list)

def test_generate_question_specific_topic_difficulty_without_context():
    gen = QuestionGenerator()
    q = gen.generate_question(topic="deployments", difficulty="beginner", include_context=False)
    assert q["topic"] == "deployments"
    assert q["difficulty"] == "beginner"
    assert "scenario_context" not in q

def test_generate_question_set_length_and_filters():
    gen = QuestionGenerator()
    qs = gen.generate_question_set(count=3, topic="services", difficulty="intermediate")
    assert isinstance(qs, list)
    assert len(qs) == 3
    for q in qs:
        assert q["topic"] == "services"
        assert q["difficulty"] == "intermediate"

def test_fallback_on_unknown_topic_or_difficulty():
    gen = QuestionGenerator()
    q = gen.generate_question(topic="nonexistent", difficulty="expert")
    # Fallback should return pods beginner question when no templates match
    assert q["topic"] == "pods"
    assert q["difficulty"] == "beginner"