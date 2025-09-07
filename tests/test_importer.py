import re
import uuid
import pytest
import os
from kubelingo.importer import format_question, import_from_file

EXPECTED_KEYS = {"id", "topic", "question", "source", "suggested_answer", "user_answer", "ai_feedback"}


@pytest.fixture
def test_files_dir():
    return os.path.join(os.path.dirname(__file__), 'import_test_files')


def test_format_question_default_id_and_fields():
    q = format_question(
        topic="pods",
        question="What is a pod?",
        suggested_answer=" ans ",
        source="http://example.com/pods"
    )
    # Check keys
    assert set(q.keys()) == EXPECTED_KEYS
    # ID is 8 hex chars
    assert re.fullmatch(r"[0-9a-f]{8}", q["id"]), f"Unexpected id: {q['id']}"
    assert q["topic"] == "pods"
    assert q["question"] == "What is a pod?"
    assert q["source"] == "http://example.com/pods"
    # suggested_answer is stripped
    assert q["suggested_answer"] == "ans"
    # user_answer and ai_feedback start empty
    assert q["user_answer"] == ""
    assert q["ai_feedback"] == ""

def test_format_question_custom_id_uses_provided():
    custom_id = "abcdef12"
    q = format_question(
        topic="svc",
        question="Q",
        suggested_answer="A",
        source="S",
        qid=custom_id
    )
    assert q["id"] == custom_id

def test_format_question_strips_whitespace_answer():
    raw = "\n\tline1\nline2  "
    q = format_question(
        topic="t",
        question="q",
        suggested_answer=raw,
        source="s"
    )
    # leading/trailing whitespace removed, internal preserved
    assert q["suggested_answer"] == "line1\nline2"

def test_import_from_json(test_files_dir):
    json_path = os.path.join(test_files_dir, 'test.json')
    questions = import_from_file(json_path)
    assert len(questions) == 1
    q = questions[0]
    assert q['topic'] == 'pods'
    assert q['question'] == 'What is a pod?'
    assert q['suggested_answer'] == 'A pod is the smallest deployable unit in Kubernetes.'
    assert q['source'] == 'test.json'

def test_import_from_yaml(test_files_dir):
    yaml_path = os.path.join(test_files_dir, 'test.yaml')
    questions = import_from_file(yaml_path)
    assert len(questions) == 1
    q = questions[0]
    assert q['topic'] == 'services'
    assert q['question'] == 'What is a service?'
    assert q['suggested_answer'] == 'A service is an abstraction which defines a logical set of Pods and a policy by which to access them.'
    assert q['source'] == 'test.yaml'

def test_import_unsupported_file(test_files_dir):
    txt_path = os.path.join(test_files_dir, 'test.txt')
    questions = import_from_file(txt_path)
    assert questions == []

def test_import_non_existent_file():
    with pytest.raises(FileNotFoundError):
        import_from_file('non_existent_file.json')
