import os
import json
import random
import pytest
import importlib.util
from pathlib import Path

# Load the question_generator module
module_path = Path(__file__).parent.parent / "question_generator.py"
spec = importlib.util.spec_from_file_location("question_generator", str(module_path))
qg_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg_module)
QuestionGenerator = qg_module.QuestionGenerator

@pytest.fixture(autouse=True)
def fixed_seed():
    random.seed(42)
    yield

def test_generate_vocab_questions_basic():
    gen = QuestionGenerator()
    # Generate 3 vocab questions
    qs = gen.generate_vocab_questions(count=3)
    assert isinstance(qs, list)
    assert len(qs) == 3
    answers = set()
    for q in qs:
        assert isinstance(q, dict)
        assert q.get('type') == 'vocab'
        assert 'question' in q and isinstance(q['question'], str)
        assert q['question'].startswith("Which Kubernetes term matches")
        assert 'answer' in q and isinstance(q['answer'], str)
        # Topic must be present and equal to the expected term
        assert 'topic' in q and q['topic'] == q['answer']
        answers.add(q['answer'])
    # Ensure no duplicate answers
    assert len(answers) == 3

def test_generate_vocab_questions_excludes_used(tmp_path):
    # Setup a temp correct folder with one used vocab term
    correct = tmp_path / 'correct'
    correct.mkdir()
    used_term = 'pod'
    data = {'id': 'test1', 'type': 'vocab', 'question': '...', 'answer': used_term}
    (correct / 'q1.json').write_text(json.dumps(data))
    gen = QuestionGenerator()
    # Generate more questions than available to force filtering
    qs = gen.generate_vocab_questions(count=10, correct_folder=str(correct))
    # Ensure used term is not in answers
    answers = {q['answer'] for q in qs}
    assert used_term not in answers
    # Ensure at most total definitions - 1 questions generated
    total_defs = len(gen.VOCAB_DEFINITIONS)
    assert len(qs) <= total_defs - 1

def test_generate_vocab_questions_no_available(tmp_path):
    # Mark all definitions as used
    correct = tmp_path / 'correct'
    correct.mkdir()
    gen = QuestionGenerator()
    for term in gen.VOCAB_DEFINITIONS.keys():
        data = {'id': term, 'type': 'vocab', 'question': '', 'answer': term}
        (correct / f'{term}.json').write_text(json.dumps(data))
    # Now no definitions should remain
    qs = gen.generate_vocab_questions(count=5, correct_folder=str(correct))
    assert qs == []