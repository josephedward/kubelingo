import pytest
from kubelingo.question_generator import generate_questions, GenerationError

@pytest.mark.parametrize("kind", ["pod", "deployment", "service", "pvc", "configmap", "secret", "job"])
def test_generate_single_question(kind):
    questions = generate_questions(kind, count=1)
    assert isinstance(questions, list) and len(questions) == 1
    q = questions[0]
    # Required keys
    assert 'question' in q
    assert 'suggestion' in q and isinstance(q['suggestion'], list) and q['suggestion']
    assert 'source' in q and isinstance(q['source'], str)
    assert 'requirements' in q and isinstance(q['requirements'], dict)

def test_generate_multiple_unique_questions():
    questions = generate_questions('pod', count=2)
    assert len(questions) == 2
    texts = [q['question'] for q in questions]
    assert len(set(texts)) == 2

def test_generate_count_exceeds_options_raises():
    # POD has 3 names; requesting more unique questions than names should error
    with pytest.raises(GenerationError):
        generate_questions('pod', count=10)

def test_generate_unsupported_kind():
    with pytest.raises(GenerationError):
        generate_questions('foobar', count=1)