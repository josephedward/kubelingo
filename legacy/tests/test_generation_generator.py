import os
import json
import tempfile
import pytest
from kubelingo.generation.generator import QuestionGenerator, Question
from kubelingo.generation.difficulty import DifficultyLevel, KubernetesTopics

def test_generate_single_question_defaults():
    gen = QuestionGenerator()
    q = gen.generate_question()
    assert isinstance(q, Question)
    # topic and difficulty values
    assert q.topic in {t.value for t in KubernetesTopics}
    assert q.difficulty in DifficultyLevel
    # question text
    assert isinstance(q.question, str) and q.question
    # context variables and lists
    assert isinstance(q.context_variables, dict)
    assert isinstance(q.expected_resources, list) and len(q.expected_resources) >= 1
    assert isinstance(q.success_criteria, list) and len(q.success_criteria) >= 1
    assert isinstance(q.hints, list)
    assert isinstance(q.scenario_context, dict)

@pytest.mark.parametrize("count", [1, 3, 5])
def test_generate_question_set_length(count):
    gen = QuestionGenerator()
    qs = gen.generate_question_set(count=count)
    assert isinstance(qs, list)
    assert len(qs) == count
    for q in qs:
        assert isinstance(q, Question)

def test_save_questions_to_file(tmp_path):
    gen = QuestionGenerator()
    qs = gen.generate_question_set(count=2)
    file_path = tmp_path / "questions.json"
    gen.save_questions_to_file(qs, str(file_path))
    # Read back and verify JSON format
    data = json.loads(file_path.read_text(encoding='utf-8'))
    assert isinstance(data, list)
    assert len(data) == 2
    for item in data:
        assert set(item.keys()) >= {"id", "topic", "difficulty", "question", "context_variables", "expected_resources", "success_criteria", "hints", "scenario_context"}