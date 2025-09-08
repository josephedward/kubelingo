import pytest
from kubelingo.question_generator import QuestionGenerator
from unittest.mock import patch, MagicMock
import json

def test_ai_generated_question_diversity(monkeypatch):
    # Mock ai_chat to return distinct questions for diversity testing
    mock_responses = [
        '{"question": "Q1: Is Kubernetes open source?", "answer": "true"}',
        '{"question": "Q2: What is a Pod?", "answer": "A deployable unit."}',
        '{"question": "Q3: What is a Deployment?", "answer": "Manages replica Pods."}',
        '{"question": "Q4: What is a Service?", "answer": "Exposes applications."}',
        '{"question": "Q5: What is a ConfigMap?", "answer": "Stores non-confidential data."}',
        '{"question": "Q6: What is a Secret?", "answer": "Stores confidential data."}',
        '{"question": "Q7: What is Ingress?", "answer": "Manages external access."}',
        '{"question": "Q8: What is a Volume?", "answer": "Provides storage."}',
        '{"question": "Q9: What is RBAC?", "answer": "Manages permissions."}',
        '{"question": "Q10: What is Networking?", "answer": "Connects components."}',
    ]
    
    # Use a side_effect to return different responses on successive calls
    monkeypatch.setattr(QuestionGenerator, 'generate_ai_question', MagicMock(side_effect=lambda topic, question_type, exclude_question_texts: json.loads(mock_responses.pop(0))))

    generator = QuestionGenerator()
    num_questions_to_generate = 10
    generated_questions_text = []

    for _ in range(num_questions_to_generate):
        question = generator.generate_question(
            topic="pods",
            question_type="true/false"
        )
        generated_questions_text.append(question["question"])

    # Assert that all generated questions are unique by text
    assert len(set(generated_questions_text)) == num_questions_to_generate