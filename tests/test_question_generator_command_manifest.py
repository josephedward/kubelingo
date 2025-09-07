import json
import pytest
from kubelingo.question_generator import QuestionGenerator
import kubelingo.llm_utils as llm_utils

@pytest.fixture(autouse=True)
def mock_ai_chat(monkeypatch):
    # Provide a fake AI response for both command and manifest types
    def _fake_ai_chat(system_prompt, user_prompt):
        # Inspect prompt to decide type
        if 'command question' in system_prompt:
            return json.dumps({
                "question": "Scale deployment my-app to 3 replicas",
                "answer": "kubectl scale deployment my-app --replicas=3",
                "explanation": "Scales the deployment to specified replicas"
            })
        if 'manifest question' in system_prompt:
            return json.dumps({
                "question": "Create a Pod named nginx-pod",
                "answer": "apiVersion: v1\nkind: Pod\nmetadata:\n  name: nginx-pod\nspec:\n  containers:\n  - name: nginx\n    image: nginx",
                "explanation": "Defines a simple nginx Pod"
            })
        # Default fallback
        return json.dumps({"question": "Foo", "answer": "Bar", "explanation": "Baz"})
    monkeypatch.setattr(llm_utils, 'ai_chat', _fake_ai_chat)
    yield

def test_generate_command_question():
    gen = QuestionGenerator()
    q = gen.generate_question(topic="deployments", question_type="command")
    assert isinstance(q, dict)
    assert q.get('question_type') == 'command'
    assert 'Scale deployment my-app to 3 replicas' in q.get('question', '')
    assert q.get('answer') == 'kubectl scale deployment my-app --replicas=3'
    assert 'explanation' in q and isinstance(q['explanation'], str)

def test_generate_manifest_question():
    gen = QuestionGenerator()
    q = gen.generate_question(topic="pods", question_type="manifest")
    assert isinstance(q, dict)
    assert q.get('question_type') == 'manifest'
    answer = q.get('answer', '')
    # YAML should start with apiVersion
    assert answer.startswith('apiVersion: 1') or answer.startswith('apiVersion:')
    # Should contain kind
    assert 'kind: Pod' in answer
    assert 'explanation' in q and q['explanation'].startswith('Defines')