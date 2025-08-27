import pytest
from unittest.mock import MagicMock, patch

import os
import yaml
import pytest

# Changed import
import kubelingo.question_generator as qg
from kubelingo.kubelingo import _get_llm_model, QUESTIONS_DIR, load_questions, get_normalized_question_text

@pytest.fixture
def mock_llm_response():
    """Mocks the LLM response for generate_more_questions."""
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_model = MagicMock()
        mock_get_llm_model.return_value = ('gemini', mock_model)
        mock_model.generate_content.return_value.text = '''
questions:
  - question: "Create a Deployment named 'my-app' with 3 replicas using the nginx image."
    solution: |
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: my-app
      spec:
        replicas: 3
        selector:
          matchLabels:
            app: my-app
        template:
          metadata:
            labels:
              app: my-app
          spec:
            containers:
            - name: nginx
              image: nginx
    source: "https://kubernetes.io/docs/concepts/workloads/controllers/deployment/"
    rationale: "Tests basic Deployment creation and scaling."
'''
        yield

@pytest.fixture
def mock_load_questions():
    """Mocks load_questions to return a predefined set of existing questions."""
    with patch('kubelingo.question_generator.load_questions') as mock_load:
        mock_load.return_value = {
            'questions': [
                {'question': 'Existing Q1', 'solution': 'sol1', 'source': 'src1'},
                {'question': 'Existing Q2', 'solution': 'sol2', 'source': 'src2'}
            ]
        }
        yield

@pytest.fixture
def mock_load_questions_with_duplicate():
    """Mocks load_questions to include a question that will be a duplicate of the generated one."""
    with patch('kubelingo.question_generator.load_questions') as mock_load:
        mock_load.return_value = {
            'questions': [
                {'question': 'Existing Q1', 'solution': 'sol1', 'source': 'src1'},
                {"question": "Create a Deployment named 'my-app' with 3 replicas using the nginx image.", "solution": "sol_dup", "source": "src_dup"}
            ]
        }
        yield

def test_generate_more_questions_success(mock_llm_response, mock_load_questions):
    topic = "Deployments"
    question = {'question': 'Example Q', 'solution': 'example sol'}
    new_q = qg.generate_more_questions(topic, question)

    assert new_q is not None
    assert new_q['question'] == "Create a Deployment named 'my-app' with 3 replicas using the nginx image."
    assert 'suggestion' in new_q
    assert isinstance(new_q['suggestion'], list)
    assert new_q['source'] == "https://kubernetes.io/docs/concepts/workloads/controllers/deployment/"
    assert new_q['rationale'] == "Tests basic Deployment creation and scaling."

def test_generate_more_questions_no_llm_model():
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_get_llm_model.return_value = (None, None)
        topic = "Deployments"
        question = {'question': 'Example Q', 'solution': 'example sol'}
        new_q = qg.generate_more_questions(topic, question)
        assert new_q is None

def test_generate_more_questions_invalid_yaml_from_llm(mock_load_questions):
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_model = MagicMock()
        mock_get_llm_model.return_value = ('gemini', mock_model)
        mock_model.generate_content.return_value.text = 'This is not valid YAML'
        topic = "Deployments"
        question = {'question': 'Example Q', 'solution': 'example sol'}
        new_q = qg.generate_more_questions(topic, question)
        assert new_q is None

def test_generate_more_questions_missing_source(mock_load_questions):
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_model = MagicMock()
        mock_get_llm_model.return_value = ('gemini', mock_model)
        mock_model.generate_content.return_value.text = '''
questions:
  - question: "Question without source"
    solution: "some solution"
    rationale: "some rationale"
'''
        topic = "Deployments"
        question = {'question': 'Example Q', 'solution': 'example sol'}
        new_q = qg.generate_more_questions(topic, question)
        assert new_q is None # Expect None because source is missing

def test_generate_more_questions_duplicate_detected(mock_llm_response, mock_load_questions_with_duplicate):
    topic = "Deployments"
    question = {'question': 'Example Q', 'solution': 'example sol'}
    new_q = qg.generate_more_questions(topic, question)
    assert new_q is None # Expect None because a duplicate was detected
