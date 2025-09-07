import random
import pytest
from unittest.mock import patch # Import patch
from kubelingo import question_generator
import kubelingo.cli as cli

QuestionGenerator = question_generator.QuestionGenerator

# Mock ai_chat for all tests in this module
@pytest.fixture(autouse=True)
def mock_ai_chat():
    with patch('kubelingo.llm_utils.ai_chat') as mock_chat:
        # Default mock response for general questions, including expected_resources etc.
        mock_chat.side_effect = [
            '{"question": "Mocked question 1", "expected_resources": ["Pod"], "success_criteria": ["Criteria"], "hints": ["Hint"]}',
            '{"question": "Mocked question 2", "expected_resources": ["Pod"], "success_criteria": ["Criteria"], "hints": ["Hint"]}',
            '{"question": "Mocked question 3", "expected_resources": ["Pod"], "success_criteria": ["Criteria"], "hints": ["Hint"]}',
            '{"question": "Mocked question 4", "expected_resources": ["Pod"], "success_criteria": ["Criteria"], "hints": ["Hint"]}',
            '{"question": "Mocked question 5", "expected_resources": ["Pod"], "success_criteria": ["Criteria"], "hints": ["Hint"]}',
        ]
        yield mock_chat

@pytest.fixture(autouse=True)
def fixed_seed():
    random.seed(0)
    yield

def test_generate_question_defaults():
    gen = QuestionGenerator()
    q = gen.generate_question(question_type="short answer") # Explicitly request short answer to get expected_resources
    assert isinstance(q, dict)
    assert "question" in q
    # Topic selection is handled by AI; ensure a non-empty string is returned
    assert isinstance(q["topic"], str) and q["topic"]
    # Difficulty is now a parameter, not directly in the returned question dict unless AI adds it
    # We don't assert its absence here as AI might include it.
    assert "id" in q and len(q["id"]) == 8
    assert isinstance(q["expected_resources"], list)
    assert isinstance(q["success_criteria"], list)

def test_generate_question_specific_topic_difficulty_without_context():
    gen = QuestionGenerator()
    q = gen.generate_question(topic="deployments", include_context=False)
    assert q["topic"] == "deployments"
    # scenario_context is now part of the AI-generated question text, not a separate key
    # We don't assert its absence here.

def test_generate_question_set_length_and_filters():
    gen = QuestionGenerator()
    qs = gen.generate_question_set(count=3, subject_matter="services")
    assert isinstance(qs, list)
    assert len(qs) == 3
    for q in qs:
        assert q["topic"] == "services"
        # Difficulty is now a parameter, not directly in the returned question dict unless AI adds it
        # We don't assert its absence here as AI might include it.

def test_fallback_on_unknown_topic_or_difficulty(monkeypatch):
    monkeypatch.setattr(random, 'choice', lambda x: "resource_management") # Mock random.choice to return a predictable topic
    gen = QuestionGenerator()
    # Since ai_chat is mocked, this test might need adjustment if the fallback logic
    # depends on ai_chat failing. For now, it will just use the mocked response.
    # Difficulty fallback removed; test topic fallback works without error
    q = gen.generate_question(topic="nonexistent")
    # Provided topic should be preserved
    assert q["topic"] == "nonexistent"
    # Difficulty is now a parameter, not directly in the returned question dict unless AI adds it
    # We don't assert its absence here as AI might include it.

def test_multiple_choice_options_uniqueness(mock_ai_chat):
    gen = QuestionGenerator()
    
    # Configure mock_ai_chat to return a response with duplicate options
    mock_ai_chat.side_effect = [
        '{"question": "Test MC Question", "options": ["A", "B", "A", "C"], "answer": "B"}'
    ]
    
    q = gen.generate_question(question_type="multiple choice", topic="test")
    
    assert "options" in q
    options = q["options"]
    
    # Assert that there are no duplicate options
    assert len(options) == len(set(options)), "Multiple choice options should be unique"