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
    random.seed(123)
    yield

def test_generate_tf_questions_basic():
    gen = QuestionGenerator()
    qs = gen.generate_tf_questions(topic="pods", count=4)
    assert isinstance(qs, list)
    assert len(qs) == 4
    seen = set()
    for q in qs:
        assert isinstance(q, dict)
        assert 'id' in q and isinstance(q['id'], str) and len(q['id']) == 8
        assert q.get('topic') == 'pods'
        assert q.get('type') == 'tf'
        qt = q.get('question')
        assert isinstance(qt, str) and qt.startswith('True or False:'), f"Bad question: {qt}"
        ans = q.get('answer')
        assert ans in ('true', 'false')
        seen.add(qt)
    # ensure no duplicate questions
    assert len(seen) == 4

def test_generate_tf_questions_excludes_used(tmp_path):
    # Setup temp correct folder with two used tf questions
    correct = tmp_path / 'correct'
    (correct / 'sub').mkdir(parents=True)
    used = []
    gen = QuestionGenerator()
    # pick two true statements
    true_items = [(t, d) for t, d in gen.VOCAB_DEFINITIONS.items()]
    stmt1 = f"True or False: {true_items[0][0]} is {true_items[0][1]}"
    stmt2 = f"True or False: {true_items[1][0]} is {true_items[1][1]}"
    used.extend([stmt1, stmt2])
    for i, stmt in enumerate(used, 1):
        data = {'id': f'id{i}', 'topic': 'pods', 'type': 'tf', 'question': stmt, 'answer': 'true'}
        (correct / 'sub' / f'q{i}.json').write_text(json.dumps(data))
    qs = gen.generate_tf_questions(topic='pods', count=10, correct_folder=str(correct))
    # answers should not include used statements
    questions_texts = {q['question'] for q in qs}
    assert stmt1 not in questions_texts
    assert stmt2 not in questions_texts

def test_generate_tf_questions_no_available(tmp_path):
    # Mark all possible statements used
    correct = tmp_path / 'correct'
    correct.mkdir()
    gen = QuestionGenerator()
    # generate all possibilities
    all_qs = []
    terms = list(gen.VOCAB_DEFINITIONS.items())
    for term, definition in terms:
        all_qs.append(f"True or False: {term} is {definition}")
        # wrong defs
        wrong_defs = [d for _, d in terms if d != definition]
        if wrong_defs:
            all_qs.append(f"True or False: {term} is {wrong_defs[0]}")
    # write all to correct folder
    for i, stmt in enumerate(all_qs):
        data = {'id': f'id{i}', 'topic': 'pods', 'type': 'tf', 'question': stmt, 'answer': 'true'}
        (correct / f'q{i}.json').write_text(json.dumps(data))
    qs = gen.generate_tf_questions(topic='pods', count=5, correct_folder=str(correct))
    assert qs == []