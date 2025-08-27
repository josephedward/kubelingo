import pytest
from unittest.mock import MagicMock, patch

import os
import yaml
import pytest
import random

# Changed import
import kubelingo.question_generator as qg
from kubelingo.kubelingo import _get_llm_model, QUESTIONS_DIR, load_questions, get_normalized_question_text

@pytest.fixture
def mock_yaml_safe_load():
    with patch('kubelingo.question_generator.yaml.safe_load') as mock_load:
        yield mock_load

@pytest.fixture
def mock_yaml_dump():
    with patch('kubelingo.question_generator.yaml.dump') as mock_dump:
        yield mock_dump

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
    assert 'solution' in new_q
    assert isinstance(new_q['solution'], str)
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

def test_generate_more_questions_missing_source(mock_load_questions, mock_googlesearch):
    mock_googlesearch.return_value = ['http://found-source.com']
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
        assert new_q is not None
        assert 'source' in new_q
        assert new_q['source'] == 'http://found-source.com' # Assuming assign_source finds this

def test_generate_more_questions_duplicate_detected(mock_llm_response, mock_load_questions_with_duplicate):
    topic = "Deployments"
    question = {'question': 'Example Q', 'solution': 'example sol'}
    new_q = qg.generate_more_questions(topic, question)
    assert new_q is None # Expect None because a duplicate was detected

# --- Tests for assign_source function ---

@pytest.fixture
def mock_googlesearch():
    with patch('kubelingo.question_generator.search') as mock_search:
        yield mock_search

def test_assign_source_already_has_source(mock_googlesearch):
    question = {'question': 'Test Q', 'source': 'http://example.com'}
    topic = 'test_topic'
    mock_fore = MagicMock()
    mock_style = MagicMock()
    mock_genai = MagicMock()
    assigned = qg.assign_source(question, topic, mock_fore, mock_style)
    assert not assigned
    assert question['source'] == 'http://example.com'
    mock_googlesearch.assert_not_called()

def test_assign_source_finds_source(mock_googlesearch):
    mock_googlesearch.return_value = ['http://found-source.com']
    question = {'question': 'Test Q'}
    topic = 'test_topic'
    mock_fore = MagicMock()
    mock_style = MagicMock()
    mock_genai = MagicMock()
    assigned = qg.assign_source(question, topic, mock_fore, mock_style)
    assert assigned
    assert question['source'] == 'http://found-source.com'
    mock_googlesearch.assert_called_once_with('kubernetes Test Q', num_results=1)

def test_assign_source_no_source_found(mock_googlesearch):
    mock_googlesearch.return_value = []
    question = {'question': 'Test Q'}
    topic = 'test_topic'
    mock_fore = MagicMock()
    mock_style = MagicMock()
    mock_genai = MagicMock()
    assigned = qg.assign_source(question, topic, mock_fore, mock_style)
    assert not assigned
    assert 'source' not in question
    mock_googlesearch.assert_called_once_with('kubernetes Test Q', num_results=1)

def test_assign_source_search_error(mock_googlesearch, capsys):
    mock_googlesearch.side_effect = Exception("Network error")
    question = {'question': 'Test Q'}
    topic = 'test_topic'
    mock_fore = MagicMock()
    mock_style = MagicMock()
    mock_genai = MagicMock()
    assigned = qg.assign_source(question, topic, mock_fore, mock_style)
    assert not assigned
    assert 'source' not in question
    mock_googlesearch.assert_called_once_with('kubernetes Test Q', num_results=1)
    # No print message expected when genai is enabled

def test_assign_source_ai_disabled_no_search_results(mock_googlesearch, capsys):
    mock_googlesearch.return_value = []
    question = {'question': 'Test Q'}
    topic = 'test_topic'
    mock_fore = MagicMock()
    mock_style = MagicMock()
    mock_genai = None # Simulate genai disabled
    assigned = qg.assign_source(question, topic, mock_fore, mock_style)
    assert not assigned
    assert 'source' not in question
    mock_googlesearch.assert_called_once_with('kubernetes Test Q', num_results=1)
    captured = capsys.readouterr()
    assert "Note: Could not find source for a question (AI disabled or search error: Network error)." not in captured.out # No error message for no results

def test_assign_source_ai_disabled_search_error(mock_googlesearch, capsys):
    mock_googlesearch.side_effect = Exception("Network error")
    question = {'question': 'Test Q'}
    topic = 'test_topic'
    mock_fore = MagicMock()
    mock_style = MagicMock()
    mock_genai = None # Simulate genai disabled
    assigned = qg.assign_source(question, topic, mock_fore, mock_style)
    assert not assigned
    assert 'source' not in question
    mock_googlesearch.assert_called_once_with('kubernetes Test Q', num_results=1)
    captured = capsys.readouterr()
    assert "Note: Could not find source for a question (AI disabled or search error: Network error)." in captured.out

def test_assign_source_ai_disabled_googlesearch_not_installed(capsys):
    with patch('kubelingo.question_generator.search', None): # Simulate googlesearch not installed
        question = {'question': 'Test Q'}
        topic = 'test_topic'
        mock_fore = MagicMock()
        mock_style = MagicMock()
        mock_genai = None # Simulate genai disabled
        assigned = qg.assign_source(question, topic, mock_fore, mock_style)
        assert not assigned
        assert 'source' not in question
        captured = capsys.readouterr()
        assert "Note: Could not find source for a question (googlesearch not installed and AI disabled)." in captured.out

@pytest.fixture
def mock_llm_model_gemini():
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_model = MagicMock()
        mock_get_llm_model.return_value = ('gemini', mock_model)
        mock_model.generate_content.return_value.text = '''
questions:
  - question: "New Gemini Q"
    solution: "New Gemini S"
    source: "http://gemini.source.com"
'''
        yield mock_model

@pytest.fixture
def mock_llm_model_openai():
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_model = MagicMock()
        mock_get_llm_model.return_value = ('openai', mock_model)
        mock_model.chat.completions.create.return_value.choices[0].message.content = '''
questions:
  - question: "New OpenAI Q"
    solution: "New OpenAI S"
    source: "http://openai.source.com"
'''
        yield mock_model

@pytest.fixture
def mock_llm_model_no_llm():
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_get_llm_model.return_value = (None, None)
        yield

@pytest.fixture
def mock_llm_model_error():
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_model = MagicMock()
        mock_get_llm_model.return_value = ('gemini', mock_model)
        mock_model.generate_content.side_effect = Exception("LLM generation error")
        yield

@pytest.fixture
def mock_llm_model_invalid_yaml():
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_model = MagicMock()
        mock_get_llm_model.return_value = ('gemini', mock_model)
        mock_model.generate_content.return_value.text = 'This is not valid YAML.'
        yield

def test_generate_more_questions_gemini(mock_llm_model_gemini, mock_load_questions, mock_yaml_dump, capsys):
    # mock_yaml_safe_load.side_effect = [{'questions': [{'question': 'New Gemini Q', 'solution': 'New Gemini S', 'source': 'http://gemini.source.com'}]}, {'questions': []}]
    # The above line is problematic because it causes the mock to be called multiple times.
    # Instead, we should mock the behavior of load_questions directly if it's called internally.
    # For this test, we assume load_questions is mocked by mock_load_questions fixture.

    existing_question = {'question': 'Old Q', 'solution': 'Old S'}
    topic = 'test_topic'
    
    with patch('random.choice', return_value='command'): # Control question type
        new_q = qg.generate_more_questions(topic, existing_question)
    
    mock_llm_model_gemini.generate_content.assert_called_once()
    assert new_q == {'question': 'New Gemini Q', 'solution': 'New Gemini S', 'source': 'http://gemini.source.com'}
    
    captured = capsys.readouterr()
    assert "New question generated!" in captured.out

def test_generate_more_questions_openai(mock_llm_model_openai, mock_load_questions, mock_yaml_dump, capsys):
    existing_question = {'question': 'Old Q', 'solution': 'Old S'}
    topic = 'test_topic'
    
    with patch('random.choice', return_value='manifest'): # Control question type
        new_q = qg.generate_more_questions(topic, existing_question)
    
    mock_llm_model_openai.chat.completions.create.assert_called_once()
    assert new_q == {'question': 'New OpenAI Q', 'solution': 'New OpenAI S', 'source': 'http://openai.source.com'}
    
    captured = capsys.readouterr()
    assert "New question generated!" in captured.out

def test_generate_more_questions_no_llm(mock_llm_model_no_llm, capsys):
    existing_question = {'question': 'Old Q', 'solution': 'Old S'}
    topic = 'test_topic'
    
    new_q = qg.generate_more_questions(topic, existing_question)
    
    assert new_q is None
    captured = capsys.readouterr()
    assert "INFO: Set GEMINI_API_KEY or OPENAI_API_KEY environment variables to generate new questions." in captured.out

def test_generate_more_questions_llm_error(mock_llm_model_error, capsys):
    existing_question = {'question': 'Old Q', 'solution': 'Old S'}
    topic = 'test_topic'
    
    new_q = qg.generate_more_questions(topic, existing_question)
    
    assert new_q is None
    captured = capsys.readouterr()
    assert "Error generating question: LLM generation error" in captured.out

def test_generate_more_questions_invalid_yaml_response(mock_llm_model_invalid_yaml, mock_load_questions, mock_yaml_safe_load, mock_yaml_dump, capsys):
    mock_yaml_safe_load.side_effect = yaml.YAMLError("Invalid YAML for testing") # Added line
    
    existing_question = {'question': 'Old Q', 'solution': 'Old S'}
    topic = 'test_topic'
    
    with patch('random.choice', return_value='command'):
        new_q = qg.generate_more_questions(topic, existing_question)
    
    assert new_q is None
    captured = capsys.readouterr()
    assert "AI failed to generate a valid question (invalid YAML). Please try again." in captured.out
