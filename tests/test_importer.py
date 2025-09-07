import re
import uuid
import pytest
from kubelingo.importer import format_question

EXPECTED_KEYS = {"id", "topic", "question", "source", "suggested_answer", "user_answer", "ai_feedback"}

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